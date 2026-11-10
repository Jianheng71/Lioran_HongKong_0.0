import unittest

from app.cleaner import build_html_skeleton, clean_html


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


class ListPageTests(unittest.TestCase):
    def test_skeleton_keeps_three_real_repeated_cards(self):
        skeleton = build_html_skeleton(clean_html(LIST_PAGE))
        self.assertEqual(skeleton.count('class="news-card"'), 3)
        self.assertIn("<h2>", skeleton)
        self.assertIn("<time", skeleton)
        self.assertNotIn("navigation", skeleton)
        self.assertNotIn("Title one", skeleton)


if __name__ == "__main__":
    unittest.main()
