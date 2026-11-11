"""Excel export helpers."""

from io import BytesIO

import pandas as pd
from openpyxl.styles import Alignment

from app.models import ScrapeTask


REVIEW_COLUMNS = [
    "主题分类",
    "分类信心",
    "审查状态",
    "原文状态",
    "生效日期",
    "失效日期",
    "理由",
    "风险等级",
    "证据句子",
    "原文链接",
    "抓取时间",
    "人工改判",
]


def _column_width(column: str) -> int:
    normalized = column.lower()
    if any(name in normalized for name in ("序号", "编号", "sequence", "number")):
        return 8
    if any(name in normalized for name in ("链接", "网址", "link", "url")):
        return 80
    if any(name in normalized for name in ("标题", "title")):
        return 60
    if any(name in normalized for name in ("栏目", "频道", "section")):
        return 15
    if any(name in normalized for name in ("类别", "分类", "category", "type")):
        return 15
    if any(name in normalized for name in ("时间", "日期", "date", "time")):
        return 20
    if any(name in normalized for name in ("摘要", "简介", "summary", "description", "理由", "证据")):
        return 60
    return 24


def _format_sheet(sheet, columns: list[str]) -> None:
    for index, column in enumerate(columns, start=1):
        sheet.column_dimensions[sheet.cell(row=1, column=index).column_letter].width = _column_width(column)
    for row in sheet.iter_rows():
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            if cell.data_type == "f":
                cell.data_type = "s"


def _review_column_names(task: ScrapeTask) -> dict[str, str]:
    names: dict[str, str] = {}
    used = set(task.columns)
    for column in REVIEW_COLUMNS:
        candidate = column
        if candidate in used:
            candidate = f"合规{column}"
        while candidate in used:
            candidate = f"审查{candidate}"
        names[column] = candidate
        used.add(candidate)
    return names


def _review_rows(task: ScrapeTask, items: list[dict]) -> list[dict]:
    metadata_names = _review_column_names(task)
    result = []
    for index, item in enumerate(items, start=1):
        values = dict(item.get("extracted_values") or {})
        for column in task.columns:
            if any(name in column.lower() for name in ("序号", "编号", "sequence", "number")):
                values[column] = str(index)
        metadata_values = {
            "主题分类": item.get("classification_label", ""),
            "分类信心": (
                f"{item['classification_confidence']:.0%}"
                if item.get("classification_confidence") is not None
                else ""
            ),
            "审查状态": item.get("lifecycle_status", ""),
            "原文状态": item.get("status_text", ""),
            "生效日期": item.get("effective_date") or item.get("effective_date_str") or "",
            "失效日期": item.get("expiry_date") or item.get("expiry_date_str") or "",
            "理由": item.get("reason", ""),
            "风险等级": item.get("risk_level", ""),
            "证据句子": item.get("evidence", ""),
            "原文链接": item.get("link", ""),
            "抓取时间": item.get("captured_at", ""),
            "人工改判": item.get("manual_decision_note", ""),
        }
        values.update({
            metadata_names[column]: value
            for column, value in metadata_values.items()
        })
        result.append(values)
    return result


def export_xlsx(task: ScrapeTask) -> BytesIO:
    """Create an in-memory Excel workbook from a completed scrape."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        if not task.review_enabled:
            frame = pd.DataFrame(task.rows, columns=task.columns)
            frame.to_excel(writer, index=False, sheet_name="Lioran")
            _format_sheet(writer.sheets["Lioran"], task.columns)
        else:
            summary = {
                "项目": [
                    "网址",
                    "抓取时间",
                    "抓取页数",
                    "栏目数",
                    "审查总数",
                    "有效保留",
                    "排除",
                    "待生效",
                    "待人工复核",
                    "需人工确认",
                ],
                "结果": [
                    task.url,
                    task.created_at.isoformat(timespec="seconds"),
                    task.schema.get("pages_crawled", 0),
                    task.schema.get("sections_crawled", 0),
                    task.review_summary.get("total", 0),
                    task.review_summary.get("included", 0),
                    task.review_summary.get("excluded", 0),
                    task.review_summary.get("future", 0),
                    task.review_summary.get("manual_review", 0),
                    task.review_summary.get("needs_review", 0),
                ],
            }
            pd.DataFrame(summary).to_excel(writer, index=False, sheet_name="汇总")
            _format_sheet(writer.sheets["汇总"], ["项目", "结果"])
            writer.sheets["汇总"].column_dimensions["B"].width = 80
            groups = {
                "有效保留": [item for item in task.review_records if item.get("decision") == "included"],
                "排除": [item for item in task.review_records if item.get("decision") == "excluded"],
                "待生效": [item for item in task.review_records if item.get("decision") == "future"],
                "待人工复核": [
                    item for item in task.review_records
                    if item.get("decision") == "manual_review" or item.get("review_required")
                ],
            }
            metadata_columns = list(_review_column_names(task).values())
            for sheet_name, items in groups.items():
                columns = task.columns + metadata_columns
                frame = pd.DataFrame(_review_rows(task, items), columns=columns)
                frame.to_excel(writer, index=False, sheet_name=sheet_name)
                _format_sheet(writer.sheets[sheet_name], columns)
    output.seek(0)
    return output
