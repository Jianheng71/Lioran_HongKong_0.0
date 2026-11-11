"""已锁定规格必须进入抓取，并且不能绕过确认。"""

import asyncio
import unittest
from unittest.mock import patch

import httpx
from openpyxl import load_workbook
from io import BytesIO

from app.clarify import store
from app.clarify_core import ClarifySession
from app.exporter import export_xlsx
from app.main import _crawl_jobs, _request_times, _tasks, app
from app.models import CrawlJob, ScrapeTask
from app.site_crawler import _page_cache, crawl_site
from app.spec_apply import apply_spec_to_records, shape_output


REQUIREMENT = (
    "政策法规库里所有文件的标题、发文字号、发文机关、成文日期、原文链接、效力状态"
)
REVIEW = "只要 2024 年以后的现行有效政策，别转发件，最多 20 条"
KEPT_TITLES = ["关于发布城市管理规定的通知", "关于印发管理办法的通知"]


def lock_session(url: str, requirement: str = REQUIREMENT, review: str = REVIEW):
    session = ClarifySession(url, requirement, review)
    while not session.is_ready():
        current = session.pending_group()
        session.submit({item["id"]: item["options"][0] for item in current["questions"]})
    spec = session.confirm()
    store.add(session)
    return session, spec


def _clear_runtime():
    _request_times.clear()
    _page_cache.clear()


def _policy_pages(root: str) -> dict[str, str]:
    list_url = root.rstrip("/") + "/policy/"
    items = [
        ("/doc/1", "关于印发管理办法的通知", "2024-06-01"),
        ("/doc/2", "某省人民政府转发国务院关于价格工作的通知", "2024-07-01"),
        ("/doc/3", "城市管理办法的政策解读", "2024-08-01"),
        ("/doc/4", "关于修改停车场条例的决定", "2023-05-01"),
        ("/doc/5", "关于发布城市管理规定的通知", "2025-01-15"),
        ("/doc/6", "国务院关于促进养老服务的意见", "2024-09-01"),
        ("/doc/7", "关于废止旧有招商办法的通知", "2024-04-01"),
        ("/doc/8", "某市人民政府发布的工作动态通报", "2024-03-01"),
    ]
    rows = "\n".join(
        f'<li><a href="{href}">{title}</a><time>{published}</time></li>'
        for href, title, published in items
    )
    return {
        root: (
            "<html><head><title>首页</title></head><body>"
            f'<nav><a href="{list_url}">政策法规</a></nav>'
            "<main><ul class=\"featured\">"
            "<li><a href=\"/featured/1\">Featured One</a></li>"
            "<li><a href=\"/featured/2\">Featured Two</a></li>"
            "<li><a href=\"/featured/3\">Featured Three</a></li>"
            "</ul></main></body></html>"
        ),
        list_url: (
            "<html><head><title>政策法规</title></head><body><main><h1>政策法规</h1><ul>"
            f"{rows}</ul></main></body></html>"
        ),
    }


def _map_records(_requirement, records):
    columns = ["标题", "原文链接", "成文日期", "摘要"]
    rows = [
        [
            item.get("title", ""),
            item.get("link", ""),
            item.get("published_at", ""),
            item.get("summary", ""),
        ]
        for item in records
    ]
    return columns, rows, []


class SpecGateTests(unittest.TestCase):
    def setUp(self):
        _clear_runtime()

    def tearDown(self):
        _clear_runtime()

    def test_crawl_and_scrape_reject_without_confirmed_spec(self):
        async def run():
            calls = []

            async def spy(*_args, **_kwargs):
                calls.append(True)
                raise AssertionError("没有锁定规格时不应该开始抓取")

            transport = httpx.ASGITransport(app=app)
            _request_times.clear()
            with (
                patch("app.main.crawl_site", side_effect=spy),
                patch("app.main.scrape", side_effect=spy),
            ):
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    _request_times.clear()
                    crawl = await client.post(
                        "/api/crawl",
                        json={
                            "url": "https://example.gov.cn/policy",
                            "requirement": REQUIREMENT,
                            "max_pages": 5,
                        },
                    )
                    _request_times.clear()
                    scrape = await client.post(
                        "/api/scrape",
                        json={
                            "url": "https://example.gov.cn/policy",
                            "requirement": REQUIREMENT,
                        },
                    )
            self.assertEqual(crawl.status_code, 422, crawl.text)
            self.assertEqual(scrape.status_code, 422, scrape.text)
            self.assertIn("没有已确认的可执行规格", crawl.json()["msg"])
            self.assertIn("没有已确认的可执行规格", scrape.json()["msg"])
            self.assertEqual(calls, [])

        asyncio.run(run())

    def test_changed_url_requirement_or_stale_spec_is_rejected(self):
        async def run():
            calls = []

            async def spy(*_args, **_kwargs):
                calls.append(True)
                raise AssertionError("规格不匹配时不应该开始抓取")

            _session, spec = lock_session("https://example.gov.cn/policy")
            pending = ClarifySession("https://example.gov.cn/policy", REQUIREMENT, REVIEW)
            store.add(pending)
            stale = [dict(item) for item in spec["spec"]]
            stale[0] = {**stale[0], "rule": stale[0]["rule"] + "（已过期）"}
            transport = httpx.ASGITransport(app=app)
            with patch("app.main.crawl_site", side_effect=spy):
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    payloads = {
                        "url": {
                            "url": "https://example.gov.cn/other",
                            "requirement": REQUIREMENT,
                            "max_pages": 5,
                            "session_id": spec["session_id"],
                            "spec": spec["spec"],
                        },
                        "requirement": {
                            "url": "https://example.gov.cn/policy",
                            "requirement": REQUIREMENT + "，再加一列",
                            "max_pages": 5,
                            "session_id": spec["session_id"],
                            "spec": spec["spec"],
                        },
                        "stale": {
                            "url": "https://example.gov.cn/policy",
                            "requirement": REQUIREMENT,
                            "max_pages": 5,
                            "session_id": spec["session_id"],
                            "spec": stale,
                        },
                        "unconfirmed": {
                            "url": "https://example.gov.cn/policy",
                            "requirement": REQUIREMENT,
                            "max_pages": 5,
                            "session_id": pending.session_id,
                            "spec": pending.rules() or spec["spec"],
                        },
                    }
                    results = {}
                    for name, payload in payloads.items():
                        _request_times.clear()
                        results[name] = await client.post("/api/crawl", json=payload)
            self.assertEqual(calls, [])
            for name, response in results.items():
                self.assertEqual(response.status_code, 422, f"{name}: {response.text}")
            self.assertIn("请重新澄清", results["url"].json()["msg"])
            self.assertIn("请重新澄清", results["requirement"].json()["msg"])
            self.assertIn("不一致", results["stale"].json()["msg"])
            self.assertIn("尚未全部确认", results["unconfirmed"].json()["msg"])

        asyncio.run(run())

    def test_confirm_does_not_start_crawl_or_scrape(self):
        async def run():
            calls = []

            async def spy(*_args, **_kwargs):
                calls.append(True)
                raise AssertionError("确认规格时不应该开始抓取")

            before_jobs = set(_crawl_jobs)
            before_tasks = set(_tasks)
            transport = httpx.ASGITransport(app=app)
            with (
                patch("app.clarify._interpret", return_value=None),
                patch("app.main.crawl_site", side_effect=spy),
                patch("app.main.scrape", side_effect=spy),
            ):
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    created = await client.post(
                        "/api/clarify",
                        json={
                            "url": "https://example.gov.cn/confirm-only",
                            "requirement": REQUIREMENT,
                            "review": REVIEW,
                        },
                    )
                    state = created.json()["data"]
                    self.assertFalse(state["can_scrape"])
                    for _ in range(12):
                        if state["status"] == "ready":
                            break
                        answers = {item["id"]: item["options"][0] for item in state["questions"]}
                        answered = await client.post(
                            f"/api/clarify/{state['session_id']}/answer",
                            json={"answers": answers},
                        )
                        self.assertEqual(answered.status_code, 200, answered.text)
                        state = answered.json()["data"]
                        self.assertFalse(state["can_scrape"])
                    confirmed = await client.post(f"/api/clarify/{state['session_id']}/confirm")
            self.assertEqual(confirmed.status_code, 200, confirmed.text)
            body = confirmed.json()["data"]
            self.assertTrue(body["ready_to_scrape"])
            self.assertNotIn("crawl_id", body)
            self.assertNotIn("task_id", body)
            self.assertIn("只产出可执行规格", body["note"])
            self.assertEqual(calls, [])
            self.assertEqual(set(_crawl_jobs), before_jobs)
            self.assertEqual(set(_tasks), before_tasks)

        asyncio.run(run())

    def test_desktop_flow_sends_locked_spec_and_crawl_is_allowed(self):
        async def run():
            seen = {}

            async def fake_crawl(job):
                seen["spec"] = job.locked_spec
                seen["url"] = job.url
                seen["requirement"] = job.requirement
                return ScrapeTask(
                    url=job.url,
                    requirement=job.requirement,
                    columns=["标题"],
                    rows=[["关于印发管理办法的通知"]],
                    schema={"template": "site_crawl"},
                    locked_spec=job.locked_spec,
                )

            transport = httpx.ASGITransport(app=app)
            with (
                patch("app.clarify._interpret", return_value=None),
                patch("app.main.ensure_public_url", side_effect=lambda url: str(url)),
                patch("app.main.crawl_site", side_effect=fake_crawl),
            ):
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    home = await client.get("/")
                    clarify = await client.get("/clarify")
                    app_js = (await client.get("/static/app.js")).text
                    clarify_js = (await client.get("/static/clarify.js")).text
                    self.assertEqual(home.status_code, 200)
                    self.assertIn('id="scrape-form"', home.text)
                    self.assertIn('id="clarify-hint"', home.text)
                    self.assertEqual(clarify.status_code, 200)
                    self.assertNotIn("/api/crawl", clarify.text)
                    self.assertNotIn("/api/crawl", clarify_js)
                    self.assertNotIn("/api/scrape", clarify_js)
                    gate = app_js.index("if (!scrapeReady())")
                    crawl_call = app_js.index("startCrawl(event)", gate)
                    self.assertLess(gate, crawl_call)
                    self.assertIn("window.location.assign(clarifyHref(formValues()))", app_js)
                    self.assertIn("session_id: locked.session_id", app_js)
                    self.assertIn("spec: locked.spec", app_js)

                    created = await client.post(
                        "/api/clarify",
                        json={
                            "url": "https://example.gov.cn/desktop",
                            "requirement": REQUIREMENT,
                            "review": REVIEW,
                        },
                    )
                    state = created.json()["data"]
                    for _ in range(12):
                        if state["status"] == "ready":
                            break
                        answers = {item["id"]: item["options"][0] for item in state["questions"]}
                        answered = await client.post(
                            f"/api/clarify/{state['session_id']}/answer",
                            json={"answers": answers},
                        )
                        state = answered.json()["data"]
                    before_jobs = set(_crawl_jobs)
                    before_tasks = set(_tasks)
                    confirmed = await client.post(f"/api/clarify/{state['session_id']}/confirm")
                    spec = confirmed.json()["data"]
                    self.assertEqual(set(_crawl_jobs), before_jobs)
                    self.assertEqual(set(_tasks), before_tasks)
                    self.assertEqual(seen, {})
                    _request_times.clear()
                    started = await client.post(
                        "/api/crawl",
                        json={
                            "url": spec["url"],
                            "requirement": spec["requirement"],
                            "max_pages": 5,
                            "session_id": spec["session_id"],
                            "spec": spec["spec"],
                        },
                    )
                    self.assertEqual(started.status_code, 200, started.text)
                    for _ in range(30):
                        if "spec" in seen:
                            break
                        await asyncio.sleep(0.01)
            self.assertEqual(
                [(item["id"], item["rule"]) for item in seen["spec"]],
                [(item["id"], item["rule"]) for item in spec["spec"]],
            )
            self.assertEqual(seen["url"], spec["url"])
            self.assertEqual(seen["requirement"], spec["requirement"])

        asyncio.run(run())

    def test_locked_spec_changes_what_the_crawler_keeps(self):
        async def run():
            root = "https://example.test/filter/"
            pages = _policy_pages(root)
            _session, spec = lock_session(root)

            def fake_fetch(url, _allowed_hosts):
                return pages[url], url

            bare = CrawlJob(url=root, requirement=REQUIREMENT, max_pages=5)
            locked = CrawlJob(
                url=root,
                requirement=REQUIREMENT,
                max_pages=5,
                locked_spec=spec["spec"],
            )
            with (
                patch("app.site_crawler._cached_fetch", side_effect=fake_fetch),
                patch("app.site_crawler.map_raw_fields", side_effect=_map_records),
            ):
                without = await crawl_site(bare)
                _page_cache.clear()
                with_spec = await crawl_site(locked)

            without_titles = [row[0] for row in without.rows]
            with_titles = [row[0] for row in with_spec.rows]
            self.assertIn("某省人民政府转发国务院关于价格工作的通知", without_titles)
            self.assertEqual(with_titles, KEPT_TITLES)
            self.assertNotIn("摘要", with_spec.columns)
            self.assertEqual(with_spec.columns, ["标题", "原文链接", "成文日期"])
            self.assertLess(len(with_titles), len(without_titles))
            reasons = {item["标题"]: item["淘汰原因"] for item in with_spec.schema["rejected"]}
            self.assertEqual(reasons["某省人民政府转发国务院关于价格工作的通知"], "转发件")
            self.assertEqual(reasons["城市管理办法的政策解读"], "非政策原文")
            self.assertEqual(reasons["关于修改停车场条例的决定"], "早于时间条件")
            self.assertEqual(reasons["国务院关于促进养老服务的意见"], "超出层级范围")
            self.assertEqual(reasons["关于废止旧有招商办法的通知"], "已废止或失效")
            self.assertEqual(reasons["某市人民政府发布的工作动态通报"], "文种不在范围内")
            self.assertEqual(
                [(item["id"], item["rule"]) for item in with_spec.schema["locked_spec"]],
                [(item["id"], item["rule"]) for item in spec["spec"]],
            )

            transport = httpx.ASGITransport(app=app)
            _request_times.clear()
            _page_cache.clear()
            with (
                patch("app.main.ensure_public_url", side_effect=lambda url: str(url)),
                patch("app.site_crawler._cached_fetch", side_effect=fake_fetch),
                patch("app.site_crawler.map_raw_fields", side_effect=_map_records),
            ):
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    created = await client.post(
                        "/api/crawl",
                        json={
                            "url": root,
                            "requirement": REQUIREMENT,
                            "max_pages": 5,
                            "session_id": spec["session_id"],
                            "spec": spec["spec"],
                        },
                    )
                    self.assertEqual(created.status_code, 200, created.text)
                    crawl_id = created.json()["data"]["crawl_id"]
                    status = None
                    for _ in range(50):
                        status = await client.get(f"/api/crawl/{crawl_id}")
                        if status.json()["data"]["status"] in {"completed", "stopped", "error"}:
                            break
                        await asyncio.sleep(0.01)
                    payload = status.json()["data"]
                    self.assertEqual(payload["status"], "completed", payload)
                    preview = await client.get("/api/preview", params={"task_id": payload["task_id"]})
            preview_rows = preview.json()["data"]["rows"]
            self.assertEqual([row[0] for row in preview_rows], KEPT_TITLES)
            self.assertEqual(preview.json()["data"]["columns"], ["标题", "原文链接", "成文日期"])

        asyncio.run(run())

    def test_locked_spec_changes_what_scrape_keeps(self):
        html = """
        <html><body><main><ul>
          <li><a href="https://example.gov.cn/policy/a">关于印发管理办法的通知</a><time>2024-06-01</time><p>正文甲</p></li>
          <li><a href="https://example.gov.cn/policy/b">某省人民政府转发国务院关于价格工作的通知</a><time>2024-07-01</time><p>正文乙</p></li>
          <li><a href="https://example.gov.cn/policy/c">城市管理办法的政策解读</a><time>2024-08-01</time><p>正文丙</p></li>
          <li><a href="https://example.gov.cn/policy/d">关于修改停车场条例的决定</a><time>2023-05-01</time><p>正文丁</p></li>
        </ul></main></body></html>
        """

        async def fake_understand(_url):
            return "政策列表", html

        def fake_fetch(url, _timeout, _force_stealth=False, allowed_hosts=None):
            from types import SimpleNamespace

            return SimpleNamespace(body=html.encode(), encoding="utf-8", url=url)

        async def fake_schema(*_args, **_kwargs):
            return {
                "base_selector": "li",
                "fields": [
                    {"name": "标题", "selector": "a", "type": "text"},
                    {"name": "原文链接", "selector": "a", "type": "attr:href"},
                    {"name": "成文日期", "selector": "time", "type": "text"},
                    {"name": "摘要", "selector": "p", "type": "text"},
                ],
            }

        async def run():
            _session, spec = lock_session("https://example.gov.cn/policy")
            transport = httpx.ASGITransport(app=app)
            _request_times.clear()
            with (
                patch("app.main.ensure_public_url", side_effect=lambda url: str(url)),
                patch("app.runner.check_robots", return_value=None),
                patch("app.runner.understand_page", side_effect=fake_understand),
                patch("app.runner.fetch_page", side_effect=fake_fetch),
                patch("app.runner.generate_schema", side_effect=fake_schema),
            ):
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    created = await client.post(
                        "/api/scrape",
                        json={
                            "url": "https://example.gov.cn/policy",
                            "requirement": REQUIREMENT,
                            "session_id": spec["session_id"],
                            "spec": spec["spec"],
                        },
                    )
            self.assertEqual(created.status_code, 200, created.text)
            data = created.json()["data"]
            self.assertEqual([row[0] for row in data["preview_rows"]], ["关于印发管理办法的通知"])
            self.assertEqual(data["columns"], ["标题", "原文链接", "成文日期"])
            self.assertEqual(data["total"], 1)
            self.assertGreaterEqual(data["schema"]["rejected_count"], 3)
            self.assertEqual(
                [(item["id"], item["rule"]) for item in data["schema"]["locked_spec"]],
                [(item["id"], item["rule"]) for item in spec["spec"]],
            )

        asyncio.run(run())

    def test_page_scope_changes_which_pages_are_fetched(self):
        async def run():
            root = "https://example.test/scope/"
            list_url = "https://example.test/scope/policy/"
            detail_url = "https://example.test/story/keep"
            list_html = """
            <html><head><title>政策法规</title></head><body><main><h1>政策法规</h1><ul>
              <li><a href="/story/keep">关于印发管理办法的通知</a></li>
              <li><a href="/story/rule">关于发布城市管理规定的通知</a><time>2024-02-02</time></li>
              <li><a href="/story/decision">关于修改停车场条例的决定</a><time>2024-03-03</time></li>
            </ul></main></body></html>
            """
            pages = {
                root: (
                    "<html><body><nav><a href=\"/scope/policy/\">政策法规</a></nav>"
                    "<main><ul class=\"featured\">"
                    "<li><a href=\"/featured/1\">Featured One</a></li>"
                    "<li><a href=\"/featured/2\">Featured Two</a></li>"
                    "<li><a href=\"/featured/3\">Featured Three</a></li>"
                    "</ul></main></body></html>"
                ),
                list_url: list_html,
                detail_url: (
                    "<html><body><main><h1>关于印发管理办法的通知</h1>"
                    "<p>正文</p><time>2024-06-01</time></main></body></html>"
                ),
                "https://example.test/story/rule": "<html><body><main><p>规定</p></main></body></html>",
                "https://example.test/story/decision": "<html><body><main><p>决定</p></main></body></html>",
            }

            def fake_fetch(url, _allowed_hosts):
                if url not in pages:
                    raise KeyError(url)
                return pages[url], url

            _session, spec = lock_session(root)
            detail_spec = [dict(item) for item in spec["spec"]]
            for item in detail_spec:
                if item["id"] == "page_scope":
                    item["rule"] = "抓取层级 = 列表页 + 每条原文详情页"
            with (
                patch("app.site_crawler._cached_fetch", side_effect=fake_fetch),
                patch("app.site_crawler.map_raw_fields", side_effect=_map_records),
            ):
                listed = await crawl_site(CrawlJob(
                    url=root,
                    requirement=REQUIREMENT,
                    max_pages=8,
                    locked_spec=spec["spec"],
                ))
                _page_cache.clear()
                detailed = await crawl_site(CrawlJob(
                    url=root,
                    requirement=REQUIREMENT,
                    max_pages=8,
                    locked_spec=detail_spec,
                ))
            self.assertEqual(listed.schema["pages_crawled"], 2)
            self.assertNotIn("关于印发管理办法的通知", [row[0] for row in listed.rows])
            self.assertGreater(detailed.schema["pages_crawled"], listed.schema["pages_crawled"])
            self.assertIn("关于印发管理办法的通知", [row[0] for row in detailed.rows])

        asyncio.run(run())

    def test_spec_limit_order_dedupe_and_no_guessing_change_output(self):
        _session, spec = lock_session("https://example.gov.cn/rules")
        rules = spec["spec"]
        records = [
            {
                "title": f"转发通知{index}",
                "published_at": "2024-06-01",
                "link": f"https://example.test/forward/{index}",
            }
            for index in range(20)
        ] + [
            {
                "title": f"关于管理办法的通知{index}",
                "published_at": f"2024-07-{index + 1:02d}",
                "link": f"https://example.test/keep/{index}",
            }
            for index in range(5)
        ]
        filtered_first, _rejected = apply_spec_to_records(records, rules)
        self.assertEqual(len(filtered_first), 5)
        limit_first = [dict(item) for item in rules]
        for item in limit_first:
            if item["id"] == "filter_then_limit":
                item["rule"] = "数量与筛选顺序 = 先取 20 再筛"
        taken_first, _rejected = apply_spec_to_records(records, limit_first)
        self.assertEqual(taken_first, [])

        duplicates = [
            {
                "title": "关于印发管理办法的通知 ×政发〔2024〕5号",
                "published_at": "2024-06-01",
                "link": "https://example.test/a",
            },
            {
                "title": "关于印发管理办法的通知 ×政发〔2024〕5号",
                "published_at": "2024-06-02",
                "link": "https://example.test/b",
            },
        ]
        deduped, _rejected = apply_spec_to_records(duplicates, rules)
        self.assertEqual(len(deduped), 1)

        columns, rows = shape_output(
            ["标题", "效力状态", "摘要"],
            [["关于印发管理办法的通知", "现行（推断）", "正文"]],
            rules,
        )
        self.assertEqual(columns, ["标题", "效力状态"])
        self.assertEqual(rows, [["关于印发管理办法的通知", ""]])

        task = ScrapeTask(
            url="https://example.gov.cn/rules",
            requirement=REQUIREMENT,
            columns=["标题"],
            rows=[["关于印发管理办法的通知"]],
            schema={
                "rejected": [
                    {"标题": "转发通知", "链接": "https://example.test/forward/0", "淘汰原因": "转发件"}
                ]
            },
        )
        workbook = load_workbook(BytesIO(export_xlsx(task).getvalue()))
        self.assertEqual(workbook.sheetnames, ["Lioran", "淘汰记录"])
        self.assertEqual(workbook["淘汰记录"]["A2"].value, "转发通知")
        plain = ScrapeTask(
            url="https://example.gov.cn/rules",
            requirement=REQUIREMENT,
            columns=["标题"],
            rows=[["关于印发管理办法的通知"]],
            schema={},
        )
        plain_book = load_workbook(BytesIO(export_xlsx(plain).getvalue()))
        self.assertEqual(plain_book.sheetnames, ["Lioran"])


if __name__ == "__main__":
    unittest.main()
