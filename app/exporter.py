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
        for row in writer.sheets["Lioran"].iter_rows():
            for cell in row:
                if cell.data_type == "f":
                    cell.data_type = "s"
    output.seek(0)
    return output
