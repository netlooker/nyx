---
name: synapse
description: Semantic search, discovery, reasoning, research-bundle ingest, and compiled-knowledge review over markdown vaults via Synapse MCP tools.
user-invocable: true
disable-model-invocation: false
---

# Synapse MCP

Synapse is a semantic retrieval, discovery, and compiled-knowledge engine for markdown knowledge bases. It indexes markdown folders into embeddings, exposes deterministic search and validation over MCP, and can ingest prepared research bundles into reviewable `source_summary` proposals under a managed knowledge subtree.

In Nyx, Synapse is installed into the container with `uv tool install`. The host does not need a separate Python or Synapse install.

## Available tools

### Deterministic retrieval

| Tool | Purpose | Key params |
|------|---------|------------|
| `synapse_health` | Check runtime readiness, DB status, provider config | optional overrides |
| `synapse_index` | Index a markdown folder into the vector store | `vault_root`, `db_path` |
| `synapse_search` | Semantic search across indexed content | `query`, `mode`, `limit` |
| `synapse_discover` | Find unlinked but semantically related documents | `threshold`, `max_total` |
| `synapse_validate` | Report broken `[[wikilinks]]` in indexed vault | optional overrides |
| `synapse_health_for_workspace` | Check readiness for the configured active workspace | `workspace` |
| `synapse_index_for_workspace` | Index the configured active workspace | `workspace` |
| `synapse_search_for_workspace` | Search the configured active workspace | `workspace`, `query`, `mode`, `limit` |

### Strict-shape local-model facade

These are reduced-shape variants for weaker runtimes: top-level plain string args only.

| Tool | Purpose | Required params |
|------|---------|-----------------|
| `synapse_health_simple` | Minimal health probe | `vault_root`, `db_path` |
| `synapse_index_simple` | Minimal index call | `vault_root`, `db_path` |
| `synapse_search_simple` | Minimal search call | `query`, `db_path` |

### Reasoning via Cipher

| Tool | Purpose | Key params |
|------|---------|------------|
| `synapse_cipher_health` | Report Cipher runtime requirements and readiness | optional overrides |
| `synapse_cipher_audit` | Audit vault integrity | `mode` |
| `synapse_cipher_explain` | Explain why two documents are related | `doc_a`, `doc_b` |
| `synapse_cipher_chunking_strategy` | Recommend chunking parameters for a model | optional overrides |
| `synapse_cipher_review_stubs` | Review proposed stub notes before creation | candidates |

### Compiled knowledge layer

Feature-gated: these tools require `[knowledge].enabled = true` or `SYNAPSE_KNOWLEDGE_ENABLED=true`. In Nyx this is normally enabled in the active Synapse config.

| Tool | Purpose | Required params |
|------|---------|-----------------|
| `synapse_ingest_bundle` | Ingest a prepared research source bundle JSON | `bundle_path` |
| `synapse_knowledge_overview` | Managed-root status, counts, recent proposals | — |
| `synapse_knowledge_compile_bundle` | Turn an ingested bundle into pending `source_summary` proposals | `bundle_id` |
| `synapse_knowledge_list_proposals` | Filter review queue by `status` | optional `status`, `limit` |
| `synapse_knowledge_get_proposal` | Full proposal detail | `proposal_id` |
| `synapse_knowledge_apply_proposal` | Apply a pending proposal | `proposal_id` |
| `synapse_knowledge_reject_proposal` | Reject a pending proposal and append reason to `log.md` | `proposal_id` |
| `synapse_knowledge_revert_proposal` | Revert an applied proposal back to pending review | `proposal_id` |
| `synapse_knowledge_bundle_detail` | Bundle metadata plus per-source proposal counts | `bundle_id` |
| `synapse_knowledge_source_detail` | Normalized source metadata, stored segments, related proposals | `bundle_id`, `source_id` |

These tools share the same service path as the HTTP admin surface, so operator actions and MCP actions stay in one audit trail.

## Retrieval workflow

Preferred path for weaker local models:

1. `synapse_health_for_workspace(workspace="current")`
2. `synapse_index_for_workspace(workspace="current")`
3. `synapse_search_for_workspace(workspace="current", query="...", mode="research")`

Canonical explicit-path path:

1. Run `synapse_health`
2. Run `synapse_index` if the DB is missing or stale
3. Run `synapse_search`
4. Run `synapse_discover` if you need hidden cross-note links
5. Run `synapse_cipher_*` only after deterministic evidence exists

Do not start with Cipher when retrieval can answer the question.

## Search modes

Use the real Synapse search modes:

- `research`: blended source-first retrieval, usually the default and best starting point
- `source`: return source-oriented matches
- `note`: return note-oriented matches
- `evidence`: return narrow evidence matches

Prefer `research` unless the user explicitly wants note-only or evidence-only behavior.

## Compiled knowledge workflow

When the goal is to build a curated, reviewable corpus from Sonar or other upstream artifacts:

1. Prepare or locate a persisted bundle artifact.
2. Ingest it with `synapse_ingest_bundle(bundle_path=...)`.
3. Compile it with `synapse_knowledge_compile_bundle(bundle_id=...)`.
4. Review proposals with `synapse_knowledge_list_proposals` and `synapse_knowledge_get_proposal`.
5. Apply, reject, or revert with the `synapse_knowledge_*_proposal` tools.
6. Use `synapse_knowledge_overview` or bundle/source detail tools for status and provenance checks.

Guardrails:

- Never hand-edit files under the managed root.
- `synapse_knowledge_apply_proposal` is the only supported path to create managed notes.
- `synapse_knowledge_revert_proposal` is the supported path to undo an applied note while preserving audit history.
- Rejected proposals remain part of the audit trail.

## Bundle ingest guidance

Synapse ingest is intentionally more tolerant than older revisions:

- manual bundles may omit optional fields like `document_id`, `search_score`, `direct_paper_url`, or `published`
- a bundle may provide `sources`, `prepared_sources`, or a single `source`
- a source may provide raw text via `text`, `content`, `body`, or `markdown`

Deduplication behavior:

- ingest now checks duplicate sources by normalized URL identity and content hash
- duplicate sources are skipped by default instead of reinserted
- pass `replace_existing=true` to `synapse_ingest_bundle` when you want a duplicate source to replace the previously ingested one

## Embedding behavior

Synapse no longer hard-fails solely because the primary Infinity endpoint is unreachable:

- it tries the configured provider first
- if a compatible named `fallback` provider exists, it tries that next
- if remote providers fail, it falls back to a purely local in-process embedding adapter

This preserves indexing and search availability during provider outages, though search quality may degrade relative to the primary model.

## Practical patterns

### Search a workspace

```text
synapse_search_for_workspace(workspace="current", query="rate limiting patterns", mode="research", limit=10)
```

### Search a specific DB directly

```text
synapse_search(query="rate limiting patterns", mode="research", limit=10)
```

### Find hidden connections

```text
synapse_discover(threshold=0.20, max_total=20)
```

### Ingest and review a bundle

```text
synapse_ingest_bundle(bundle_path="/data/workspace/vault/_sources/<run>/prepared_source_bundle.json")
synapse_knowledge_compile_bundle(bundle_id="<bundle_id>")
synapse_knowledge_list_proposals(status="pending")
synapse_knowledge_get_proposal(proposal_id=123)
synapse_knowledge_apply_proposal(proposal_id=123)
```

### Replace an already ingested duplicate source

```text
synapse_ingest_bundle(bundle_path="/data/workspace/vault/_sources/<run>/prepared_source_bundle.json", replace_existing=true)
```

### Undo an applied compiled note

```text
synapse_knowledge_revert_proposal(proposal_id=123)
```

## Configuration

Synapse binaries live under `/usr/local/bin` in the Nyx container. The active config is selected by `SYNAPSE_CONFIG`.

Common sections:

- `[vault]`: markdown folder root
- `[database]`: SQLite path
- `[providers.embeddings.*]`: embedding providers
- `[cipher]`: reasoning timeouts
- `[knowledge]`: compiled knowledge layer settings

Important knobs:

- `[knowledge].enabled`
- `[knowledge].managed_root`
- `[knowledge].auto_compile_on_ingest`
- `[index].provider`
- `[index].contextual_provider`
- `[search].provider`

## Local-model guidance

- Prefer `*_for_workspace` tools first for weaker local runtimes
- Treat raw-path tools as explicit overrides, not defaults
- Use `research` mode unless you have a reason not to
- For note writing from source bundles, read compact manifest artifacts first and load full bundle JSON only when necessary
- Build the corpus in stages:
  1. confirm source set
  2. health
  3. ingest or write
  4. index
  5. search
  6. optional reasoning
