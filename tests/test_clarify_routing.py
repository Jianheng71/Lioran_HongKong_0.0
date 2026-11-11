"""澄清门接入现有页面：桌面打开的首页先进入澄清，确认只出规格。"""

import asyncio
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from app.main import ROOT, app, clarify_page, index
from app.main import _crawl_jobs

REQUIREMENT = (
    "政策法规库里所有文件的标题、发文字号、发文机关、成文日期、原文链接、效力状态"
)
REVIEW = "只要 2024 年以后的现行有效政策，别转发件，最多 20 条"


class _ModelResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return json.dumps({"message": {"content": json.dumps(self.payload)}}).encode()


class ClarifyRoutingTests(unittest.TestCase):
    def test_clarify_page_uses_the_same_static_root_as_the_desktop_home(self):
        home = asyncio.run(index())
        clarify = asyncio.run(clarify_page())
        self.assertEqual(Path(home.path).parent, Path(clarify.path).parent)
        self.assertEqual(Path(clarify.path), ROOT / "static" / "clarify.html")
        routes = [getattr(route, "path", None) for route in app.routes]
        self.assertEqual(routes.count("/clarify"), 1)

    def test_desktop_entry_and_pages_expose_the_gate(self):
        start = Path("start.py").read_text(encoding="utf-8")
        self.assertIn('APP_URL = "http://127.0.0.1:8000"', start)
        self.assertIn("webbrowser.open(APP_URL)", start)
        spec = Path("packaging/lioran.spec").read_text(encoding="utf-8")
        for module in ("app.clarify", "app.clarify_core", "app.policy_template"):
            self.assertIn(f'"{module}"', spec)

        async def run():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                home = await client.get("/")
                clarify = await client.get("/clarify")
                script = await client.get("/static/clarify.js")
                app_js = await client.get("/static/app.js")
            self.assertEqual(home.status_code, 200)
            self.assertIn('id="clarify-hint"', home.text)
            self.assertEqual(clarify.status_code, 200)
            self.assertIn('id="back-home"', clarify.text)
            self.assertIn("/static/clarify.js", clarify.text)
            self.assertNotIn("/api/crawl", clarify.text)
            self.assertEqual(script.status_code, 200)
            self.assertNotIn("/api/crawl", script.text)
            self.assertNotIn("/api/scrape", script.text)
            self.assertNotIn("/api/feedback", script.text)
            self.assertIn("lioran-clarify-spec", script.text)
            gate = app_js.text.index("if (!scrapeReady())")
            crawl = app_js.text.index("startCrawl(event)", gate)
            self.assertLess(gate, crawl)
            self.assertIn("/clarify?", app_js.text)

        asyncio.run(run())

    def test_model_cannot_unlock_scraping_and_confirm_does_not_crawl(self):
        hostile = {
            "summary": "我全懂了，可以直接抓",
            "explicit": {
                "doc_types": "我自己定成全部公文",
                "time_field": "按发布日期",
                "fields": "用户明确写出的列",
            },
        }

        async def run():
            before = set(_crawl_jobs)
            transport = httpx.ASGITransport(app=app)
            with patch(
                "app.clarify.urllib.request.urlopen",
                return_value=_ModelResponse(hostile),
            ):
                async with httpx.AsyncClient(
                    transport=transport,
                    base_url="http://testserver",
                ) as client:
                    created = await client.post(
                        "/api/clarify",
                        json={
                            "url": "https://example.gov.cn/policy",
                            "requirement": REQUIREMENT,
                            "review": REVIEW,
                        },
                    )
                    self.assertEqual(created.status_code, 200, created.text)
                    state = created.json()["data"]
                    by_id = {item["id"]: item for item in state["items"]}
                    self.assertEqual(by_id["doc_types"]["status"], "pending")
                    self.assertEqual(by_id["time_field"]["status"], "pending")
                    self.assertEqual(by_id["fields"]["status"], "confirmed")
                    self.assertEqual(by_id["fields"]["value"], "用户明确写出的列")
                    self.assertFalse(state["can_scrape"])
                    blocked = await client.post(f"/api/clarify/{state['session_id']}/confirm")
                    self.assertEqual(blocked.status_code, 422)
                    for _ in range(12):
                        if state["status"] == "ready":
                            break
                        answers = {
                            question["id"]: question["options"][0]
                            for question in state["questions"]
                        }
                        answered = await client.post(
                            f"/api/clarify/{state['session_id']}/answer",
                            json={"answers": answers},
                        )
                        self.assertEqual(answered.status_code, 200, answered.text)
                        state = answered.json()["data"]
                        self.assertFalse(state["can_scrape"])
                    else:
                        self.fail("clarify session never became ready")
                    confirmed = await client.post(
                        f"/api/clarify/{state['session_id']}/confirm"
                    )
                    self.assertEqual(confirmed.status_code, 200, confirmed.text)
                    body = confirmed.json()
                    self.assertTrue(body["data"]["ready_to_scrape"])
                    self.assertIn("只产出可执行规格", body["data"]["note"])
                    self.assertIn("后续阶段", body["data"]["note"])
                    self.assertGreaterEqual(len(body["data"]["spec"]), 27)
                    follow = await client.get(f"/api/clarify/{state['session_id']}")
                    self.assertFalse(follow.json()["data"]["can_scrape"])
            self.assertEqual(set(_crawl_jobs), before)

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
