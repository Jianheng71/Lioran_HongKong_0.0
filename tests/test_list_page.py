import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.cleaner import build_html_skeleton, clean_html
from app.local_llm import map_raw_fields
from app.models import CrawlJob
from app.site_crawler import _should_queue, analyze_page, crawl_site


LIST_PAGE = """
<html><body><nav>navigation</nav><main>
  <div class="news-list">
    <article class="news-card"><h2><a href="/news/1">Title one</a></h2><time>Today</time></article>
    <article class="news-card"><h2><a href="/news/2">Title two</a></h2><time>Yesterday</time></article>
    <article class="news-card"><h2><a href="/news/3">Title three</a></h2><time>Monday</time></article>
    <article class="news-card"><h2><a href="/news/4">Title four</a></h2><time>Tuesday</time></article>
  </div>
</main><footer>footer</footer></body></html>
"""

GENERIC_LIST = """
<html><head><title>News - Example</title></head><body>
  <nav><ul><li><a href="/news/">News</a></li><li><a href="/login">Log in</a></li></ul></nav>
  <main><h1>Latest News</h1><ul class="news-list">
    <li><a href="/news/story-1">Story One</a><time datetime="2026-11-10">Nov 10, 2026</time><p>First summary.</p></li>
    <li><a href="/news/story-2">Story Two</a><time>2026-11-09</time><p>Second summary.</p></li>
    <li><a href="/news/story-3">Story Three</a><p>Third summary.</p></li>
  </ul></main>
  <footer><ul><li><a href="/footer/1">Footer One</a></li><li><a href="/footer/2">Footer Two</a></li><li><a href="/footer/3">Footer Three</a></li></ul></footer>
  <a href="https://other.example/">External link</a>
</body></html>
"""


class ListPageTests(unittest.TestCase):
    def test_skeleton_keeps_three_real_repeated_cards(self):
        skeleton = build_html_skeleton(clean_html(LIST_PAGE))
        self.assertEqual(skeleton.count('class="news-card"'), 3)
        self.assertIn("<h2>", skeleton)
        self.assertIn("<time", skeleton)
        self.assertNotIn("navigation", skeleton)
        self.assertNotIn("Title one", skeleton)

    def test_generic_list_extraction_skips_chrome_and_keeps_raw_materials(self):
        page = analyze_page("https://example.test/", GENERIC_LIST, "News")

        self.assertEqual(page.section, "News")
        self.assertEqual([record.title for record in page.records], [
            "Story One", "Story Two", "Story Three",
        ])
        self.assertEqual(page.records[0].published_at, "2026-11-10")
        self.assertIn("First summary", page.records[0].summary)
        self.assertEqual(page.records[2].category, "新闻（推断）")
        self.assertEqual([label for _, label in page.links], ["News"])

    def test_shallow_section_links_are_discovered_but_not_exported_as_records(self):
        source = """
        <html><body><main><h1>News</h1>
          <ul class="quick-links">
            <li><a href="/home">Home</a></li>
            <li><a href="/sport">Sport</a></li>
            <li><a href="/weather">Weather</a></li>
            <li><a href="/world/sport/roundup">Sport</a></li>
          </ul>
          <ul class="stories">
            <li><a href="/news/story-1">Story One</a></li>
            <li><a href="/news/story-2">Story Two</a></li>
            <li><a href="/news/story-3">Story Three</a></li>
          </ul>
        </main></body></html>
        """
        page = analyze_page("https://example.test/", source, "News")

        self.assertEqual([record.title for record in page.records], [
            "Story One", "Story Two", "Story Three",
        ])
        self.assertIn(("https://example.test/sport", "Sport"), page.links)

    def test_title_and_relative_time_are_separated_from_card_metadata(self):
        source = """
        <html><body><main><h1>News</h1><ul class="stories">
          <li><a href="/news/articles/story-1"><h2>Story One</h2>
            <time>15 mins ago</time><span>World</span></a></li>
          <li><a href="/news/articles/story-2"><h2>Story Two</h2>
            <time>2 hours ago</time><span>Asia</span></a></li>
          <li><a href="/news/articles/story-3"><h2>Story Three</h2>
            <time>Yesterday</time><span>Business</span></a></li>
        </ul></main></body></html>
        """
        page = analyze_page("https://example.test/news/", source, "News")

        self.assertEqual(page.records[0].title, "Story One")
        self.assertEqual(page.records[0].published_at, "15 mins ago")

    def test_queue_keeps_sections_and_pagination_but_skips_article_details(self):
        current = "https://example.test/news/"
        self.assertTrue(_should_queue("https://example.test/news/world/", "World News", current))
        self.assertTrue(_should_queue("https://example.test/news/?page=2", "Next page", current))
        self.assertFalse(
            _should_queue(
                "https://example.test/news/articles/story-1",
                "News story about policy",
                current,
            )
        )
        self.assertFalse(
            _should_queue(
                "https://example.test/news/2026/11/story.shtml",
                "Latest news story",
                current,
            )
        )

    def test_local_ai_mapping_preserves_requested_columns(self):
        answer = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=(
                            '{"fields":['
                            '{"name":"序号","source":"sequence"},'
                            '{"name":"标题","source":"title"},'
                            '{"name":"链接","source":"link"},'
                            '{"name":"栏目名称","source":"section"},'
                            '{"name":"类别","source":"category"}]}'
                        )
                    )
                )
            ]
        )
        record = {
            "title": "关于绿色发展的意见",
            "link": "https://example.test/policy/1",
            "published_at": "",
            "summary": "",
            "section": "政策",
            "category": "意见（推断）",
            "source_url": "https://example.test/policy/",
        }
        with patch("litellm.completion", return_value=answer):
            columns, rows, mapping = map_raw_fields(
                "我要序号、标题、链接、栏目名称、类别",
                [record],
            )

        self.assertEqual(columns, ["序号", "标题", "链接", "栏目名称", "类别"])
        self.assertEqual(rows[0], [
            "1",
            record["title"],
            record["link"],
            "政策",
            "意见（推断）",
        ])
        self.assertEqual(len(mapping), 5)

    def test_local_ai_mapping_keeps_custom_requested_columns(self):
        answer = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=(
                            '{"fields":['
                            '{"name":"标题","source":"title"},'
                            '{"name":"作者","source":"inferred"},'
                            '{"name":"链接","source":"link"}]}'
                        )
                    )
                )
            ]
        )
        record = {
            "title": "A story",
            "link": "https://example.test/news/story-1",
            "published_at": "",
            "summary": "",
            "section": "News",
            "category": "",
            "source_url": "https://example.test/news/",
        }
        with patch("litellm.completion", return_value=answer):
            columns, rows, _ = map_raw_fields(
                "输出标题、作者和链接",
                [record],
            )

        self.assertEqual(columns, ["标题", "作者", "链接"])
        self.assertEqual(rows[0], [
            "A story",
            "未提取到（推断）",
            record["link"],
        ])

    def test_bounded_bfs_crawls_sections_and_pagination_and_deduplicates(self):
        root_url = "https://example.test/"
        news_url = "https://example.test/news/"
        feature_url = "https://example.test/feature/"
        page_two_url = "https://example.test/news/?page=2"
        root_html = """
        <html><head><title>Example</title></head><body>
          <nav><a href="/news/">News</a><a href="/feature/">Featured News</a>
          <a href="/account/login">Log in</a>
          <a href="https://external.test/news">External</a></nav>
          <main><h1>Home</h1><ul class="featured">
            <li><a href="/featured/1">Featured One</a></li>
            <li><a href="/featured/2">Featured Two</a></li>
            <li><a href="/featured/3">Featured Three</a></li>
          </ul></main>
        </body></html>
        """
        feature_html = """
        <html><head><title>Feature</title></head><body><main><h1>Feature</h1>
          <p>One detail link: <a href="/feature/more-list/">More news</a></p>
        </main></body></html>
        """
        news_html = """
        <html><head><title>News</title></head><body><main><h1>News</h1>
          <ul><li><a href="/story/1">Story One</a><time>2026-11-10</time></li>
          <li><a href="/story/2">Story Two</a></li>
          <li><a href="/story/3">Story Three</a></li></ul>
          <a href="/news/?page=2">Next page</a>
        </main></body></html>
        """
        page_two_html = """
        <html><head><title>News page 2</title></head><body><main><h1>News</h1>
          <ul><li><a href="/story/4">Story Four</a></li>
          <li><a href="/story/5">Story Five</a></li>
          <li><a href="/story/6">Story Six</a></li></ul>
        </main></body></html>
        """
        pages = {
            root_url: root_html,
            news_url: news_html,
            feature_url: feature_html,
            page_two_url: page_two_html,
        }

        def fake_fetch(url, _allowed_hosts):
            return pages[url], url

        def fake_map(_requirement, records):
            return ["序号", "标题", "链接"], [
                [str(index), item["title"], item["link"]]
                for index, item in enumerate(records, 1)
            ], []

        job = CrawlJob(
            url=root_url,
            requirement="我要序号、标题、链接",
            max_pages=5,
        )
        with (
            patch("app.site_crawler._cached_fetch", side_effect=fake_fetch),
            patch("app.site_crawler.map_raw_fields", side_effect=fake_map),
        ):
            task = asyncio.run(crawl_site(job))

        self.assertEqual(job.pages_crawled, 4)
        self.assertEqual(job.rows_count, 6)
        self.assertEqual(task.total, 6)
        self.assertEqual(task.rows[0][0], "1")
        self.assertEqual(task.rows[0][1], "Story One")
        self.assertEqual(task.rows[-1][1], "Story Six")
        self.assertEqual(task.schema["sections_crawled"], 2)


if __name__ == "__main__":
    unittest.main()
