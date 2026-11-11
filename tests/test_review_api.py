import asyncio
from datetime import datetime, timezone
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import httpx

from app.main import app, _store_task
from app.models import ScrapeTask
from app import review_store


class ReviewApiTests(unittest.TestCase):
    def test_saved_review_can_be_loaded_corrected_and_exported(self):
        async def run_test():
            with tempfile.TemporaryDirectory() as temp_dir:
                task_id = str(uuid4())
                review_id = str(uuid4())
                record = {
                    "review_id": review_id,
                    "title": "住房保障办法",
                    "link": "https://example.test/policy/1",
                    "published_at": "",
                    "section": "政策文件",
                    "category": "办法",
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    "evidence": "原文证据。",
                    "status_text": "",
                    "effective_date_str": "",
                    "expiry_date_str": "",
                    "effective_date": "",
                    "expiry_date": "",
                    "decision": "manual_review",
                    "lifecycle_status": "待人工复核",
                    "risk_level": "中",
                    "reason": "状态不明确",
                    "review_required": True,
                    "manual_override": False,
                    "manual_decision_note": "",
                    "extracted_values": {
                        "序号": "1",
                        "标题": "住房保障办法",
                        "链接": "https://example.test/policy/1",
                    },
                }
                task = ScrapeTask(
                    task_id=task_id,
                    url="https://example.test/",
                    requirement="审查住房政策",
                    columns=["序号", "标题", "链接"],
                    rows=[],
                    schema={"pages_crawled": 1, "sections_crawled": 1},
                    review_enabled=True,
                    review_time=True,
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
                with patch.object(
                    review_store,
                    "database_path",
                    return_value=Path(temp_dir) / "lioran.sqlite3",
                ):
                    _store_task(task)
                    transport = httpx.ASGITransport(app=app)
                    async with httpx.AsyncClient(
                        transport=transport,
                        base_url="http://testserver",
                    ) as client:
                        manual = await client.get(
                            "/api/review/items",
                            params={"task_id": task_id, "decision": "needs_review"},
                        )
                        self.assertEqual(manual.status_code, 200)
                        self.assertEqual(len(manual.json()["data"]["items"]), 1)

                        correction = await client.patch(
                            f"/api/review/items/{review_id}",
                            json={"decision": "included", "note": "人工确认有效"},
                        )
                        self.assertEqual(correction.status_code, 200)
                        preview = await client.get(
                            "/api/preview",
                            params={"task_id": task_id},
                        )
                        self.assertEqual(
                            preview.json()["data"]["rows"],
                            [["1", "住房保障办法", "https://example.test/policy/1"]],
                        )
                        workbook = await client.get(
                            "/api/download",
                            params={"task_id": task_id},
                        )
                        self.assertEqual(workbook.status_code, 200)
                        self.assertIn(
                            "spreadsheetml",
                            workbook.headers["content-type"],
                        )

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
