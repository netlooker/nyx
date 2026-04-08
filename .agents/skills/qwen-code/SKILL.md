---
name: qwen-code
description: Delegate tasks to Qwen Code, a headless sub-agent running on local LLM inference via llama.cpp.
user-invocable: true
disable-model-invocation: false
metadata: {"openclaw": {"requires": {"bins": ["qwen"]}}}
---

# Qwen Code (Headless Sub-Agent)

Qwen Code is a second AI coding agent running inside this container. Delegate tasks via its headless CLI and read back the results. It runs a local model on llama.cpp — no cloud dependency.

Qwen can also reuse the project skills mounted into the workspace. In practice,
that means the same Sonar and Synapse guidance used by the main Nyx agent can
be applied in Qwen runs too, as long as the prompt keeps the workflow narrow.

## When to use

- Second opinion or independent code review
- Parallel work: kick off a task in qwen while you continue
- Code generation where you want to compare approaches
- Tasks that benefit from a fresh context (no conversation history)
- Semantic search, discovery, or reasoning via Synapse MCP tools
- Structured retrieval tasks via Sonar MCP tools when the workflow is kept narrow

## Invocation

```bash
# Text response (default for human-readable output)
qwen -p "your task here" --output-format text

# JSON response (includes token usage stats)
qwen -p "your task here" --output-format json

# Auto-approve file writes
qwen -p "refactor utils.py into modules" --output-format text --yolo

# Run from a specific directory
cd /data/workspace/projects/myrepo && qwen -p "explain this codebase" --output-format text
```

Always use `--output-format text` for readable results or `--output-format json` when you need to parse responses or track token usage.

## Best practices for local-model runs

- Keep prompts narrow and staged
- Prefer one clear tool objective per invocation
- Prefer structured JSON output for anything you will inspect or reuse
- Avoid asking Qwen to do long multi-step tool orchestration in one prompt
- Reuse fresh artifacts on disk between invocations instead of making one call carry the whole workflow

Good staged pattern:

1. collect or confirm sources
2. inspect the auto-persisted prepared bundle
3. inspect any per-source sidecars you need
4. index or search
5. synthesize the final answer

Bad pattern:

- one prompt that asks Qwen to search the web, fetch pages, extract text, choose papers, write notes, index them, search them, and explain the result

Each `qwen -p` starts with a fresh context, so staged workflows are usually more reliable than monolithic ones.

## Passing context via stdin

```bash
cat README.md | qwen -p "summarize this" --output-format text
git diff HEAD~1 | qwen -p "review this diff for issues" --output-format text
```

## Synapse MCP tools

Qwen has Synapse MCP connected. These tools are available in every invocation:

| Tool | Purpose |
|------|---------|
| `synapse_health` | Check runtime readiness |
| `synapse_index` | Index markdown files into vector store |
| `synapse_search` | Hybrid semantic + keyword search |
| `synapse_health_for_workspace` | Check the active workspace |
| `synapse_index_for_workspace` | Index the active workspace |
| `synapse_search_for_workspace` | Search the active workspace |
| `synapse_discover` | Find unlinked similar documents |
| `synapse_validate` | Report broken wikilinks |
| `synapse_cipher_audit` | Audit vault integrity |
| `synapse_cipher_explain` | Explain why two documents relate |
| `synapse_cipher_chunking_strategy` | Get chunking recommendations |
| `synapse_cipher_review_stubs` | Review proposed stub notes |

```bash
qwen -p "use synapse_search to find everything about authentication" --output-format text
qwen -p "use synapse_discover to show hidden connections in the knowledge base" --output-format text
```

For weaker local runtimes, prefer the workspace facade:

```bash
qwen -p 'use synapse_health_for_workspace with workspace="current", then synapse_search_for_workspace with workspace="current" and mode="hybrid" for "prompt engineering theory"' --output-format text
```

## Sonar MCP tools

Qwen also has Sonar MCP available when the Nyx runtime is healthy.

Prefer the high-level Sonar facade first:

| Tool | Purpose |
|------|---------|
| `sonar_find_papers` | Curated scientific paper candidates |
| `sonar_prepare_paper_set` | Prepared paper/source set in one call |
| `sonar_collect_sources_for_topic` | Compact source bundle for a topic |

Use low-level Sonar tools only when needed:

| Tool | Purpose |
|------|---------|
| `sonar_search` | Ranked web search |
| `sonar_fetch` | Fetch one URL |
| `sonar_extract` | Extract readable text |

```bash
qwen -p 'use sonar_prepare_paper_set for "prompt engineering scientific papers" and return JSON only' --output-format json
```

High-level Sonar preparation now auto-persists durable artifacts by default, so
the usual workflow is to read the returned `bundle` object and then inspect the
persisted bundle under `bundle.bundle_path`, including
`prepared_source_bundle.json` and any `source_XX.txt` files, before writing
notes.

## Recommended Nyx pattern

For Sonar plus Synapse tasks inside Nyx, prefer this sequence:

1. Sonar high-level collection:
   `sonar_prepare_paper_set` or `sonar_collect_sources_for_topic`
2. Inspect the returned `bundle` object
3. Inspect `bundle.bundle_path` plus `prepared_source_bundle.json` and any per-paper sidecars
4. Write notes that include both metadata lines and a Markdown `# Title` heading
5. Synapse workspace pass:
   `synapse_health_for_workspace`
   `synapse_index_for_workspace`
   `synapse_search_for_workspace`
6. Final synthesis in a separate Qwen call if needed

This matches the flow that tested well in practice.

Recommended persisted artifact names:

- `<bundle_path>/prepared_source_bundle.json`
- `<bundle_path>/source_01.txt`, `<bundle_path>/source_02.txt`, ...
- `ingestion_vault/paper-01.md`, `paper-02.md`, ...

## Token monitoring

Context window: 131K tokens. Baseline overhead: ~14K tokens. Each `qwen -p` starts fresh.

```bash
# Check total usage
qwen -p "your task" --output-format json | jq '.[-1].usage'
```

| Consumption | Action |
|-------------|--------|
| < 40K | Normal |
| 40K-80K | Keep prompts focused |
| 80K-110K | Wrap up, split remaining work |
| > 110K | Stop. Start a fresh invocation |

For large tasks, split by module — each call gets a fresh 131K window:

```bash
qwen -p "review synapse/mcp_server.py for security issues" --output-format text
qwen -p "review synapse/search.py for security issues" --output-format text
```

## Constraints

- **Shared inference**: qwen uses the same llama.cpp server — avoid simultaneous heavy tasks
- **No memory**: each invocation is stateless
- **Working directory matters**: always `cd` to the right place first
- **Headless only**: never run `qwen` without `-p` inside the container
- **MCP health matters**: if a server appears disconnected, verify the runtime config and restart/recreate `nyx` before debugging prompts
