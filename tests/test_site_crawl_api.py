import asyncio
import unittest
from unittest.mock import patch

import httpx
from pydantic import ValidationError

from app.main import app
from app.models import CrawlRequest, ScrapeTask


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
