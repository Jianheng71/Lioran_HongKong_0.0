from datetime import datetime, timezone
from io import BytesIO
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import load_workbook

from app import review_store
from app.exporter import export_xlsx
from app.models import ScrapeTask


def _task() -> ScrapeTask:
    record = {
        "review_id": "review-1",
        "title": "住房保障办法",
        "link": "https://example.test/policy/1",
        "section": "政策文件",
        "category": "办法",
        "decision": "manual_review",
        "lifecycle_status": "待人工复核",
        "status_text": "",
        "effective_date": "",
        "effective_date_str": "",
        "expiry_date": "",
        "expiry_date_str": "",
        "reason": "状态不明确",
        "risk_level": "中",
        "evidence": "原文证据。",
        "captured_at": "2026-11-10T12:00:00+08:00",
        "extracted_values": {
            "序号": "1",
            "标题": "住房保障办法",
            "链接": "https://example.test/policy/1",
        },
        "review_required": True,
        "manual_override": False,
        "manual_decision_note": "",
    }
    return ScrapeTask(
        task_id="task-1",
        url="https://example.test/",
        requirement="审查住房政策",
        columns=["序号", "标题", "链接"],
        rows=[],
        schema={"pages_crawled": 4, "sections_crawled": 2},
        created_at=datetime(2026, 11, 10, tzinfo=timezone.utc),
        review_enabled=True,
        review_time=True,
        deep_review=True,
        review_records=[record],
        review_summary={
            "total": 1,
            "included": 0,
            "excluded": 0,
            "future": 0,
            "manual_review": 1,
            "needs_review": 1,
        },
    )


class ReviewStorageExportTests(unittest.TestCase):
    def test_review_extraction_cache_reuses_exact_and_near_duplicate_text(self):
        first = {
            "title": "住房租金管理办法",
            "content": (
                "本办法规定住房租金补贴的申请条件、标准和办理流程。"
                "具体细则由主管部门另行制定。"
            ),
        }
        near_duplicate = {
            "title": "住房租金管理办法",
            "content": (
                "本办法规定住房租金补贴的申请条件、标准和办理流程。"
                "相关细则由主管部门后续制定。"
            ),
        }
        extraction = {
            "index": 0,
            "title": first["title"],
            "link": "https://example.test/1",
            "is_wanted": True,
            "is_policy": True,
            "is_effective": True,
            "status_text": "现行有效",
            "effective_date_str": "",
            "expiry_date_str": "",
            "reason": "住房租金政策",
            "risk_level": "低",
            "evidence": "本办法规定住房租金补贴的申请条件、标准和办理流程。",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "lioran.sqlite3"
            with patch.object(review_store, "database_path", return_value=path):
                review_store.save_cached_extractions("intent-housing", [first], {0: extraction})
                exact = review_store.get_cached_extractions("intent-housing", [first])
                similar = review_store.get_cached_extractions(
                    "intent-housing",
                    [near_duplicate],
                )
                unrelated_intent = review_store.get_cached_extractions(
                    "intent-environment",
                    [first],
                )

        self.assertEqual(exact[0]["evidence"], extraction["evidence"])
        self.assertEqual(similar[0]["evidence"], extraction["evidence"])
        self.assertEqual(unrelated_intent, {})

    def test_review_records_persist_and_manual_corrections_survive_reload(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "lioran.sqlite3"
            with patch.object(review_store, "database_path", return_value=path):
                task = _task()
                review_store.save_task(task)
                updated = review_store.update_review_item(
                    "review-1",
                    "included",
                    "人工确认有效",
                )
                loaded = review_store.load_task("task-1")
                saved_tasks = review_store.list_review_tasks()

        self.assertEqual(updated["task_id"], "task-1")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.review_records[0]["decision"], "included")
        self.assertTrue(loaded.review_records[0]["manual_override"])
        self.assertEqual(saved_tasks[0]["total"], 1)

    def test_compliance_export_contains_classification_sheets_and_widths(self):
        workbook = load_workbook(BytesIO(export_xlsx(_task()).getvalue()))

        self.assertEqual(
            workbook.sheetnames,
            ["汇总", "有效保留", "排除", "待生效", "待人工复核"],
        )
        self.assertEqual(workbook["汇总"]["B4"].value, 4)
        self.assertEqual(workbook["待人工复核"]["B1"].value, "标题")
        self.assertEqual(workbook["待人工复核"].column_dimensions["A"].width, 8)
        self.assertEqual(workbook["待人工复核"].column_dimensions["C"].width, 80)


if __name__ == "__main__":
    unittest.main()
