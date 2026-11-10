"""End-to-end single-page scrape orchestration."""

import asyncio
import re
from typing import Any

from app.cleaner import (
    build_html_skeleton,
    clean_html,
    is_captcha_or_challenge,
    has_main_content,
    is_login_or_paywall,
    clean_value,
)
from app.config import settings
from app.fetcher import ScrapeError, check_robots, fetch_page
from app.models import ScrapeTask
from app.understander import FALLBACK_SELECTORS, generate_schema, understand_page


def _selector_count(page: Any, selector: str) -> int:
    try:
        return len(page.css(selector))
    except Exception:
        return 0


def _extract_value(record: Any, field: dict[str, str]) -> str:
    selector = field["selector"]
    field_type = field["type"]
    try:
        if field_type.startswith("attr:"):
            attribute = field_type.partition(":")[2]
            value = record.css(f"{selector}::attr({attribute})").get()
        else:
            element = record.css(selector).first
            value = element.get_all_text(separator=" ", strip=True) if element else ""
    except Exception:
        return ""
    return str(value or "").strip()


def _extract_rows(page: Any, schema: dict[str, Any], url: str) -> tuple[list[str], list[list[str]]]:
    columns = [field["name"] for field in schema["fields"]]
    rows: list[list[str]] = []
    seen_links: set[str] = set()
    for record in page.css(schema["base_selector"]):
        values = [
            clean_value(_extract_value(record, field), url, field["type"])
            for field in schema["fields"]
        ]
        if not any(values):
            continue
        link_index = next(
            (index for index, field in enumerate(schema["fields"]) if field["type"] == "attr:href"),
            None,
        )
        if link_index is not None and values[link_index]:
            if values[link_index] in seen_links:
                continue
            seen_links.add(values[link_index])
        rows.append(values)
    return columns, rows


def _validated_schema(schema: dict[str, Any], page: Any) -> dict[str, Any]:
    base_selector = schema["base_selector"]
    if not _selector_count(page, base_selector):
        raise ValueError("生成的记录选择器没有命中页面")
    for field in schema["fields"]:
        if not _selector_count(page, f'{base_selector} {field["selector"]}'):
            raise ValueError(f'字段“{field["name"]}”的选择器没有命中页面')
    return schema


async def scrape(url: str, requirement: str, feedback_row_index: int | None = None) -> ScrapeTask:
    """按理解、校验、提取顺序处理一个公开网页，并限制重试次数。"""
    await asyncio.to_thread(check_robots, url)
    try:
        markdown, cleaned_html = await asyncio.wait_for(
            understand_page(url),
            timeout=settings.request_timeout,
        )
    except asyncio.TimeoutError:
        raise ScrapeError("页面加载太慢，请稍后再试") from None
    except ScrapeError:
        raise
    except ValueError:
        raise ScrapeError("页面结构过于复杂，暂时无法生成抓取规则") from None
    except Exception as error:
        if "timeout" in type(error).__name__.lower() or "timed out" in str(error).lower():
            raise ScrapeError("页面加载太慢，请稍后再试") from None
        raise ScrapeError("无法读取页面结构，请确认页面是公开可访问的") from None

    lowered_page = re.sub(r"<[^>]+>", " ", cleaned_html).lower()
    if is_captcha_or_challenge(lowered_page):
        raise ScrapeError("遇到验证码或安全挑战，请换个公开页面")
    if is_login_or_paywall(lowered_page, has_main_content(cleaned_html)):
        raise ScrapeError("这个页面可能需要登录或订阅，请换个公开页面试试")

    try:
        response = await asyncio.to_thread(fetch_page, url, settings.request_timeout)
        from scrapling.parser import Selector

        skeleton_page = Selector(build_html_skeleton(cleaned_html))
        raw_html = response.body
        if isinstance(raw_html, bytes):
            raw_html = raw_html.decode(
                getattr(response, "encoding", "utf-8") or "utf-8",
                errors="replace",
            )
        page_url = str(getattr(response, "url", url))
        page = Selector(clean_html(str(raw_html)), url=page_url)
    except ScrapeError:
        raise
    except Exception as error:
        if "timeout" in type(error).__name__.lower() or "timed out" in str(error).lower():
            raise ScrapeError("页面加载太慢，请稍后再试") from None
        raise ScrapeError("网页抓取失败，请稍后重试") from None

    retried_with_browser = False
    retry_hint = ""
    last_error = ""
    for attempt in range(settings.max_retries):
        schema = None
        try:
            schema = await generate_schema(
                markdown,
                cleaned_html,
                requirement,
                feedback_row_index if attempt == 0 else None,
                retry_hint,
            )
            schema = _validated_schema(schema, page)
            columns, rows = await asyncio.to_thread(_extract_rows, page, schema, page_url)
            if rows:
                return ScrapeTask(
                    url=url,
                    requirement=requirement,
                    columns=columns,
                    rows=rows,
                    schema=schema,
                    feedback_row_index=feedback_row_index,
                )
            last_error = "该页面未提取到数据"
        except Exception as error:
            last_error = str(error) or last_error
            lowered_error = last_error.lower()
            if any(marker in lowered_error for marker in ("ollama", "litellm", "connection")):
                raise ScrapeError("无法连接本地 Ollama，请先启动 Ollama 并安装 hermes3:8b") from None
            if "timeout" in type(error).__name__.lower() or "timed out" in lowered_error:
                raise ScrapeError("本地模型响应超时，请确认 Ollama 已启动且模型可用") from None

        if schema:
            for selector in FALLBACK_SELECTORS:
                if (
                    selector == schema["base_selector"]
                    or not _selector_count(page, selector)
                    or not _selector_count(skeleton_page, selector)
                ):
                    continue
                fallback_schema = {**schema, "base_selector": selector}
                try:
                    _validated_schema(fallback_schema, page)
                    _validated_schema(fallback_schema, skeleton_page)
                    columns, rows = await asyncio.to_thread(
                        _extract_rows,
                        page,
                        fallback_schema,
                        page_url,
                    )
                except Exception:
                    continue
                if rows:
                    return ScrapeTask(
                        url=url,
                        requirement=requirement,
                        columns=columns,
                        rows=rows,
                        schema=fallback_schema,
                        feedback_row_index=feedback_row_index,
                    )

        if not retried_with_browser and attempt + 1 < settings.max_retries:
            try:
                response = await asyncio.to_thread(
                    fetch_page,
                    url,
                    settings.request_timeout,
                    True,
                )
                from scrapling.parser import Selector

                raw_html = response.body
                if isinstance(raw_html, bytes):
                    raw_html = raw_html.decode(
                        getattr(response, "encoding", "utf-8") or "utf-8",
                        errors="replace",
                    )
                page_url = str(getattr(response, "url", url))
                page = Selector(clean_html(str(raw_html)), url=page_url)
                retried_with_browser = True
            except ScrapeError:
                pass
        available = [selector for selector in FALLBACK_SELECTORS if _selector_count(page, selector)]
        retry_hint = (
            f"{last_error}. 可用的备用选择器候选：{', '.join(available) or '无'}"
        )

    raise ScrapeError("无法识别页面结构，请手动点选一行")
