"""清理网页并压缩结构样本，规范化提取结果。"""

from collections import defaultdict
from dataclasses import dataclass, field
from html import escape
from html.parser import HTMLParser
import re
from typing import Iterable
from urllib.parse import urljoin

DROP_TAGS = {"script", "style", "nav", "footer", "header", "noscript", "iframe"}
DROP_CLASSES = {"ad", "popup", "cookie"}
VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}
MAX_MARKDOWN_CHARS = 32_000
MAX_SKELETON_CHARS = 12_000
MAX_MARKDOWN_TOKENS = 8_000
MARKDOWN_TOKEN = re.compile(r"[\u3400-\u9fff]|[A-Za-z0-9]{1,4}|[^\s]")
AD_WORDS = re.compile(r"\b(advertisement|sponsored|cookie|subscribe now)\b", re.I)
CARD_WORDS = re.compile(r"(card|item|article|post|news|entry|record|result)", re.I)


@dataclass
class HtmlNode:
    tag: str
    attrs: dict[str, str]
    parent: "HtmlNode | None" = None
    children: list["HtmlNode | str"] = field(default_factory=list)


class _TreeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = HtmlNode("document", {})
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key.lower(): value or "" for key, value in attrs}
        node = HtmlNode(tag.lower(), attrs_dict, self.stack[-1])
        self.stack[-1].children.append(node)
        if tag.lower() not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() not in VOID_TAGS and len(self.stack) > 1:
            self.stack.pop()

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag.lower():
                del self.stack[index:]
                return

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.stack[-1].children.append(data)


def _is_dropped(node: HtmlNode) -> bool:
    classes = set(node.attrs.get("class", "").lower().split())
    return node.tag in DROP_TAGS or bool(classes & DROP_CLASSES)


def _walk(node: HtmlNode) -> Iterable[HtmlNode]:
    for child in node.children:
        if isinstance(child, HtmlNode):
            if not _is_dropped(child):
                yield child
                yield from _walk(child)


def _signature(node: HtmlNode) -> tuple[str, tuple[str, ...]]:
    return node.tag, tuple(sorted(node.attrs.get("class", "").split()))


def _size(node: HtmlNode) -> int:
    return 1 + sum(_size(child) for child in node.children if isinstance(child, HtmlNode))


def _candidate_group(root: HtmlNode) -> tuple[HtmlNode, list[HtmlNode]] | None:
    candidates: list[tuple[float, HtmlNode, list[HtmlNode]]] = []
    for parent in _walk(root):
        groups: dict[tuple[str, tuple[str, ...]], list[HtmlNode]] = defaultdict(list)
        for child in parent.children:
            if isinstance(child, HtmlNode) and not _is_dropped(child):
                groups[_signature(child)].append(child)
        for (_, classes), nodes in groups.items():
            if len(nodes) < 3:
                continue
            average_size = sum(_size(node) for node in nodes[:3]) / min(len(nodes), 3)
            class_text = " ".join(classes)
            score = len(nodes) * average_size
            if CARD_WORDS.search(class_text):
                score *= 1.5
            candidates.append((score, parent, nodes))
    if not candidates:
        return None
    _, parent, nodes = max(candidates, key=lambda item: item[0])
    return parent, nodes[:3]


def _serialize(node: HtmlNode, selected_children: dict[int, set[int]] | None = None) -> str:
    if _is_dropped(node):
        return ""
    if node.tag == "document":
        return "".join(
            _serialize(child, selected_children)
            for child in node.children
            if isinstance(child, HtmlNode)
        )
    attrs: list[str] = []
    for key in ("class",):
        value = node.attrs.get(key, "").strip()
        if value:
            attrs.append(f'{key}="{escape(value[:200], quote=True)}"')
    if node.tag in {"a", "area"}:
        attrs.append('href=""')
    if node.tag == "time":
        attrs.append('datetime=""')
    start = f"<{node.tag}{(' ' + ' '.join(attrs)) if attrs else ''}>"
    if node.tag in VOID_TAGS:
        return start
    parts = [start]
    for child in node.children:
        if isinstance(child, HtmlNode):
            allowed = selected_children.get(id(node)) if selected_children else None
            if allowed is None or id(child) in allowed:
                parts.append(_serialize(child, selected_children))
    parts.append(f"</{node.tag}>")
    return "".join(parts)


def _serialize_pruned(root: HtmlNode, parent: HtmlNode, cards: list[HtmlNode]) -> str:
    selected_children = {id(parent): {id(card) for card in cards}}
    current = parent
    while current is not root:
        if current.parent is not None:
            selected_children[id(current.parent)] = {id(current)}
            current = current.parent
        else:
            break
    return _serialize(root, selected_children)


def build_html_skeleton(html: str) -> str:
    """保留最多三个重复卡片的标签与 class，移除长文本。"""
    parser = _TreeParser()
    parser.feed(html)
    group = _candidate_group(parser.root)
    if group:
        skeleton = _serialize_pruned(parser.root, group[0], group[1])
    else:
        content = next(
            (node for node in _walk(parser.root) if node.tag in {"main", "article"}),
            None,
        )
        skeleton = _serialize(content) if content else _serialize(parser.root)
    if len(skeleton) <= MAX_SKELETON_CHARS:
        return skeleton
    raise ValueError("页面结构过于复杂，无法生成安全的精简 HTML 骨架")


def clean_html(html: str) -> str:
    """Remove unwanted page regions while preserving content structure."""
    parser = _TreeParser()
    parser.feed(html)

    def render(node: HtmlNode) -> str:
        if _is_dropped(node):
            return ""
        attrs = "".join(
            f' {key}="{escape(value[:500], quote=True)}"'
            for key, value in node.attrs.items()
            if key in {"class", "id", "href", "datetime"}
        )
        if node.tag in VOID_TAGS:
            return f"<{node.tag}{attrs}>"
        content = "".join(
            render(child) if isinstance(child, HtmlNode) else escape(child, quote=False)
            for child in node.children
        )
        return f"<{node.tag}{attrs}>{content}</{node.tag}>"

    return "".join(render(child) for child in parser.root.children if isinstance(child, HtmlNode))


def normalize_markdown(markdown: str) -> tuple[str, bool]:
    """将交给本地模型的 Markdown 限制在约 8,000 tokens 内。"""
    if len(markdown) <= MAX_MARKDOWN_CHARS and sum(
        1 for _ in MARKDOWN_TOKEN.finditer(markdown)
    ) <= MAX_MARKDOWN_TOKENS:
        return markdown, False
    end = 0
    for index, match in enumerate(MARKDOWN_TOKEN.finditer(markdown)):
        if index >= MAX_MARKDOWN_TOKENS:
            break
        if match.end() > MAX_MARKDOWN_CHARS:
            break
        end = match.end()
    return markdown[:end].rstrip() + "\n\n页面过长，已截取头部。", True


def clean_value(value: object, base_url: str, field_type: str) -> str:
    text = " ".join(str(value or "").split()).strip()
    if field_type == "attr:href" and text:
        absolute_url = urljoin(base_url, text)
        if absolute_url.startswith(("http://", "https://")):
            return absolute_url
        return ""
    if AD_WORDS.search(text):
        return ""
    return text


def has_main_content(html: str) -> bool:
    """判断清理后的页面是否仍包含足够的正文文本。"""
    parser = _TreeParser()
    parser.feed(html)

    def text_content(node: HtmlNode) -> str:
        return " ".join(
            text_content(child) if isinstance(child, HtmlNode) else child.strip()
            for child in node.children
        ).strip()

    content_nodes = [
        node for node in _walk(parser.root) if node.tag in {"main", "article"}
    ]
    if content_nodes:
        return any(len(text_content(node)) > 120 for node in content_nodes)
    return len(text_content(parser.root)) > 120


def is_captcha_or_challenge(text: str) -> bool:
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in (
            "captcha",
            "verify you are human",
            "checking your browser",
            "just a moment...",
            "cf-challenge",
            "cloudflare ray id",
            "attention required",
        )
    )


def is_login_or_paywall(text: str, has_main_content: bool) -> bool:
    if has_main_content:
        return False
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in ("请登录", "登录后", "subscribe", "paywall", "付费", "sign in to continue")
    )
