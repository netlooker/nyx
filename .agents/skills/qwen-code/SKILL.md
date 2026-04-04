---
name: qwen-code
description: Delegate tasks to Qwen Code, a headless sub-agent running on local LLM inference via llama.cpp.
user-invocable: true
disable-model-invocation: false
metadata: {"openclaw": {"requires": {"bins": ["qwen"]}}}
---

# Qwen Code (Headless Sub-Agent)

Qwen Code is a second AI coding agent running inside this container. Delegate tasks via its headless CLI and read back the results. It runs a local model on llama.cpp — no cloud dependency.

## When to use

- Second opinion or independent code review
- Parallel work: kick off a task in qwen while you continue
- Code generation where you want to compare approaches
- Tasks that benefit from a fresh context (no conversation history)
- Semantic search, discovery, or reasoning via Synapse MCP tools (already wired)

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
