---
name: scrapling
description: Adaptive web scraping with anti-bot bypass — HTTP impersonation, Playwright, and Camoufox stealth fetches via Scrapling MCP.
user-invocable: true
disable-model-invocation: false
metadata: {"openclaw": {"requires": {"bins": ["scrapling"]}}}
---

# Scrapling MCP

Scrapling is a web-fetching engine that escalates from lightweight HTTP to full browser automation to anti-bot-defeating stealth browsing — pick the cheapest tool that works. Use it for pages that Sonar cannot fetch (JavaScript-rendered, behind Cloudflare, requires session state).

## When to use Scrapling vs Sonar

- **Sonar first** for ranked search and extraction of static pages. It is cheaper, deterministic, cached, and respects robots.txt.
- **Scrapling** when Sonar returns empty text (SPA rendered after load), `forbidden` on a page you must read, or when you need to keep a browser session open across multiple requests (login, cart, pagination).
- **Never** use Scrapling to bypass robots.txt for its own sake. The escalation is for real rendering or anti-bot walls, not for ignoring opt-outs.

## Available tools

Three fetcher tiers, plus bulk variants, plus session management:

| Tool | Tier | Use when |
|------|------|----------|
| `get` | HTTP impersonation (curl_cffi) | Page returns real HTML to a plain request, but the server fingerprints the TLS/headers — fastest option |
| `bulk_get` | HTTP impersonation | Same, parallel across many URLs |
| `fetch` | Playwright (Chromium) | Page needs JavaScript to render content |
| `bulk_fetch` | Playwright | Same, parallel |
| `stealthy_fetch` | Camoufox (patched Firefox) | JS-rendered + bot-detection present; can solve Cloudflare Turnstile |
| `bulk_stealthy_fetch` | Camoufox | Same, parallel |
| `open_session` | Session setup | Multi-step flows (login → navigate → fetch) |
| `close_session` | Session teardown | Always close sessions when done |
| `list_sessions` | Debug | See what's still open |
| `screenshot` | Session capture | Visual evidence of a page state |

## Escalation ladder

Always start at the lowest tier and climb only on failure:

1. `get` — 90% of pages work here. Defaults to `chrome` TLS impersonation.
2. `fetch` — if `get` returns a shell page (SPA) or empty body.
3. `stealthy_fetch` — if `fetch` gets blocked, redirected to a challenge page, or returns a Cloudflare interstitial. Set `solve_cloudflare=true` to auto-solve Turnstile.

Escalating wastes seconds and browser resources. Staying too low wastes retries. Read the returned `ResponseModel` — if `main_content` looks empty or challenge-shaped, climb.

## Output control

All fetchers share these params:

- `extraction_type`: `"markdown"` (default, cleanest for LLMs), `"text"`, or `"html"` (raw).
- `main_content_only`: `true` (default) strips nav/footer/ads. Set `false` when you need the full page.
- `css_selector`: extract a specific region only — faster than post-filtering, preserves structure.

Prefer `markdown` + `main_content_only=true` unless a task demands raw HTML.

## Sessions

Sessions are expensive to open (browser launch) but cheap to reuse. Open one per **task domain**, not per URL.

```
session = open_session(session_type="stealthy", session_id="amazon-scrape")
fetch(url="https://amazon.com/product/A", session_id="amazon-scrape")
fetch(url="https://amazon.com/product/B", session_id="amazon-scrape")
close_session(session_id="amazon-scrape")
```

Always `close_session` in a cleanup step — leaking sessions holds a browser process hostage in `/data/scrapling`. Use `list_sessions` if unsure what's open.

## Practical patterns

### Cheapest fetch — plain page with TLS impersonation
```
get(url="https://docs.python.org/3/library/asyncio.html")
```

### JS-rendered single-page app
```
fetch(url="https://app.example.com/dashboard", wait_selector=".loaded", network_idle=true)
```

### Cloudflare-protected page
```
stealthy_fetch(url="https://protected.example.com/data", solve_cloudflare=true)
```

### Extract one region only
```
fetch(url="https://news.example.com/article/1", css_selector="article.main", extraction_type="markdown")
```

### Parallel scrape with impersonation
```
bulk_get(urls=["https://a.com/1", "https://a.com/2", "https://a.com/3"], impersonate="chrome131")
```

### Multi-step session with screenshot
```
open_session(session_type="dynamic", session_id="gh-login")
fetch(url="https://github.com/login", session_id="gh-login")
# ... navigate with fetch calls reusing session_id ...
screenshot(url="https://github.com/settings", session_id="gh-login", full_page=true)
close_session(session_id="gh-login")
```

## Constraints & gotchas

- **First boot delay**: `scrapling install` runs in the background on the container's first boot (~500MB download of Chromium + Camoufox). Browser-based tools (`fetch`, `stealthy_fetch`, `screenshot`) will fail until it completes. `get` works immediately.
- **Check installation**: if browser tools fail with "executable not found", run `scrapling install` manually: `docker compose exec nyx scrapling install`. Browsers land under `/data/scrapling/` and survive rebuilds.
- **Respect robots.txt**: Scrapling does not enforce it automatically like Sonar does. The agent is the enforcement point — do not scrape sites that opt out.
- **Timeouts are in milliseconds** for browser tools (`fetch`, `stealthy_fetch`, `screenshot`), but **seconds** for `get`/`bulk_get`. This is inherited from the underlying libraries.
- **Cloudflare solving is opt-in**: `solve_cloudflare=true` only on `stealthy_fetch`. It is slower and louder — do not set it blindly.
- **Sessions are per-worker memory**: they do not persist across container restarts. Re-open after `just restart`.
- **Prefer bulk over loops**: `bulk_fetch([a,b,c])` shares one browser context; three separate `fetch` calls cold-start three times.

## Configuration

Scrapling is installed via `uv tool` into `/opt/uv/tools/scrapling` at image build time. The CLI lives at `/usr/local/bin/scrapling` (on PATH). Version is pinned via the `SCRAPLING_VERSION` build arg in `justfile`/`docker-compose.yml` and recorded in `/app/build-info.json`.

Browser backends (Playwright chromium, Camoufox) are downloaded on first container boot into `/data/scrapling/ms-playwright` and `/data/scrapling/camoufox` (symlinked from `~/.cache/…`) so they persist across image rebuilds.

MCP server registration (already wired in `container/qwen.json5.example`):
```json
{
  "mcpServers": {
    "scrapling": {
      "command": "/usr/local/bin/scrapling",
      "args": ["mcp"],
      "trust": true
    }
  }
}
```

Transport is stdio by default. Add `--http --port 8000` to `args` if an HTTP MCP transport is needed.

## Local-model guidance

- Always start at `get` — weaker models have a tendency to jump to `stealthy_fetch` unnecessarily, which wastes time and fingerprint budget.
- Always pass `extraction_type="markdown"` and `main_content_only=true` unless explicitly told otherwise — raw HTML blows up context for marginal value.
- Use `css_selector` aggressively. A 50KB page region beats a 500KB full-page dump every time.
- For parallelism, prefer `bulk_*` tools — do not loop over single `fetch` calls.
- Pair Scrapling with Sonar: use `sonar_search` to find candidate URLs, then Scrapling only on the ones Sonar cannot read.
