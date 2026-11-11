import asyncio
import unittest
from unittest.mock import patch

import httpx
from pydantic import ValidationError

from app.clarify import store
from app.clarify_core import ClarifySession
from app.main import _request_times, app
from app.models import CrawlRequest, ScrapeTask


def _lock_spec(url: str, requirement: str) -> dict:
    session = ClarifySession(
        url,
        requirement,
        "只要 2024 年以后的现行有效政策，别转发件，最多 20 条",
    )
    while not session.is_ready():
        current = session.pending_group()
        session.submit({item["id"]: item["options"][0] for item in current["questions"]})
    spec = session.confirm()
    store.add(session)
    return spec


class SiteCrawlApiTests(unittest.TestCase):
    def test_page_limit_is_bounded_to_five_hundred(self):
        with self.assertRaises(ValidationError):
            CrawlRequest(
                url="https://example.test/",
                requirement="title and link",
                max_pages=501,
            )

    def test_background_crawl_can_be_stopped_and_returns_partial_result(self):
        async def run_test():
            async def waiting_crawl(job):
                job.status = "running"
                job.pages_crawled = 1
                job.current_section = "News"
                while not job.stop_requested:
                    await asyncio.sleep(0.005)
                job.status = "stopped"
                return ScrapeTask(
                    url=job.url,
                    requirement=job.requirement,
                    columns=["序号", "标题"],
                    rows=[["1", "已抓到的标题"]],
                    schema={"template": "site_crawl"},
                )

            transport = httpx.ASGITransport(app=app)
            locked = _lock_spec("https://example.test/", "title and link")
            _request_times.clear()
            with (
                patch("app.main.ensure_public_url", side_effect=lambda url: str(url)),
                patch("app.main.crawl_site", side_effect=waiting_crawl),
            ):
                async with httpx.AsyncClient(
                    transport=transport,
                    base_url="http://testserver",
                ) as client:
                    created = await client.post(
                        "/api/crawl",
                        json={
                            "url": "https://example.test/",
                            "requirement": "title and link",
                            "max_pages": 10,
                            "session_id": locked["session_id"],
                            "spec": locked["spec"],
                        },
                    )
                    self.assertEqual(created.status_code, 200)
                    crawl_id = created.json()["data"]["crawl_id"]
                    await asyncio.sleep(0.02)
                    stopped = await client.post(f"/api/crawl/{crawl_id}/stop")
                    self.assertEqual(stopped.status_code, 200)
                    for _ in range(20):
                        status = await client.get(f"/api/crawl/{crawl_id}")
                        if status.json()["data"]["status"] == "stopped":
                            break
                        await asyncio.sleep(0.01)
                    result = status.json()["data"]
                    self.assertEqual(result["status"], "stopped")
                    self.assertIsNotNone(result["task_id"])
                    preview = await client.get(
                        "/api/preview",
                        params={"task_id": result["task_id"]},
                    )
                    self.assertEqual(preview.json()["data"]["rows"], [["1", "已抓到的标题"]])

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
