---
name: synapse
description: Semantic search, discovery, reasoning, and compiled-knowledge ingest/review over markdown vaults via Synapse MCP tools.
user-invocable: true
disable-model-invocation: false
---

# Synapse MCP

Synapse is a semantic retrieval, discovery, and compiled-knowledge engine for markdown knowledge bases. It indexes markdown folders into vector embeddings, exposes search/discovery/validation/reasoning over MCP, and — when the knowledge layer is enabled — ingests prepared research bundles into reviewable `source_summary` proposals that operators apply into a managed subtree of the vault.

## Available tools

### Deterministic retrieval (no LLM required)

| Tool | Purpose | Key params |
|------|---------|------------|
| `synapse_health` | Check runtime readiness, DB status, provider config | — |
| `synapse_index` | Index a markdown folder into the vector store | `vault_root`, `db_path` |
| `synapse_search` | Semantic search across indexed content | `query`, `mode` (note/chunk/hybrid), `limit` |
| `synapse_health_for_workspace` | Check readiness for the configured active workspace | `workspace` |
| `synapse_index_for_workspace` | Index the configured active workspace | `workspace` |
| `synapse_search_for_workspace` | Search the configured active workspace | `workspace`, `query`, `mode`, `limit` |
| `synapse_discover` | Find unlinked but semantically related documents | `threshold`, `max` |
| `synapse_validate` | Report broken `[[wikilinks]]` in indexed vault | — |

### Local-model "simple" facade

These are strict-shape variants for weaker runtimes: top-level plain-string args only, no nested objects, mode defaults to `research`.

| Tool | Purpose | Required params |
|------|---------|-----------------|
| `synapse_health_simple` | Minimal health probe | `vault_root`, `db_path` |
| `synapse_index_simple` | Minimal index call | `vault_root`, `db_path` |
| `synapse_search_simple` | Minimal search call (optional `mode`) | `query`, `db_path` |

### Reasoning (requires configured model via Cipher)

| Tool | Purpose | Key params |
|------|---------|------------|
| `synapse_cipher_health` | Report Cipher runtime requirements and readiness | optional overrides only |
| `synapse_cipher_audit` | Audit vault integrity (broken links, stale docs) | `mode` |
| `synapse_cipher_explain` | Explain why two documents are related | `doc_a`, `doc_b` |
| `synapse_cipher_chunking_strategy` | Recommend chunking parameters for a model | — |
| `synapse_cipher_review_stubs` | Review proposed stub notes before creation | — |

### Compiled knowledge layer (opt-in, Synapse v0.3.x)

Feature-gated: every tool below raises a structured bad-request error unless `[knowledge].enabled = true` (or `SYNAPSE_KNOWLEDGE_ENABLED=true`). In Nyx this is enabled by default in both `container/synapse.toml.example` and the active `secrets/synapse.toml` override — nothing to toggle at the call site.

| Tool | Purpose | Required params |
|------|---------|-----------------|
| `synapse_ingest_bundle` | Ingest a prepared research source bundle JSON (typically from `sonar_collect_sources_for_topic` / `sonar_prepare_paper_set`) | `bundle_path` |
| `synapse_knowledge_overview` | Managed-root status, counts, recent proposals | — |
| `synapse_knowledge_compile_bundle` | Turn an ingested bundle into pending `source_summary` proposals | `bundle_id` |
| `synapse_knowledge_list_proposals` | Filter the review queue by `status` (pending / applied / rejected) | — |
| `synapse_knowledge_get_proposal` | Full proposal detail: frontmatter, body, refs, reviewer action | `proposal_id` |
| `synapse_knowledge_apply_proposal` | Write the managed note, update `index.md` / `log.md`, reindex | `proposal_id` |
| `synapse_knowledge_reject_proposal` | Mark a proposal rejected, append reason to `log.md` | `proposal_id` (optional `reason`) |
| `synapse_knowledge_bundle_detail` | Bundle metadata + per-source proposal/applied counts | `bundle_id` |
| `synapse_knowledge_source_detail` | Normalized source metadata, stored segments, related proposals | `bundle_id`, `source_id` |

All nine tools wrap the same `service_api` entry points the admin console drives, so MCP-driven and human-driven reviews share a single code path.

## Workflow: always retrieval first

### Preferred for weaker/local models: workspace facade first

1. Use `synapse_health_for_workspace(workspace="current")`
2. Use `synapse_index_for_workspace(workspace="current")`
3. Use `synapse_search_for_workspace(workspace="current", mode="hybrid", query="...")`

This is the default path for weaker local runtimes because it removes raw path
arguments from the model-facing surface.

### Canonical path-bearing workflow

Use `synapse_health`, `synapse_index`, and `synapse_search` with explicit
`vault_root` and `db_path` only when you need exact path control.

1. **Check health** before any operation: `synapse_health`
2. **Index** if the DB is missing or stale: `synapse_index`
3. **Search** for user-facing retrieval: `synapse_search` with `mode: hybrid`
4. **Discover** for hidden connections: `synapse_discover` with explicit threshold
5. **Reason** only after deterministic evidence is gathered: `synapse_cipher_*`

Do not call Cipher tools before gathering evidence via search or discovery.

## Workflow: compiled knowledge review

When the goal is to build a curated, reviewable corpus from upstream Sonar artifacts, use the knowledge layer instead of writing raw notes by hand:

1. **Prepare upstream evidence** — run `sonar_collect_sources_for_topic` (or `sonar_prepare_paper_set`) and note the persisted `bundle_path` (e.g. `/data/workspace/vault/_sources/<run>/prepared_source_bundle.json`).
2. **Ingest** — `synapse_ingest_bundle(bundle_path=...)`. Returns the `bundle_id` used by every subsequent call.
3. **Compile** — `synapse_knowledge_compile_bundle(bundle_id=...)`. Produces `source_summary` proposals in `pending` state.
4. **Review** — `synapse_knowledge_list_proposals(status="pending")`, then `synapse_knowledge_get_proposal(proposal_id=...)` for each candidate. Use `synapse_knowledge_bundle_detail` / `synapse_knowledge_source_detail` to cross-check provenance before acting.
5. **Apply or reject** — `synapse_knowledge_apply_proposal(proposal_id=...)` writes the managed note under `<vault_root>/<managed_root>/`, updates `index.md` + `log.md`, and reindexes. `synapse_knowledge_reject_proposal(proposal_id=..., reason=...)` records the decision without touching the managed note.
6. **Status check anytime** — `synapse_knowledge_overview` for top-level counts and recent activity.

Guardrails:
- Never hand-edit files under the managed root (`_knowledge/` by default). The layer expects every write to go through apply/reject so `index.md` and `log.md` stay consistent and reindex runs after each mutation.
- `auto_compile_on_ingest = false` is the Nyx default — ingest and compile are explicit, separate steps. This is deliberate so operators can stage bundles before paying the compile cost.
- Rejected proposals stay inspectable via `status="rejected"` — they are an audit trail, not a garbage bin.

## Search modes

- **`note`**: broad thematic retrieval, returns full documents ranked by similarity
- **`chunk`**: precise section-level retrieval, returns specific passages
- **`hybrid`** (recommended): combines note shortlist + chunk evidence, weighted 40/60

Always prefer `hybrid` unless the user specifically needs document-level or section-level results.

## Discovery thresholds

Discovery scoring: `min(1.0, 0.75 * semantic + metadata_score + graph_score)`

- Service default threshold: `0.20` (sensitive, returns more connections)
- CLI default threshold: `0.65` (conservative)
- Always set threshold explicitly — do not rely on surface-specific defaults
- Start with `0.20` for exploration, raise to `0.40-0.65` for high-confidence links

## Practical patterns

### Search for a topic
```
synapse_search(query="rate limiting patterns", mode="hybrid", limit=10)
```

### Search the active workspace
```
synapse_search_for_workspace(query="rate limiting patterns", workspace="current", mode="hybrid", limit=10)
```

### Find hidden connections in a vault
```
synapse_discover(threshold=0.20, max=20)
```

### Full reindex after adding notes
```
synapse_index(vault_root="/data/workspace/vault", db_path="/data/workspace/vault/.synapse.sqlite")
```

### Audit before maintenance
```
synapse_cipher_audit(mode="audit")
```

### Explain a discovered relationship
```
synapse_cipher_explain(doc_a="notes/topic-a.md", doc_b="notes/topic-b.md")
```

### Ingest a Sonar bundle and review its proposals
```
synapse_ingest_bundle(bundle_path="/data/workspace/vault/_sources/<run>/prepared_source_bundle.json")
# → returns bundle_id
synapse_knowledge_compile_bundle(bundle_id="<id>")
# → creates pending source_summary proposals
synapse_knowledge_list_proposals(status="pending")
synapse_knowledge_get_proposal(proposal_id="<pid>")
synapse_knowledge_apply_proposal(proposal_id="<pid>")
```

### Status snapshot for the compiled knowledge layer
```
synapse_knowledge_overview()
```

## Configuration

Synapse is part of the Nix base layer (`flake.nix` pins it to a tag commit by
rev + sha256 — currently v0.3.1) and is installed under `/nix-env/bin`
(`/nix-env/bin/synapse-mcp`, `/nix-env/bin/synapse-index`,
`/nix-env/bin/synapse-search`, `/nix-env/bin/synapse-ingest-bundle`, etc.).
Those binaries are also exported on PATH, but Nyx prefers absolute paths in
config. Bumping: update the `rev` + `hash` in `flake.nix` to the newest tag
commit, then `just rebuild`. (`just update-synapse` tracks `main`, not tags —
use it only when main is at the release you want.)

The active config is selected by the `SYNAPSE_CONFIG` env var:

- Image default: `/app/synapse.toml.default` (shipped with the container)
- User override: drop a `secrets/synapse.toml` on the host → bind-mounted at
  `/config/synapse.toml` and picked up automatically by `entrypoint.sh`

Key config sections:

- `[vault]`: markdown folder root (defaults to `/data/workspace/vault`)
- `[database]`: SQLite path
- `[providers.embeddings.*]`: embedding model endpoints
- `[cipher]`: reasoning model timeouts
- `[knowledge]`: compiled knowledge layer toggle (`enabled`, `managed_root`,
  `default_status`, `generated_by`, `auto_compile_on_ingest`) — Nyx ships with
  `enabled = true` and `managed_root = "_knowledge"`. Override at runtime via
  `SYNAPSE_KNOWLEDGE_ENABLED=true|false`.

MCP server registration (already wired in `container/qwen.json5.example`):
```json
{
  "mcpServers": {
    "synapse": {
      "command": "/nix-env/bin/synapse-mcp",
      "env": { "SYNAPSE_MCP_TRANSPORT": "stdio" },
      "trust": true
    }
  }
}
```
`SYNAPSE_CONFIG` is inherited from the container environment, so the MCP
entry does not need to re-specify it.

## Local-model guidance

- Prefer `*_for_workspace` tools first for Qwen, Gemma, and other weaker local
  runtimes
- Treat raw-path tools as advanced overrides, not as the default agent path
- For notes intended for indexing, include both metadata fields and a Markdown
  `# Title` heading so indexed `documents.title` is populated reliably
- When building a corpus from retrieved sources, write notes from persisted
  Sonar artifacts rather than from memory of a prior tool result
- For weaker local-model workflows, use this read order before note writing:
  1. `prepared_sources_bundle.md`
  2. `prepared_source_manifest.json`
  3. only the specific `source_XX.json` or `source_XX.txt` files you need
  4. the full `prepared_source_bundle.json` only if the compact manifest is
     missing or clearly inconsistent
- Prefer Sonar `abstract` and `full_text` fields over lossy transcript snippets
  when preparing Synapse-ready notes
- Prefer `mode="hybrid"` unless the task clearly needs note-only or chunk-only retrieval
- Stage work explicitly:
  1. confirm the prepared source set from compact artifacts
  2. health
  3. write notes
  4. index
  5. search
  6. optional reasoning
- Keep the query semantic and precise; avoid overloading one search with many unrelated questions

Recommended note skeleton for indexed markdown:
```
TEST_ID: ...
QUERY: ...
SOURCE_URL: ...
TITLE: ...
AUTHORS: ...
PUBLISHED: ...
RETRIEVED_AT: ...

# Actual Document Title

## Abstract
...

## Extract
...

## Why Selected
...
```

## Important constraints

- For hybrid retrieval, note and contextual embedding providers must use matching dimensions
- Content-hash based change detection — unchanged files are skipped during reindex
- Reusing the same DB across different vault roots can leave stale documents
- Synapse works best when upstream source bundles preserve provenance and full text;
  if Sonar artifacts exist, prefer them over ad hoc summaries
- `synapse_cipher_audit` is deterministic; other Cipher tools require a reasoning model
- Discovery thresholds are corpus-dependent — tune for your vault size
