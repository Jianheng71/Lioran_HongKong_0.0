# Lioran

Lioran is a local, no-code web data extraction tool. Paste a public webpage URL, describe the data you need in one sentence, preview the results, and export them to Excel.

> **Disclaimer:** For public data only. Follow the target website's terms of service, robots.txt, and applicable laws. Lioran does not attempt to bypass logins, paywalls, CAPTCHAs, or security challenges.

## Preview

<!-- TODO: Add an application screenshot -->

## Run locally (3 steps)

You need Python 3.11 or newer, [Ollama](https://ollama.com/), and Chromium.

```bash
# 1. Install dependencies and the browser
git clone https://github.com/Jianheng71/Lioran_HongKong_0.0.git
cd Lioran_HongKong_0.0
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
patchright install chromium

# 2. Prepare the local model
ollama pull hermes3:8b
# Ensure Ollama is running; if needed, start `ollama serve` in another terminal

# 3. Start the application
cp .env.example .env
python -m app.main
```

Open <http://localhost:8000>. Ollama must be running locally. Page understanding, rule generation, and data processing run locally without paid AI APIs; the app only makes network requests to the public webpage requested by the user.

## Docker

Start Ollama on the host, then run:

```bash
docker compose up --build
```

Open <http://localhost:8000>. Docker Compose connects to host Ollama at `host.docker.internal:11434`; Chromium is installed during the first build.

## Stack and workflow

- **Crawl4AI** reads one page, produces Markdown, and generates CSS rules through `JsonCssExtractionStrategy.generate_schema(html=...)` from a compact HTML skeleton.
- **Hermes 3 8B / Ollama** provides local inference. Markdown conveys page semantics; the skeleton contains at most three repeated cards with tags and classes. Selectors must exist in the skeleton.
- **Scrapling** extracts data with validated CSS rules and can fall back from fast HTTP fetching to its Patchright-based browser fetcher.
- **FastAPI + vanilla HTML/CSS/JavaScript** serves the single-page interface, previews, and Excel downloads. There is no login, user system, or pagination.

Each task currently scrapes one public page. Results are held in process memory and expire after one hour by default.

## Configuration

Copy `.env.example` to `.env` to adjust the Ollama URL, model, retries, and timeouts. The default model is `hermes3:8b`; pull it through Ollama first.

## Tests

```bash
python -m unittest discover -s tests -v
```

`test_hermes_json.py` connects to local Ollama and generates a schema ten times; it is skipped when Ollama is unavailable. The list/detail tests cover HTML skeleton and value-cleaning behavior without pretending to perform a live scrape. Live-site tests should use public pages you are authorized to access and that permit automated fetching.

## License

This project is released under the MIT License. Crawl4AI is Apache-2.0; observe the licenses of all dependencies.
