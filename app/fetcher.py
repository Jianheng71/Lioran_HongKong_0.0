"""Public-page checks and Scrapling-based fetching."""

import asyncio
import ipaddress
import re
import socket
import threading
import time
import truststore

truststore.inject_into_ssl()

from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.robotparser import RobotFileParser

from scrapling.fetchers import Fetcher, StealthyFetcher

from app.cleaner import is_captcha_or_challenge
from app.config import settings

USER_AGENT = "Lioran/0.1 (+https://github.com/Jianheng71/Lioran_HongKong_0.0)"
REDIRECT_CODES = {301, 302, 303, 307, 308}
MAX_REDIRECTS = 5
ROBOTS_CACHE_SECONDS = 3600
_robots_cache: dict[str, tuple[float, RobotFileParser]] = {}
_robots_cache_lock = threading.Lock()


class ScrapeError(Exception):
    """An expected, user-displayable scraping failure."""


def ensure_public_url(url: str) -> str:
    """只允许标准端口上的公开 HTTP(S) 地址。"""
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ScrapeError("请输入有效的公开网页链接（http 或 https）")
    if parsed.username or parsed.password:
        raise ScrapeError("链接不能包含用户名或密码")
    if parsed.port not in (None, 80, 443):
        raise ScrapeError("暂不支持非标准网页端口")

    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise ScrapeError("仅支持公开网页，不能访问本地地址")
    try:
        addresses = {ipaddress.ip_address(hostname)}
    except ValueError:
        try:
            addresses = {
                ipaddress.ip_address(result[4][0])
                for result in socket.getaddrinfo(hostname, parsed.port or 443, type=socket.SOCK_STREAM)
            }
        except (OSError, ValueError):
            raise ScrapeError("无法解析该网页地址，请检查链接") from None
    if not addresses or any(not address.is_global for address in addresses):
        raise ScrapeError("仅支持公开网页，不能访问内网或本地地址")
    return url


class _PublicRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urljoin(req.full_url, newurl)
        ensure_public_url(target)
        return super().redirect_request(req, fp, code, msg, headers, target)


def check_robots(url: str) -> None:
    """抓取前检查 robots.txt，并遵守目标网站规则。"""
    ensure_public_url(url)
    parsed = urlsplit(url)
    robots_url = urlunsplit((parsed.scheme, parsed.netloc, "/robots.txt", "", ""))
    with _robots_cache_lock:
        cached = _robots_cache.get(robots_url)
    if cached and time.monotonic() - cached[0] < ROBOTS_CACHE_SECONDS:
        parser = cached[1]
    else:
        parser = RobotFileParser()
        try:
            request = Request(robots_url, headers={"User-Agent": USER_AGENT})
            opener = build_opener(_PublicRedirectHandler)
            with opener.open(request, timeout=min(settings.request_timeout, 10)) as response:
                lines = response.read(512_000).decode("utf-8", errors="replace").splitlines()
            parser.set_url(robots_url)
            parser.parse(lines)
        except HTTPError as error:
            if error.code == 404:
                parser.parse([])
            elif error.code in {401, 403}:
                raise ScrapeError("该网站禁止抓取") from None
            else:
                raise ScrapeError("暂时无法检查网站抓取规则，请稍后再试") from None
        except (OSError, URLError, TimeoutError, ValueError):
            raise ScrapeError("暂时无法检查网站抓取规则，请稍后再试") from None
        with _robots_cache_lock:
            _robots_cache[robots_url] = (time.monotonic(), parser)
    if not parser.can_fetch(USER_AGENT, url):
        raise ScrapeError("该网站禁止抓取")


def fetch_page(
    url: str,
    timeout: int | None = None,
    force_stealth: bool = False,
    allowed_hosts: set[str] | None = None,
):
    """优先使用 Scrapling 高速请求，必要时切换到浏览器抓取器。"""
    current = ensure_public_url(url)
    timeout = timeout or settings.request_timeout
    if allowed_hosts and urlsplit(current).hostname not in allowed_hosts:
        raise ScrapeError("抓取链接超出了起始网站域名范围")
    if force_stealth:
        response = _fetch_stealthy(current, timeout, allowed_hosts)
        _reject_challenge(response)
        final_url = str(getattr(response, "url", current))
        ensure_public_url(final_url)
        if allowed_hosts and urlsplit(final_url).hostname not in allowed_hosts:
            raise ScrapeError("网页重定向到了起始网站以外的域名")
        return response
    for _ in range(MAX_REDIRECTS + 1):
        ensure_public_url(current)
        response = Fetcher.get(
            current,
            timeout=timeout,
            follow_redirects=False,
            headers={"User-Agent": USER_AGENT},
            retries=settings.max_retries,
            retry_delay=1,
        )
        status = getattr(response, "status", 200)
        if status in REDIRECT_CODES:
            headers = getattr(response, "headers", {})
            location = headers.get("location") or headers.get("Location")
            if not location:
                break
            next_url = ensure_public_url(urljoin(current, location))
            if allowed_hosts and urlsplit(next_url).hostname not in allowed_hosts:
                raise ScrapeError("网页重定向到了起始网站以外的域名")
            check_robots(next_url)
            current = next_url
            continue
        if status >= 400:
            raise ScrapeError("网页暂时无法访问，请确认链接有效且无需登录")
        _reject_challenge(response)
        if not _has_meaningful_content(response):
            response = _fetch_stealthy(current, timeout, allowed_hosts)
            _reject_challenge(response)
        final_url = getattr(response, "url", current)
        ensure_public_url(str(final_url))
        if allowed_hosts and urlsplit(str(final_url)).hostname not in allowed_hosts:
            raise ScrapeError("网页重定向到了起始网站以外的域名")
        return response
    raise ScrapeError("网页重定向次数过多或目标地址不安全")


def _fetch_stealthy(url: str, timeout: int, allowed_hosts: set[str] | None = None):
    try:
        async def page_setup(page, **kwargs) -> None:
            await guard_public_requests(page, allowed_hosts=allowed_hosts)

        return StealthyFetcher.fetch(
            url,
            headless=True,
            timeout=timeout * 1000,
            useragent=USER_AGENT,
            solve_cloudflare=False,
            page_setup=page_setup,
            retries=settings.max_retries,
            retry_delay=1,
        )
    except Exception as error:
        if "timeout" in type(error).__name__.lower() or "timed out" in str(error).lower():
            raise ScrapeError("页面加载太慢，请稍后再试") from None
        raise ScrapeError("网页加载失败，请换一个公开页面试试") from None


async def guard_public_requests(page, allowed_hosts: set[str] | None = None, **_) -> None:
    """Block browser navigation to private addresses and non-web protocols."""
    async def guard(route) -> None:
        target = urlsplit(route.request.url)
        if target.scheme not in {"http", "https"}:
            await route.abort()
            return
        if allowed_hosts and target.hostname not in allowed_hosts:
            await route.abort()
            return
        try:
            await asyncio.to_thread(ensure_public_url, route.request.url)
        except ScrapeError:
            await route.abort()
            return
        await route.continue_()

    await page.route("**/*", guard)


def _has_meaningful_content(response) -> bool:
    html = _response_html(response)
    return len(html) > 500


def _response_html(response) -> str:
    body = getattr(response, "body", b"")
    if isinstance(body, bytes):
        return body.decode(getattr(response, "encoding", "utf-8") or "utf-8", errors="replace")
    return str(body or "")


def _reject_challenge(response) -> None:
    text = re.sub(r"<[^>]+>", " ", _response_html(response))
    if is_captcha_or_challenge(text):
        raise ScrapeError("遇到验证码或安全挑战，请换个公开页面")
