import asyncio
import unittest
from urllib.request import urlopen

SAMPLE_MARKDOWN = """# Latest news
- First story — 10 Nov 2026
- Second story — 9 Nov 2026
- Third story — 8 Nov 2026
"""
SAMPLE_HTML = """
<div class="news-list">
  <article class="news-card"><h2><a href="">First story</a></h2><time></time></article>
  <article class="news-card"><h2><a href="">Second story</a></h2><time></time></article>
  <article class="news-card"><h2><a href="">Third story</a></h2><time></time></article>
</div>
"""


class HermesJsonTests(unittest.TestCase):
    def test_same_page_produces_valid_json_at_least_eight_times(self):
        try:
            from app.config import settings
            from app.local_llm import normalize_schema
            from app.understander import generate_schema
        except ModuleNotFoundError as error:
            self.skipTest(f"请先安装项目依赖：{error.name}")
        try:
            with urlopen(f"{settings.ollama_base_url}/api/tags", timeout=2):
                pass
        except OSError:
            self.skipTest("本地 Ollama 未运行")

        valid = 0
        for _ in range(10):
            try:
                schema = asyncio.run(
                    generate_schema(
                        SAMPLE_MARKDOWN,
                        SAMPLE_HTML,
                        "提取每条新闻的标题、日期和链接",
                    )
                )
                normalize_schema(schema)
                valid += 1
            except Exception:
                continue
        self.assertGreaterEqual(valid, 8, f"10 次生成中只有 {valid} 次有效")


if __name__ == "__main__":
    unittest.main()
