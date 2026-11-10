"""Generic same-site crawling and repeated-list extraction."""

import asyncio
from collections import deque
from dataclasses import dataclass, field
from html import unescape
import logging
import re
import threading
import time
from typing import Any
from urllib.parse import urldefrag, urljoin, urlsplit, urlunsplit

from lxml import html as lxml_html

from app.config import settings
from app.fetcher import ScrapeError, check_robots, fetch_page
from app.local_llm import map_raw_fields
from app.models import CrawlJob, ScrapeTask

logger = logging.getLogger(__name__)
MAX_CRAWL_DEPTH = 3
MAX_CONCURRENT_FETCHES = 5
PAGE_CACHE_SECONDS = 3600
PAGE_CACHE_MAX_ITEMS = 1000
MAX_CACHE_HTML_BYTES = 2_000_000
BLOCKED_LINK_TERMS = (
    "login", "log in", "sign in", "register", "signup", "contact",
    "联系我们", "登录", "注册", "加入我们",
)
LINK_SKIP_CLASS_TERMS = ("footer", "advert", "ads", "cookie", "share", "social")
DATE_PATTERN = re.compile(
    r"(?:20\d{2}[-/.年]\s?\d{1,2}[-/.月]\s?\d{1,2}日?"
    r"|20\d{2}\s?年\s?\d{1,2}\s?月\s?\d{1,2}\s?日?"
    r"|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*"
    r"\s+\d{1,2},?\s+20\d{2}\b"
    r"|\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
    r"[a-z]*\s+20\d{2}\b"
    r"|\b(?:just now|yesterday|\d+\s+(?:secs?|seconds?|mins?|minutes?|hrs?|hours?|days?|weeks?|months?|years?)\s+ago)\b)",
    re.IGNORECASE,
)
_page_cache: dict[str, tuple[float, str, str]] = {}
_page_cache_lock = threading.Lock()


@dataclass
class RawRecord:
    title: str
    link: str
    published_at: str
    summary: str
    section: str
    category: str
    source_url: str

    def as_dict(self) -> dict[str, str]:
        return {
            "title": self.title,
            "link": self.link,
            "published_at": self.published_at,
            "summary": self.summary,
            "section": self.section,
            "category": self.category,
            "source_url": self.source_url,
        }


@dataclass
class PageAnalysis:
    title: str
    section: str
    page_type: str = "detail"
    records: list[RawRecord] = field(default_factory=list)
    links: list[tuple[str, str]] = field(default_factory=list)


def _host_key(host: str | None) -> str:
    normalized = (host or "").lower().rstrip(".")
    return normalized[4:] if normalized.startswith("www.") else normalized


def _canonical_url(url: str) -> str:
    parsed = urlsplit(urldefrag(url)[0])
    path = parsed.path or "/"
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, parsed.query, ""))


def _same_site(url: str, root_url: str) -> bool:
    return _host_key(urlsplit(url).hostname) == _host_key(urlsplit(root_url).hostname)


def _has_blocked_ancestor(node: Any) -> bool:
    current = node
    while current is not None:
        if current.tag in {"nav", "header", "footer", "aside", "form"}:
            return True
        classes = " ".join(
            (current.get("class") or "", current.get("id") or "", current.get("role") or "")
        ).lower()
        tokens = set(re.split(r"[\s_-]+", classes))
        if tokens.intersection({"nav", "navigation", "menu", "header", "footer", "sidebar", "crumb", "pager", "ad", "ads", "cookie", "share", "social"}) or any(
            term in classes for term in ("breadcrumb", "pagination", "advert")
        ):
            return True
        current = current.getparent()
    return False


def _visible_text(node: Any) -> str:
    text = " ".join(" ".join(node.itertext()).split())
    return unescape(text)


def _anchor_title(anchor: Any) -> str:
    headings = anchor.xpath(".//h1|.//h2|.//h3|.//h4|.//h5|.//h6")
    if headings:
        return max(
            (" ".join(item.text_content().split()) for item in headings),
            key=len,
        )
    return " ".join(
        (anchor.text_content() or anchor.get("title") or anchor.get("aria-label") or "").split()
    )


def _candidate_groups(document: Any) -> list[list[Any]]:
    groups: list[list[Any]] = []
    for parent in document.iter():
        if _has_blocked_ancestor(parent):
            continue
        children = [child for child in parent if isinstance(child.tag, str)]
        if len(children) < 3:
            continue
        buckets: dict[tuple[str, str], list[Any]] = {}
        for child in children:
            if _has_blocked_ancestor(child):
                continue
            signature = (
                child.tag.lower(),
                " ".join(sorted((child.get("class") or "").split())),
            )
            buckets.setdefault(signature, []).append(child)
        for (tag, classes), siblings in buckets.items():
            if len(siblings) < 3:
                continue
            classes_lower = classes.lower()
            class_tokens = set(re.split(r"[\s_-]+", classes_lower))
            if class_tokens.intersection({"nav", "navigation", "menu", "header", "footer", "sidebar", "crumb", "pager", "ad", "ads", "cookie", "share", "social"}) or any(
                term in classes_lower for term in ("breadcrumb", "pagination", "advert")
            ):
                continue
            if tag in {"script", "style", "template", "svg", "form"}:
                continue
            rows = []
            for node in siblings:
                hrefs = {
                    anchor.get("href")
                    for anchor in node.xpath(".//a[@href]")
                    if anchor.get("href")
                }
                if 1 <= len(hrefs) <= 2:
                    rows.append(node)
            if len(rows) < 3:
                continue
            groups.append(rows)
    return groups


def _extract_record(node: Any, source_url: str, section: str) -> RawRecord | None:
    anchors = node.xpath(".//a[@href]")
    if not anchors:
        return None
    anchor = max(anchors, key=lambda item: len(_anchor_title(item)))
    title = _anchor_title(anchor)
    if len(title) < 2:
        return None
    link = urljoin(source_url, anchor.get("href", "").strip())
    if urlsplit(link).scheme not in {"http", "https"} or not _same_site(link, source_url):
        return None
    path = urlsplit(link).path
    text = _visible_text(node)
    date_element = node.xpath(".//time[1]")
    published_at = ""
    if date_element:
        published_at = (
            date_element[0].get("datetime")
            or _visible_text(date_element[0])
        ).strip()
    if not published_at:
        date_match = DATE_PATTERN.search(text)
        published_at = date_match.group(0) if date_match else ""

    path_segments = [segment for segment in path.split("/") if segment]
    has_html_suffix = bool(re.search(r"\.(?:s?html?)$", path, re.I))
    shallow_section_link = (
        len(path_segments) <= 1 and len(title) <= 16
    ) or (
        len(path_segments) <= 2 and len(title) <= 6
    )
    if (
        shallow_section_link
        or (len(title) <= 6 and not published_at and not has_html_suffix)
    ):
        return None

    summary = " ".join(
        " ".join(node.xpath(".//text()[not(ancestor::a)]")).split()
    )
    if not summary:
        summary = text.replace(title, "", 1)
    if published_at:
        summary = summary.replace(published_at, "", 1)
    summary = " ".join(summary.split()).strip(" -|·•")
    if summary == title:
        summary = ""

    category = next(
        (
            f"{label}（推断）"
            for label, terms in (
                ("通知", ("通知", "notice", "announcement")),
                ("公告", ("公告", "公示", "announcement")),
                ("意见", ("意见", "opinion", "comment")),
                ("办法", ("办法", "条例", "规定", "measure", "regulation")),
                ("新闻", ("新闻", "news", "story")),
            )
            if any(term.lower() in title.lower() for term in terms)
        ),
        "",
    )
    return RawRecord(
        title=title,
        link=_canonical_url(link),
        published_at=published_at,
        summary=summary,
        section=section,
        category=category,
        source_url=source_url,
    )


def analyze_page(source_url: str, source_html: str, section_hint: str = "") -> PageAnalysis:
    """Extract generic list records and same-site links, excluding page chrome."""
    try:
        document = lxml_html.fromstring(source_html)
    except (TypeError, ValueError):
        return PageAnalysis(title="", section=section_hint)

    for node in document.xpath("//script|//style|//noscript|//iframe|//svg|//template"):
        parent = node.getparent()
        if parent is not None:
            parent.remove(node)

    title_node = document.xpath("//title[1]")
    title = " ".join(title_node[0].text_content().split()) if title_node else ""
    heading_node = document.xpath("//main//h1[1] | //article//h1[1] | //h1[1]")
    heading = " ".join(heading_node[0].text_content().split()) if heading_node else ""
    breadcrumbs = document.xpath(
        "//*[contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'breadcrumb')"
        " or contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'crumb')]"
    )
    breadcrumb_text = ""
    if breadcrumbs:
        breadcrumb_text = " ".join(_visible_text(breadcrumbs[0]).split())
    section = (
        title or section_hint
        if section_hint == "首页"
        else section_hint or heading or breadcrumb_text or title
    )
    section = re.sub(r"\s*[-_|｜]\s*[^-|｜]+$", "", section).strip()
    if not section_hint and not heading and not breadcrumb_text and section:
        section += "（推断）"

    records_by_link: dict[str, tuple[int, RawRecord]] = {}
    for group in _candidate_groups(document):
        if len(group) >= 3 and all(
            (urlsplit(urljoin(source_url, anchor.get("href", ""))).path or "/").endswith("/")
            for row in group
            for anchor in row.xpath(".//a[@href]")
            if anchor.get("href")
        ):
            continue
        for row in group:
            record = _extract_record(row, source_url, section)
            if record is None:
                continue
            score = -len({
                anchor.get("href")
                for anchor in row.xpath(".//a[@href]")
                if anchor.get("href")
            })
            previous = records_by_link.get(record.link)
            if previous is None or score > previous[0]:
                records_by_link[record.link] = (score, record)

    records = [item[1] for item in records_by_link.values()]

    record_links = {record.link for record in records}
    links: list[tuple[str, str]] = []
    seen_links: set[str] = set()
    for anchor in document.xpath("//a[@href]"):
        ancestor = anchor
        excluded_link_region = False
        while ancestor is not None:
            if ancestor.tag == "footer":
                excluded_link_region = True
                break
            classes = " ".join(
                (ancestor.get("class") or "", ancestor.get("id") or "", ancestor.get("role") or "")
            ).lower()
            if any(term in classes for term in LINK_SKIP_CLASS_TERMS):
                excluded_link_region = True
                break
            ancestor = ancestor.getparent()
        if excluded_link_region:
            continue
        href = urljoin(source_url, (anchor.get("href") or "").strip())
        parsed = urlsplit(href)
        label = _anchor_title(anchor)
        lowered = f"{label} {parsed.path}".lower()
        if (
            parsed.scheme not in {"http", "https"}
            or not _same_site(href, source_url)
            or href in record_links
            or not label
            or any(term in lowered for term in BLOCKED_LINK_TERMS)
            or re.search(r"\.(?:pdf|zip|rar|jpg|jpeg|png|gif|svg|mp4|docx?|xlsx?)$", parsed.path, re.I)
        ):
            continue
        canonical = _canonical_url(href)
        if canonical in seen_links:
            continue
        seen_links.add(canonical)
        links.append((canonical, label))
    return PageAnalysis(
        title=title,
        section=section,
        page_type="list" if len(records) >= 3 else "detail",
        records=records,
        links=links,
    )


def _is_pagination(label: str, url: str) -> bool:
    lowered = label.lower()
    path = urlsplit(url).path.lower()
    return (
        any(term in lowered for term in ("next", "previous", "下一页", "上一页", "更多", "more"))
        or bool(re.search(r"(?:page|p|index|list)[_-]?\d+", path))
        or any(key in urlsplit(url).query.lower() for key in ("page=", "p="))
    )


def _should_queue(url: str, label: str, current_url: str) -> bool:
    parsed = urlsplit(url)
    if len(label) > 160 or not parsed.path:
        return False
    path = parsed.path.lower()
    segments = [segment for segment in path.split("/") if segment]
    if any(
        segment in {"article", "articles", "story", "stories", "post", "posts", "detail", "details"}
        for segment in segments
    ):
        return False
    if re.search(r"/20\d{2}/(?:0[1-9]|1[0-2])/", path):
        return False
    is_pagination = _is_pagination(label, url)
    if is_pagination:
        return True
    is_section_link = any(
        term in f"{label} {path}".lower()
        for term in (
            "news", "channel", "category", "section", "list", "policy",
            "新闻", "栏目", "分类", "政策", "公告", "通知", "动态", "中心",
        )
    )
    if re.search(r"\.(?:pdf|zip|rar|jpg|jpeg|png|gif|svg|mp4|docx?|xlsx?)$", path, re.I):
        return False
    if re.search(r"\.(?:s?html?)$", path, re.I):
        return is_section_link and len(segments) <= 2 and len(label) <= 40
    if re.search(r"\.xml$", path, re.I):
        return False
    if len(segments) >= 3 and len(label) > 40 and is_section_link:
        return False
    if url == current_url:
        return False
    path_segments = [segment for segment in path.split("/") if segment]
    if len(path_segments) > 8:
        return False
    return True


def _cached_fetch(url: str, allowed_hosts: set[str]) -> tuple[str, str]:
    now = time.monotonic()
    with _page_cache_lock:
        cached = _page_cache.get(url)
        if cached and now - cached[0] < PAGE_CACHE_SECONDS:
            return cached[1], cached[2]
        if cached:
            del _page_cache[url]
    check_robots(url)
    response = fetch_page(url, settings.request_timeout, allowed_hosts=allowed_hosts)
    body = getattr(response, "body", b"")
    if isinstance(body, bytes):
        source_html = body.decode(
            getattr(response, "encoding", "utf-8") or "utf-8",
            errors="replace",
        )
    else:
        source_html = str(body or "")
    final_url = str(getattr(response, "url", url))
    if not _same_site(final_url, url):
        raise ScrapeError("网页重定向到了起始网站以外的域名")
    if len(source_html.encode("utf-8")) <= MAX_CACHE_HTML_BYTES:
        with _page_cache_lock:
            if len(_page_cache) >= PAGE_CACHE_MAX_ITEMS:
                oldest = min(_page_cache, key=lambda key: _page_cache[key][0])
                del _page_cache[oldest]
            _page_cache[url] = (time.monotonic(), source_html, final_url)
    return source_html, final_url


async def crawl_site(job: CrawlJob) -> ScrapeTask:
    """Crawl a bounded same-site graph breadth-first and produce a merged task."""
    root = _canonical_url(job.url)
    root_host = urlsplit(root).hostname or ""
    allowed_hosts = {root_host}
    if root_host.startswith("www."):
        allowed_hosts.add(root_host[4:])
    else:
        allowed_hosts.add(f"www.{root_host}")

    job.status = "running"
    queue: deque[tuple[str, int, str]] = deque([(root, 0, "首页")])
    queued: set[str] = {root}
    visited: set[str] = set()
    records_by_link: dict[str, RawRecord] = {}
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_FETCHES)
    errors = 0

    async def process_page(
        page_url: str,
        depth: int,
        section_hint: str,
    ) -> tuple[str, int, str, PageAnalysis | None, str | None]:
        async with semaphore:
            if job.stop_requested:
                return page_url, depth, section_hint, None, None
            try:
                source_html, final_url = await asyncio.to_thread(
                    _cached_fetch,
                    page_url,
                    allowed_hosts,
                )
                analysis = analyze_page(final_url, source_html, section_hint)
                return final_url, depth, section_hint, analysis, None
            except ScrapeError as error:
                return page_url, depth, section_hint, None, str(error)
            except Exception as error:
                logger.warning("Skipping crawl page %s: %s", page_url, error)
                return page_url, depth, section_hint, None, "读取页面失败"

    while queue and len(visited) < job.max_pages and not job.stop_requested:
        level = queue.popleft()
        page_url, depth, section_hint = level
        if page_url in visited:
            continue
        batch = [level]
        while queue and len(batch) < MAX_CONCURRENT_FETCHES and len(visited) + len(batch) < job.max_pages:
            next_entry = queue.popleft()
            if next_entry[0] not in visited:
                batch.append(next_entry)
        job.current_section = ", ".join(item[2] for item in batch[:3])
        results = await asyncio.gather(
            *(process_page(*item) for item in batch),
            return_exceptions=False,
        )
        for page_url, depth, section_hint, analysis, page_error in results:
            visited.add(page_url)
            job.pages_crawled = len(visited)
            if page_error:
                errors += 1
                continue
            if analysis is None:
                continue
            section = analysis.section or section_hint or "未识别栏目（推断）"
            if depth > 0:
                job.sections.add(section)
            job.current_section = section
            if analysis.page_type == "list":
                job.list_pages += 1
                if depth > 0:
                    for record in analysis.records:
                        records_by_link.setdefault(record.link, record)
            else:
                job.detail_pages += 1
            job.rows_count = len(records_by_link)
            if depth >= MAX_CRAWL_DEPTH or analysis.page_type != "list":
                continue
            for discovered_url, label in analysis.links:
                canonical = _canonical_url(discovered_url)
                if (
                    canonical in queued
                    or canonical in visited
                    or not _same_site(canonical, root)
                    or not _should_queue(canonical, label, page_url)
                ):
                    continue
                queued.add(canonical)
                inherited_section = label if depth == 0 else section
                queue.append((canonical, depth + 1, inherited_section))
                if len(queued) >= job.max_pages:
                    break

    if job.stop_requested:
        job.status = "stopped"
    job.current_section = "正在整理字段和合并结果"
    job.status = "mapping"
    records = list(records_by_link.values())
    columns, rows, mapping = await asyncio.to_thread(
        map_raw_fields,
        job.requirement,
        [record.as_dict() for record in records],
    )
    job.rows_count = len(rows)
    task = ScrapeTask(
        url=job.url,
        requirement=job.requirement,
        columns=columns,
        rows=rows,
        schema={
            "template": "site_crawl",
            "max_depth": MAX_CRAWL_DEPTH,
            "max_pages": job.max_pages,
            "pages_crawled": job.pages_crawled,
            "list_pages": job.list_pages,
            "detail_pages": job.detail_pages,
            "sections_crawled": len(job.sections),
            "errors": errors,
            "field_mapping": mapping,
        },
    )
    job.current_section = ""
    job.status = "stopped" if job.stop_requested else "completed"
    return task
