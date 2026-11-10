import unittest
from unittest.mock import patch

from app.fetcher import fetch_page


class FetcherTests(unittest.TestCase):
    def test_browser_fallback_preserves_site_host_allowlist(self):
        response = type(
            "Response",
            (),
            {"body": b"<html>short page</html>", "status": 200, "url": "https://example.test/"},
        )()
        allowed_hosts = {"example.test", "www.example.test"}

        with (
            patch("app.fetcher.ensure_public_url", side_effect=lambda url: url),
            patch("app.fetcher.Fetcher.get", return_value=response),
            patch("app.fetcher._fetch_stealthy", return_value=response) as browser_fetch,
        ):
            result = fetch_page(
                "https://example.test/",
                timeout=10,
                allowed_hosts=allowed_hosts,
            )

        self.assertIs(result, response)
        browser_fetch.assert_called_once_with(
            "https://example.test/",
            10,
            allowed_hosts,
        )


if __name__ == "__main__":
    unittest.main()
