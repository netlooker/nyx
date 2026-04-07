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
| `sonar_find_papers` | Return curated scientific paper candidates for a topic | `query`, `count`, `profile` |
| `sonar_prepare_paper_set` | Search, filter, and extract a prepared scientific paper set in one call | `query`, `count`, `profile`, `direct_only` |
| `sonar_collect_sources_for_topic` | Return a compact structured source bundle for a topic | `topic`, `max_results`, `corpus` |

All Sonar tools are deterministic — no reasoning model involved.

## Workflow Choice

### Preferred for weaker/local models: high-level facade first

1. Start with `sonar_prepare_paper_set`, `sonar_find_papers`, or `sonar_collect_sources_for_topic`
2. Persist the structured result to disk before summarizing or writing notes
3. Use the low-level tools only when you need tighter control over ranking, fetch, or extraction

This is the default path for weaker local runtimes such as Gemma/Qwen because
it collapses the fragile `search -> fetch -> extract -> choose` loop into fewer
transitions.

For agentic corpus-building flows, treat the high-level Sonar result as source
material, not as disposable tool output. Save the returned JSON and any per-paper
extracts you need before writing downstream notes. Large tool payloads can be
truncated in transcripts, while persisted artifacts remain inspectable.

### Strong-model or manual workflow: search → fetch → extract

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

### Prepare a scientific paper set in one call
```
sonar_prepare_paper_set(query="prompt engineering scientific papers", count=5, profile="scientific", direct_only=true)
```

### Collect a compact source bundle for a topic
```
sonar_collect_sources_for_topic(topic="prompt engineering", max_results=5, corpus="papers")
```

### Persist the prepared source set before note writing
```
bundle = sonar_collect_sources_for_topic(topic="prompt engineering", max_results=5, corpus="papers")
# Save the structured bundle to artifacts/source_bundle.json before summarizing it
```

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

Sonar is installed in the runtime/app layer under `/opt/sonar/bin`
(`/opt/sonar/bin/sonar-mcp`, `/opt/sonar/bin/sonar-api`,
`/opt/sonar/bin/sonar-smoke`). Those binaries are also exported on PATH, but
Nyx prefers absolute paths in config.

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
      "command": "/opt/sonar/bin/sonar-mcp",
      "env": { "SONAR_MCP_TRANSPORT": "stdio" },
      "trust": true
    }
  }
}
```
`SONAR_CONFIG` is inherited from the container environment, so the MCP
entry does not need to re-specify it.

## Local-model guidance

- Prefer the high-level paper/source tools for Qwen, Gemma, and other weaker
  local runtimes
- Avoid asking a weak model to orchestrate many Sonar steps in one prompt
- Persist Sonar outputs to disk before compressing them into notes or summaries
- Prefer durable artifacts such as `artifacts/source_bundle.json` and per-source
  text files over relying on long tool results in the transcript
- If you need multi-step evidence gathering, stage it:
  1. search or prepare
  2. persist the result set
  3. inspect the persisted artifacts
  4. only then fetch/extract more
- Prefer one high-value Sonar call over long search/fetch/extract loops
- Return or request structured JSON whenever possible

## Important constraints

- No LLM inside Sonar — all ranking and extraction is deterministic
- `robots.txt` is respected automatically; a `forbidden` error means the site opts out — do not try to work around it
- Extracted text can be large — only extract URLs you actually need to read
- `document_id` in `sonar_extract` refers to a previously fetched or searched document, not an arbitrary identifier
- The SearXNG sidecar must be running for search to work — `sonar_health` will report if it is unreachable
- Cache is per-query-signature (query + limit + engines + categories + language + freshness) — changing any parameter produces a separate cache entry
