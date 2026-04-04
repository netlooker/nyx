---
name: synapse
description: Semantic search, discovery, and reasoning over markdown vaults via Synapse MCP tools.
user-invocable: true
disable-model-invocation: false
---

# Synapse MCP

Synapse is a semantic retrieval and discovery engine for markdown knowledge bases. It indexes markdown folders into vector embeddings and exposes search, discovery, validation, and reasoning via MCP tools.

## Available tools

### Deterministic (no LLM required)

| Tool | Purpose | Key params |
|------|---------|------------|
| `synapse_health` | Check runtime readiness, DB status, provider config | — |
| `synapse_index` | Index a markdown folder into the vector store | `vault_root`, `db_path` |
| `synapse_search` | Semantic search across indexed content | `query`, `mode` (note/chunk/hybrid), `limit` |
| `synapse_discover` | Find unlinked but semantically related documents | `threshold`, `max` |
| `synapse_validate` | Report broken `[[wikilinks]]` in indexed vault | — |

### Reasoning (requires configured model via Cipher)

| Tool | Purpose | Key params |
|------|---------|------------|
| `synapse_cipher_audit` | Audit vault integrity (broken links, stale docs) | `mode` |
| `synapse_cipher_explain` | Explain why two documents are related | `doc_a`, `doc_b` |
| `synapse_cipher_chunking_strategy` | Recommend chunking parameters for a model | — |
| `synapse_cipher_review_stubs` | Review proposed stub notes before creation | — |

## Workflow: always retrieval first

1. **Check health** before any operation: `synapse_health`
2. **Index** if the DB is missing or stale: `synapse_index`
3. **Search** for user-facing retrieval: `synapse_search` with `mode: hybrid`
4. **Discover** for hidden connections: `synapse_discover` with explicit threshold
5. **Reason** only after deterministic evidence is gathered: `synapse_cipher_*`

Do not call Cipher tools before gathering evidence via search or discovery.

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

## Configuration

Synapse config lives at `config/synapse.toml` in the synapse project. Key sections:

- `[vault]`: markdown folder root
- `[database]`: SQLite path
- `[providers.embeddings.*]`: embedding model endpoints
- `[cipher]`: reasoning model timeouts

MCP server registration (already configured in container):
```json
{
  "mcpServers": {
    "synapse": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/synapse", "synapse-mcp"],
      "env": {
        "SYNAPSE_CONFIG": "/path/to/synapse/config/synapse.toml",
        "SYNAPSE_MCP_TRANSPORT": "stdio"
      }
    }
  }
}
```

## Important constraints

- For hybrid retrieval, note and contextual embedding providers must use matching dimensions
- Content-hash based change detection — unchanged files are skipped during reindex
- Reusing the same DB across different vault roots can leave stale documents
- `synapse_cipher_audit` is deterministic; other Cipher tools require a reasoning model
- Discovery thresholds are corpus-dependent — tune for your vault size
