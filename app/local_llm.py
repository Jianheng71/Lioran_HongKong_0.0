"""Helpers for validating JSON emitted by Ollama-hosted Hermes."""

import json
import re
from typing import Any


TOOL_CALL_PATTERN = re.compile(r"<tool_call>\s*(.*?)\s*</tool_call>", re.DOTALL)


def parse_model_json(content: str | dict[str, Any]) -> dict[str, Any]:
    """Parse plain JSON or Hermes' XML-wrapped tool-call JSON."""
    if isinstance(content, dict):
        return content
    if not isinstance(content, str):
        raise ValueError("本地模型没有返回 JSON")

    match = TOOL_CALL_PATTERN.search(content)
    candidate = match.group(1).strip() if match else content.strip()
    candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", candidate, flags=re.IGNORECASE)
    parsed = json.loads(candidate)
    if not isinstance(parsed, dict):
        raise ValueError("本地模型返回的 JSON 格式不正确")
    return parsed


def normalize_schema(value: str | dict[str, Any]) -> dict[str, Any]:
    """Normalize Crawl4AI schema output to Lioran's snake-case contract."""
    schema = parse_model_json(value)
    base_selector = schema.get("base_selector") or schema.get("baseSelector")
    fields = schema.get("fields")
    if not isinstance(base_selector, str) or not isinstance(fields, list):
        raise ValueError("模型没有生成有效的 CSS 抓取规则")

    normalized_fields: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for field in fields:
        if not isinstance(field, dict):
            continue
        name = str(field.get("name", "")).strip()
        selector = str(field.get("selector", "")).strip()
        field_type = str(field.get("type", "text")).strip()
        if field_type == "attribute":
            field_type = f'attr:{field.get("attribute", "href")}'
        valid_type = field_type == "text" or bool(
            re.fullmatch(r"attr:[a-zA-Z_][a-zA-Z0-9_-]*", field_type)
        )
        if (
            name
            and name not in seen_names
            and selector
            and valid_type
            and re.fullmatch(r"[a-z][a-z0-9_]*", name)
        ):
            normalized_fields.append(
                {"name": name, "selector": selector, "type": field_type}
            )
            seen_names.add(name)
    if not normalized_fields:
        raise ValueError("模型没有生成可用的数据字段")

    template = schema.get("template", "list")
    if template not in {"list", "detail", "article"}:
        template = "list"
    return {
        "template": template,
        "page_type": schema.get("page_type", "list"),
        "base_selector": base_selector.strip(),
        "fields": normalized_fields,
    }
