# Lioran architecture

## Request flow

1. FastAPI validates a single public HTTP(S) URL and applies a per-IP request limit.
2. The fetcher checks the site's `robots.txt`; Crawl4AI loads the page once and returns Markdown plus cleaned HTML.
3. The cleaner builds an HTML skeleton from up to three repeated cards. Crawl4AI's `JsonCssExtractionStrategy.generate_schema(html=...)` asks local Ollama/Hermes for CSS selectors; the Markdown is included in the query for semantic context.
4. Scrapling fetches the page and the generated base/field selectors are checked against the actual response. The app extracts, normalizes, and deduplicates rows.
5. Results are held in memory under a task ID. Preview returns at most five rows; download creates an `.xlsx` file with pandas/openpyxl.

## Boundaries

- One page per task; `max_pages` is constrained to one.
- Only public HTTP(S) hosts and standard web ports are accepted.
- CAPTCHA, Cloudflare challenges, login walls, and paywalls are reported without bypass attempts.
- API JSON uses `{code, msg, data}` envelopes; the XLSX success response is a file stream.
- The task store and rate limiter are process-local. A multi-worker or multi-host deployment would need shared storage and shared rate limiting; that is intentionally outside this MVP.
