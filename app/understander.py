"""使用 Crawl4AI 理解页面并生成 CSS 抽取规则。"""

import asyncio
import re
from typing import Any

from app.cleaner import (
    build_html_skeleton,
    clean_html,
    is_captcha_or_challenge,
    is_login_or_paywall,
    has_main_content,
    normalize_markdown,
)
from app.config import settings
from app.fetcher import guard_public_requests
from app.fetcher import ScrapeError
from app.local_llm import normalize_schema
from app.prompts import FEEDBACK_HINT, RETRY_HINT, SCHEMA_QUERY

FALLBACK_SELECTORS = ("h1", "h2", ".title", ".item", "article", "li", ".card")


def _markdown_text(result: Any) -> str:
    markdown = getattr(result, "markdown", "") or ""
    if isinstance(markdown, str):
        return markdown
    return (
        getattr(markdown, "raw_markdown", None)
        or getattr(markdown, "fit_markdown", None)
        or str(markdown)
    )


async def understand_page(url: str) -> tuple[str, str]:
    """通过 Crawl4AI 获取 Markdown 与清理后的 HTML。"""
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig

    browser_config = BrowserConfig(headless=True, verbose=False)
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        word_count_threshold=10,
        page_timeout=settings.request_timeout * 1000,
    )
    async with AsyncWebCrawler(config=browser_config) as crawler:
        crawler.crawler_strategy.set_hook(
            "on_page_context_created",
            guard_public_requests,
        )
        result = await crawler.arun(url=url, config=run_config)
    raw_html = getattr(result, "cleaned_html", None) or getattr(result, "html", "") or ""
    cleaned = clean_html(raw_html)
    page_text = re.sub(r"<[^>]+>", " ", cleaned).lower()
    if is_captcha_or_challenge(page_text):
        raise ScrapeError("遇到验证码或安全挑战，请换个公开页面")
    if is_login_or_paywall(page_text, has_main_content(cleaned)):
        raise ScrapeError("这个页面可能需要登录或订阅，请换个公开页面试试")
    if not getattr(result, "success", False):
        raise RuntimeError("网页加载失败")
    markdown, _ = normalize_markdown(_markdown_text(result))
    return markdown, cleaned


async def generate_schema(
    markdown: str,
    cleaned_html: str,
    requirement: str,
    feedback_row_index: int | None = None,
    retry_hint: str = "",
) -> dict[str, Any]:
    """使用 Crawl4AI 的 HTML schema API 生成并校验 CSS 规则。"""
    from crawl4ai import JsonCssExtractionStrategy, LLMConfig

    skeleton = build_html_skeleton(cleaned_html)
    query = SCHEMA_QUERY.format(
        requirement=requirement,
        markdown=markdown,
    )
    if feedback_row_index is not None:
        query += FEEDBACK_HINT.format(row_index=feedback_row_index + 1)
    if retry_hint:
        query += RETRY_HINT.format(details=retry_hint)

    llm_config = LLMConfig(
        provider=f"ollama/{settings.ollama_model}",
        api_token="no_token",
        base_url=settings.ollama_base_url,
        temperature=0.1,
    )
    raw_schema = await asyncio.to_thread(
        JsonCssExtractionStrategy.generate_schema,
        html=skeleton,
        schema_type="CSS",
        query=query,
        llm_config=llm_config,
        validate=False,
        max_refinements=0,
    )
    schema = normalize_schema(raw_schema)
    from scrapling.parser import Selector

    sample = Selector(skeleton)
    if not _matches(sample, schema["base_selector"]):
        for fallback in FALLBACK_SELECTORS:
            if _matches(sample, fallback) and _fields_match(sample, schema, fallback):
                schema["base_selector"] = fallback
                break
        else:
            raise ValueError("base_selector 不在精简 HTML 骨架中，备用选择器也未命中")
    if not _fields_match(sample, schema, schema["base_selector"]):
        raise ValueError("字段选择器不在精简 HTML 骨架中")
    return schema


def _matches(page: Any, selector: str) -> bool:
    try:
        return bool(page.css(selector))
    except Exception:
        return False


def _fields_match(page: Any, schema: dict[str, Any], base_selector: str) -> bool:
    for field in schema["fields"]:
        selector = field["selector"]
        if "//" in selector or "xpath" in selector.lower():
            return False
        if not _matches(page, f'{base_selector} {selector}'):
            return False
    return True
