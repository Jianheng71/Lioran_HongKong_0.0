# Lioran

Extract data from a public webpage with a natural-language request and export it to Excel. Processing uses Scrapling, Crawl4AI, and the local Hermes 3 8B model through Ollama; no paid AI API is used.

## Get started

1. Download the installer for your computer:
   - [Windows x64 — LioranSetup.exe](https://github.com/Jianheng71/Lioran_HongKong_0.0/releases/download/v0.1.0-build.7/LioranSetup.exe)
   - [macOS Apple Silicon — Lioran.dmg](https://github.com/Jianheng71/Lioran_HongKong_0.0/releases/download/v0.1.0-build.7/Lioran.dmg)
2. Run the installer and follow its prompts. On macOS, open the DMG and run `Lioran.pkg`.
3. Double-click the **Lioran** desktop icon. The first launch downloads Hermes 3 8B (about 4.7 GB) and the Chromium browsers, starts the local app, and opens it in your browser. Ollama must be installed; if it is missing, Lioran opens the Ollama download page.

These are unsigned preview builds. Windows SmartScreen or macOS Gatekeeper may show a security warning.

For public webpages only. Respect each site's terms of service and `robots.txt`. Lioran does not bypass logins, paywalls, CAPTCHAs, or security challenges.

## Whole-site crawl

Enter a site's home page to discover same-site sections and pagination. Crawls run breadth-first, up to 500 pages and 3 link levels, with at most 5 concurrent page requests; the form lets you lower the page limit and stop a crawl. Repeated list entries are merged by link into one Excel file. Successful page responses are cached in memory for one hour.

The local Hermes model interprets free-form extraction requests, selects the output columns, and maps them to each list item's title, link, date, summary, section, and category. Values that cannot be found are marked as inferred rather than left blank.

Coverage depends on the site's public HTML, navigation, and `robots.txt`; this is a bounded crawler, not a guarantee that every page on every site can be discovered. The progress panel reports visited pages, discovered sections, and extracted records.
