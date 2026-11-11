"""Excel export helpers."""

from io import BytesIO

import pandas as pd

from app.models import ScrapeTask


def export_xlsx(task: ScrapeTask) -> BytesIO:
    """Create an in-memory Excel workbook from a completed scrape."""
    output = BytesIO()
    frame = pd.DataFrame(task.rows, columns=task.columns)
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False, sheet_name="Lioran")
        sheet = writer.sheets["Lioran"]
        widths = {
            "sequence": 8,
            "title": 60,
            "link": 80,
            "time": 20,
            "summary": 60,
            "section": 15,
            "category": 15,
        }
        for index, column in enumerate(task.columns, start=1):
            normalized = column.lower()
            if any(name in normalized for name in ("序号", "编号", "sequence", "number")):
                width = widths["sequence"]
            elif any(name in normalized for name in ("链接", "网址", "link", "url")):
                width = widths["link"]
            elif any(name in normalized for name in ("标题", "title")):
                width = widths["title"]
            elif any(name in normalized for name in ("栏目", "频道", "section")):
                width = widths["section"]
            elif any(name in normalized for name in ("类别", "分类", "category", "type")):
                width = widths["category"]
            elif any(name in normalized for name in ("摘要", "简介", "summary", "description")):
                width = widths["summary"]
            elif any(name in normalized for name in ("时间", "日期", "date", "time")):
                width = widths["time"]
            else:
                width = 24
            sheet.column_dimensions[sheet.cell(row=1, column=index).column_letter].width = width
        rejected = []
        if isinstance(task.schema, dict):
            rejected = task.schema.get("rejected") or []
        if rejected:
            pd.DataFrame(rejected).to_excel(writer, index=False, sheet_name="淘汰记录")
        for sheet in writer.sheets.values():
            for row in sheet.iter_rows():
                for cell in row:
                    if cell.data_type == "f":
                        cell.data_type = "s"
    output.seek(0)
    return output
