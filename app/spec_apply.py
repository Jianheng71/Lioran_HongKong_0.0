"""把澄清阶段锁定的规格应用到已经抽出的记录和表格上。

规格来自确认接口返回的可执行规则（id + rule）。这里只解释政策模板已经
写出的判定句，不另起一套问卷，也不在缺字段时编造数值。
"""

from __future__ import annotations

from datetime import date
import re
from typing import Any


DOC_NUMBER_RE = re.compile(r"[〔\[]\s*(20\d{2})\s*[〕\]]\s*(\d+)\s*号")
DATE_RE = re.compile(r"(20\d{2})\s*[-/.年]\s*(\d{1,2})\s*[-/.月]\s*(\d{1,2})")
READING_TERMS = ("政策解读", "答记者问", "新闻通稿", "解读", "通稿")
CENTRAL_MARKERS = ("国务院", "国发〔", "国办发", "中华人民共和国")
COLUMN_GROUPS = (
    {"标题", "名称", "title"},
    {"原文链接", "链接", "网址", "url", "link"},
    {"成文日期", "发布日期", "实施日期", "时间", "日期", "date", "published_at"},
    {"发文字号", "文号"},
    {"发文机关", "机关"},
    {"效力状态", "效力"},
    {"正文摘要", "摘要", "简介", "summary"},
    {"栏目名称", "栏目", "section"},
    {"类别", "分类", "category"},
    {"序号", "编号", "sequence"},
)


def rule_text(spec: list[dict] | None, item_id: str) -> str:
    if not spec:
        return ""
    for item in spec:
        if item.get("id") == item_id and isinstance(item.get("rule"), str):
            return item["rule"]
    return ""


def rules_by_id(spec: list[dict] | None) -> dict[str, str]:
    found: dict[str, str] = {}
    for item in spec or []:
        item_id = item.get("id")
        rule = item.get("rule")
        if isinstance(item_id, str) and isinstance(rule, str) and item_id and rule:
            found[item_id] = rule
    return found


def wants_detail_pages(spec: list[dict] | None) -> bool:
    """「只抓列表页」沿用现有队列；点名详情页或整栏目时才跟进每条原文。"""
    rule = rule_text(spec, "page_scope")
    return "详情" in rule or "整个政策法规栏目" in rule


def attach_rejected(spec: list[dict] | None) -> bool:
    return "另附" in rule_text(spec, "rejected_rows")


def spec_for_schema(spec: list[dict]) -> list[dict[str, str]]:
    return [
        {"id": str(item.get("id", "")), "rule": str(item.get("rule", ""))}
        for item in spec
        if item.get("id") and item.get("rule")
    ]


def annotate_schema(
    schema: dict[str, Any],
    spec: list[dict] | None,
    rejected: list[dict],
) -> dict[str, Any]:
    updated = dict(schema)
    if not spec:
        return updated
    updated["locked_spec"] = spec_for_schema(spec)
    updated["rejected_count"] = len(rejected)
    if attach_rejected(spec) and rejected:
        updated["rejected"] = rejected
    return updated


def apply_spec_to_records(
    records: list[dict],
    spec: list[dict] | None,
) -> tuple[list[dict], list[dict]]:
    """按已锁定规则筛、去重、排序并截断记录。返回 (保留, 淘汰)。"""
    if not spec:
        return [dict(record) for record in records], []
    rules = rules_by_id(spec)
    working = [dict(record) for record in records]
    limit = _row_limit(rules.get("max_count", ""))
    limit_first = _limit_before_filter(rules.get("filter_then_limit", ""))
    if limit is not None and limit_first:
        working = working[:limit]

    kept: list[dict] = []
    rejected: list[dict] = []
    for record in working:
        reason = _reject_reason(record, rules)
        if reason:
            rejected.append(_rejection(record, reason))
        else:
            kept.append(record)
    kept = _collapse_revisions(kept, rules.get("revision", ""))
    kept = _dedupe(kept, rules.get("dedupe", ""))
    kept = _sort_records(kept, rules.get("sorting", ""))
    if limit is not None and not limit_first and len(kept) > limit:
        for extra in kept[limit:]:
            rejected.append(_rejection(extra, "超过数量上限"))
        kept = kept[:limit]
    return kept, rejected


def apply_spec_to_table(
    columns: list[str],
    rows: list[list[str]],
    spec: list[dict] | None,
) -> tuple[list[str], list[list[str]], list[dict]]:
    """单页提取结果走同一套规则，再按输出列和「不许猜」收口。"""
    if not spec:
        return list(columns), [list(row) for row in rows], []
    records = []
    for row in rows:
        record = _row_to_record(columns, row)
        record["_cells"] = list(row)
        records.append(record)
    kept, rejected = apply_spec_to_records(records, spec)
    kept_rows = [list(record.get("_cells") or []) for record in kept]
    shaped_columns, shaped_rows = shape_output(columns, kept_rows, spec)
    return shaped_columns, shaped_rows, rejected


def shape_output(
    columns: list[str],
    rows: list[list[str]],
    spec: list[dict] | None,
) -> tuple[list[str], list[list[str]]]:
    """输出列和推断值策略作用在已经映射好的表格上。"""
    if not spec:
        return list(columns), [list(row) for row in rows]
    shaped = _blank_guesses(rows, rule_text(spec, "no_guessing"))
    wanted = _wanted_columns(rule_text(spec, "fields"))
    if not wanted:
        return list(columns), shaped
    indexes = [
        index for index, name in enumerate(columns) if _column_wanted(name, wanted)
    ]
    if not indexes or len(indexes) == len(columns):
        return list(columns), shaped
    return (
        [columns[index] for index in indexes],
        [
            [row[index] if index < len(row) else "" for index in indexes]
            for row in shaped
        ],
    )


def _title(record: dict) -> str:
    return str(record.get("title") or "")


def _blob(record: dict) -> str:
    return " ".join(
        str(record.get(key) or "")
        for key in ("title", "summary", "text", "published_at")
    )


def _rejection(record: dict, reason: str) -> dict[str, str]:
    return {
        "标题": _title(record),
        "链接": str(record.get("link") or ""),
        "淘汰原因": reason,
    }


def _reject_reason(record: dict, rules: dict[str, str]) -> str | None:
    checks = (
        _attachment_reason,
        _forward_reason,
        _reading_reason,
        _validity_reason,
        _tier_reason,
        _doc_type_reason,
        _time_reason,
    )
    for check in checks:
        reason = check(record, rules)
        if reason:
            return reason
    return None


def _attachment_reason(record: dict, rules: dict[str, str]) -> str | None:
    rule = rules.get("attachments", "")
    if not rule or "单独算一条" in rule:
        return None
    title = _title(record)
    if title.startswith("附件") or re.search(r"附件\s*\d", title):
        return "附件不单列"
    return None


def _forward_reason(record: dict, rules: dict[str, str]) -> str | None:
    exclude = rules.get("exclude_forward", "")
    judge = rules.get("forward_rule", "")
    if "保留" in exclude or "单独标注" in exclude:
        return None
    if (
        "排除" not in exclude
        and "不要转发" not in exclude
        and "即排除" not in judge
        and "双条件" not in judge
    ):
        return None
    title = _title(record)
    title_hit = "转发" in title or "转载" in title
    mismatch = _issuer_mismatch(record)
    if "双条件" in judge:
        if title_hit and mismatch:
            return "转发件"
        return None
    if "发文机关" in judge and "标题" not in judge:
        if mismatch:
            return "转发件"
        return None
    if title_hit:
        return "转发件"
    return None


def _issuer_mismatch(record: dict) -> bool:
    text = _title(record)
    central = any(token in text for token in ("国务院", "国发〔", "国办发"))
    local = any(token in text for token in ("省人民政府", "市人民政府", "区人民政府", "县人民政府"))
    return central and local


def _reading_reason(record: dict, rules: dict[str, str]) -> str | None:
    rule = rules.get("original_vs_reading", "")
    if "只要政策原文" not in rule:
        return None
    title = _title(record)
    if any(term in title for term in READING_TERMS):
        return "非政策原文"
    return None


def _validity_reason(record: dict, rules: dict[str, str]) -> str | None:
    validity = rules.get("validity", "")
    abolished = rules.get("abolished", "")
    title = _title(record)
    if "废止" in title and "只要现行有效" in validity and "含已废止" not in validity and "不限" not in validity:
        return "已废止或失效"
    if "废止" in title and "都排除" in abolished:
        return "已废止或失效"
    if ("尚未实施" in title or "尚未施行" in title) and "都排除" in abolished:
        return "尚未实施"
    return None


def _tier_reason(record: dict, rules: dict[str, str]) -> str | None:
    rule = rules.get("tier", "")
    if "只要本级" not in rule:
        return None
    title = _title(record)
    if any(token in title for token in CENTRAL_MARKERS):
        return "超出层级范围"
    return None


def _doc_type_reason(record: dict, rules: dict[str, str]) -> str | None:
    rule = rules.get("doc_types", "")
    if not rule or "全部公文" in rule:
        return None
    match = re.search(r"\{([^{}]*)\}", rule)
    if not match:
        return None
    allowed = [part.strip() for part in match.group(1).split(",") if part.strip()]
    if not allowed:
        return None
    title = _title(record)
    if any(token in title for token in allowed):
        return None
    return "文种不在范围内"


def _time_reason(record: dict, rules: dict[str, str]) -> str | None:
    boundary = rules.get("time_boundary", "")
    lower = rules.get("time_lower", "")
    rule = boundary if ("≥" in boundary or "文号年份" in boundary) else lower
    if not rule or "不限" in rule:
        return _missing_date_reason(record, rules)
    if "文号年份" in rule:
        year_match = re.search(r"(20\d{2})", rule)
        minimum = int(year_match.group(1)) if year_match else None
        year = _doc_year(record)
        if year is None:
            return _missing_date_reason(record, rules)
        if minimum is not None and year < minimum:
            return "早于时间条件"
        return None
    threshold = _parse_date(rule)
    if threshold is not None:
        found = _record_date(record)
        if found is None:
            return _missing_date_reason(record, rules)
        if found < threshold:
            return "早于时间条件"
        return None
    year_match = re.search(r"(20\d{2})\s*年", rule)
    if year_match:
        found = _record_date(record)
        if found is None:
            return _missing_date_reason(record, rules)
        if found.year < int(year_match.group(1)):
            return "早于时间条件"
        return None
    return _missing_date_reason(record, rules)


def _missing_date_reason(record: dict, rules: dict[str, str]) -> str | None:
    if _record_date(record) is not None or _doc_year(record) is not None:
        return None
    if "丢掉" in rules.get("missing_date", ""):
        return "缺少日期"
    return None


def _parse_date(value: str) -> date | None:
    match = DATE_RE.search(value or "")
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def _record_date(record: dict) -> date | None:
    for key in ("published_at", "title", "summary", "text"):
        found = _parse_date(str(record.get(key) or ""))
        if found:
            return found
    return None


def _doc_year(record: dict) -> int | None:
    match = DOC_NUMBER_RE.search(_blob(record))
    if match:
        return int(match.group(1))
    found = _record_date(record)
    return found.year if found else None


def _row_limit(rule: str) -> int | None:
    if not rule or "不限" in rule:
        return None
    match = re.search(r"(\d+)", rule)
    if not match:
        return None
    return int(match.group(1))


def _limit_before_filter(rule: str) -> bool:
    return "先取" in rule and "再筛" in rule


def _collapse_revisions(records: list[dict], rule: str) -> list[dict]:
    if "只留最新版" not in rule:
        return records
    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    for record in records:
        key = re.sub(r"\s+", "", _title(record).replace("修订", ""))
        key = re.sub(r"20\d{2}\s*年?", "", key)
        if key not in groups:
            order.append(key)
        groups.setdefault(key, []).append(record)
    kept: list[dict] = []
    for key in order:
        items = groups[key]
        if len(items) == 1 or not any("修订" in _title(item) for item in items):
            kept.extend(items)
            continue
        kept.append(max(items, key=_revision_score))
    return kept


def _revision_score(record: dict) -> tuple[int, date]:
    found = _record_date(record) or date.min
    revised = 1 if "修订" in _title(record) else 0
    return revised, found


def _dedupe(records: list[dict], rule: str) -> list[dict]:
    if not rule or "不去重" in rule:
        return records
    seen: set[tuple] = set()
    kept: list[dict] = []
    for record in records:
        if "标题" in rule:
            key = (_title(record), str(record.get("published_at") or ""))
        elif "字号" in rule or "文号" in rule:
            match = DOC_NUMBER_RE.search(_title(record))
            if not match:
                kept.append(record)
                continue
            key = (match.group(1), match.group(2))
        else:
            kept.append(record)
            continue
        if key in seen:
            continue
        seen.add(key)
        kept.append(record)
    return kept


def _sort_records(records: list[dict], rule: str) -> list[dict]:
    if "倒序" in rule:
        def by_date(record: dict) -> tuple[bool, date]:
            found = _record_date(record)
            return (found is not None, found or date.min)

        return sorted(records, key=by_date, reverse=True)
    if "字号" in rule or "文号" in rule:
        def by_number(record: dict) -> tuple[int, int, int]:
            match = DOC_NUMBER_RE.search(_title(record))
            if not match:
                return (1, 0, 0)
            return (0, int(match.group(1)), int(match.group(2)))

        return sorted(records, key=by_number)
    return records


def _blank_guesses(rows: list[list[str]], rule: str) -> list[list[str]]:
    if "不许猜" not in rule and "一律留空" not in rule:
        return [list(row) for row in rows]
    blanked: list[list[str]] = []
    for row in rows:
        blanked.append([
            "" if "（推断）" in str(cell) or "(推断)" in str(cell) else cell
            for cell in row
        ])
    return blanked


def _wanted_columns(rule: str) -> list[str]:
    if not rule:
        return []
    if "只要标题和链接" in rule:
        return ["标题", "原文链接"]
    if "再加正文摘要" in rule:
        return ["标题", "发文字号", "发文机关", "成文日期", "原文链接", "效力状态", "正文摘要"]
    if "输出列" not in rule:
        return []
    payload = rule.split("=", 1)[-1]
    return [part.strip() for part in re.split(r"\s*/\s*|、", payload) if part.strip()]


def _column_wanted(name: str, wanted: list[str]) -> bool:
    for token in wanted:
        if _columns_match(name.strip(), token):
            return True
    return False


def _columns_match(left: str, right: str) -> bool:
    if left == right:
        return True
    return any(left in group and right in group for group in COLUMN_GROUPS)


def _row_to_record(columns: list[str], row: list[str]) -> dict[str, str]:
    record = {
        "title": "",
        "link": "",
        "published_at": "",
        "summary": "",
        "section": "",
        "category": "",
        "source_url": "",
        "text": " ".join(str(cell) for cell in row),
    }
    slots = {
        "标题": "title",
        "名称": "title",
        "title": "title",
        "原文链接": "link",
        "链接": "link",
        "网址": "link",
        "url": "link",
        "link": "link",
        "成文日期": "published_at",
        "发布日期": "published_at",
        "实施日期": "published_at",
        "时间": "published_at",
        "日期": "published_at",
        "date": "published_at",
        "摘要": "summary",
        "简介": "summary",
        "正文摘要": "summary",
        "summary": "summary",
        "栏目": "section",
        "栏目名称": "section",
        "section": "section",
        "类别": "category",
        "分类": "category",
        "category": "category",
    }
    for name, value in zip(columns, row):
        slot = slots.get(str(name).strip())
        if slot and not record[slot]:
            record[slot] = str(value or "")
    if record["link"]:
        record["source_url"] = record["link"]
    return record
