---
name: sonar
description: Live-web search, fetch, and text extraction via Sonar MCP tools.
user-invocable: true
disable-model-invocation: false
metadata: {"openclaw": {"requires": {"bins": ["sonar-mcp"]}}}
---

# Sonar MCP

Sonar is a deterministic live-web evidence engine. It searches the web through a private SearXNG instance, ranks and deduplicates results, fetches URLs while respecting robots.txt, and extracts readable text. No LLM inside — all mechanics are transparent and reproducible.

## Available tools

| Tool | Purpose | Key params |
|------|---------|------------|
| `sonar_health` | Check runtime readiness (DB writable, SearXNG reachable) | `config_path`, `db_path` |
| `sonar_search` | Search the live web and return ranked evidence | `query`, `limit`, `freshness`, `engines`, `categories`, `language`, `force_refresh` |
| `sonar_fetch` | Fetch one URL and cache its metadata | `url`, `force_refresh` |
| `sonar_extract` | Extract readable text from a URL or cached document | `url` or `document_id`, `force_refresh` |

All four tools are deterministic — no reasoning model involved.

## Workflow: search → fetch → extract

1. **Check health** if unsure about connectivity: `sonar_health`
2. **Search** for ranked web results: `sonar_search`
3. **Fetch** to verify and cache a specific URL: `sonar_fetch`
4. **Extract** to get full readable text: `sonar_extract`

Compose these steps deliberately. Do not extract every search result — pick the most relevant URLs first, then extract only what you need. A typical evidence-gathering session uses search to narrow, then extract on 1-3 top results.

## Search parameters

- **`freshness`**: `"any"` (default), `"day"`, `"week"`, `"month"` — use `"day"` or `"week"` when the user needs recent information
- **`limit`**: default 8, max 20 — start with 5-8; go higher only if the first pass is thin
- **`engines`** / **`categories`**: optional SearXNG filters — omit for broad search, specify when targeting a domain (e.g., `engines: ["stackoverflow"]`)
- **`language`**: optional BCP-47 tag — omit unless the user needs results in a specific language
- **`force_refresh`**: bypass the cache — use sparingly, only when results feel stale

## Ranking mechanics

Sonar scores every result transparently. Understanding the scoring helps interpret why certain results rank higher:

- **Position score**: first results from SearXNG weighted higher (decays 0.1 per rank)
- **Query overlap**: fraction of query terms found in title + snippet (weighted ×0.8)
- **Freshness boost**: exponential decay with ~30-day half-life — recent documents get up to +0.4
- **Domain priors**: configurable per-domain bonus (e.g., `docs.python.org` +0.35, `wikipedia.org` +0.10)
- **Deduplication**: results are deduplicated by canonical URL (tracking params like `utm_*`, `fbclid` stripped)

## Caching behaviour

- **Search results**: cached 15 minutes (same query + params returns instant cached response)
- **Extracted text**: cached 24 hours
- `force_refresh=true` bypasses the cache — only use when the cached response is known stale
- Fetching and extracting a cached URL is cheap; the first fetch of a new URL is the expensive operation

## Error handling

Sonar returns structured errors with a `retryable` hint:

| Error type | Meaning | Action |
|------------|---------|--------|
| `dependency_unavailable` | SearXNG or DB not reachable | Retryable — back off and retry |
| `upstream_unavailable` | SearXNG returned an error | Retryable — back off and retry |
| `timeout` | Fetch or search timed out | Retryable — back off and retry |
| `bad_request` | Invalid parameters | Fix the params, do not retry |
| `forbidden` | robots.txt blocks this URL | Skip this URL — the site opts out |
| `not_found` | URL does not exist or document_id invalid | Check the URL or ID |

## Practical patterns

### Search for a topic
```
sonar_search(query="Python asyncio task groups", limit=8)
```

### Search for recent information
```
sonar_search(query="kubernetes 1.31 release notes", freshness="month", limit=5)
```

### Full evidence pipeline: search → pick → extract
```
results = sonar_search(query="rate limiting algorithms", limit=8)
# Review results, pick the best URL
sonar_extract(url="https://example.com/rate-limiting-guide")
```

### Health check before a session
```
sonar_health()
```

### Fetch metadata without extracting
```
sonar_fetch(url="https://docs.python.org/3/library/asyncio.html")
```

## Configuration

Sonar is installed in the runtime/app layer (`/opt/sonar/bin`) and exposed on PATH
as `sonar-mcp`, `sonar-api`, and `sonar-smoke`.

The active config is selected by the `SONAR_CONFIG` env var:

- Image default: `/app/sonar.toml.default` (shipped with the container)
- User override: drop a `secrets/sonar.toml` on the host → bind-mounted at
  `/config/sonar.toml` and picked up automatically by `entrypoint.sh`

Key config sections:

- `[searxng]`: SearXNG base URL (defaults to internal `http://searxng:8080` sidecar)
- `[database]`: SQLite path (defaults to `/data/sonar.sqlite`)
- `[cache]`: TTLs for search and extract results
- `[fetch]`: timeouts, max body size, user agent
- `[search]`: default and max result limits
- `[ranking.domain_priors]`: per-domain score bonuses
- `[secrets]`: path to secrets overlay for SearXNG auth

MCP server registration (already wired in `container/qwen.json5.example`):
```json
{
  "mcpServers": {
    "sonar": {
      "command": "sonar-mcp",
      "env": { "SONAR_MCP_TRANSPORT": "stdio" },
      "trust": true
    }
  }
}
```
`SONAR_CONFIG` is inherited from the container environment, so the MCP
entry does not need to re-specify it.

## Important constraints

- No LLM inside Sonar — all ranking and extraction is deterministic
- `robots.txt` is respected automatically; a `forbidden` error means the site opts out — do not try to work around it
- Extracted text can be large — only extract URLs you actually need to read
- `document_id` in `sonar_extract` refers to a previously fetched or searched document, not an arbitrary identifier
- The SearXNG sidecar must be running for search to work — `sonar_health` will report if it is unreachable
- Cache is per-query-signature (query + limit + engines + categories + language + freshness) — changing any parameter produces a separate cache entry
