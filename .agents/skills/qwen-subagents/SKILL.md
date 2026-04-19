---
name: qwen-subagents
description: Delegate focused research, curation, or retrieval tasks to purpose-built Qwen Code subagents by shelling out in headless mode. Use this to get a clean, isolated context for deep Sonar research or Synapse knowledge work without polluting the current conversation.
user-invocable: true
disable-model-invocation: false
metadata: {"openclaw": {"requires": {"bins": ["qwen"]}}}
---

# Qwen Subagent Delegation

Three purpose-built subagents live under `~/.qwen/agents/` (source: `.agents/subagents/*.md`). They are invoked via Qwen Code in headless mode — each call spins up an isolated session with a restricted tool allowlist, runs the task end-to-end, and returns the final answer as text.

Use this skill when you want the work done in a **separate context** from yours: deep multi-step research that would otherwise consume thousands of tokens here, or a specialized pipeline that already encodes the correct tool ordering.

## Available subagents

| Subagent | Use when | Returns |
|----------|----------|---------|
| `sonar-researcher` | You need a prepared research bundle — web search + extraction for a topic or paper set | `BUNDLE_PATH: /root/.sonar/bundles/<id>/prepared_source_bundle.json` + counts |
| `synapse-curator` | You have a prepared bundle path and want it ingested into the Synapse knowledge layer | `BUNDLE_ID`, proposal counts, knowledge overview |
| `synapse-searcher` | You want semantic retrieval over indexed vault content (notes, chunks, discovery links) | Ranked note paths with scores and excerpts |

These chain naturally: `sonar-researcher` → hand its `BUNDLE_PATH` to `synapse-curator` → later query with `synapse-searcher`.

## Invocation

Headless Qwen has no `--agent` flag. The main Qwen agent picks the right subagent from the prompt, so **name it explicitly**:

```bash
qwen -p "Use the sonar-researcher subagent to collect 5 sources on <topic>." --yolo --output-format text
```

Key flags:

- `-p "<prompt>"` — headless / non-interactive mode. Required; otherwise Qwen opens a TUI.
- `--yolo` — auto-approve tool calls. Required for shell-out; without it Qwen blocks on approval prompts with no stdin to answer.
- `--output-format text` (default) — plain text. Use `json` when you need to parse the transcript programmatically; use `stream-json` if you want line-delimited events (rarely useful from a shell-out).
- `--system-prompt` / `--append-system-prompt` — **do not set**. Overriding the system prompt defeats the subagent definition.

## When to delegate vs. do it yourself

Delegate when:

- The task is >3 tool calls of someone else's domain (e.g. you'd need to learn Sonar's bundle-path conventions).
- You want the intermediate steps kept out of your context — only the final answer back.
- The task matches a subagent's `description` exactly (all three say "MUST BE USED" for their trigger).

Don't delegate when:

- A single MCP call would do. Running `sonar_search` directly is cheaper than spawning a Qwen session.
- You need streaming intermediate results — the shell-out is one-shot.
- The subagent's tools are a subset of what you'd need and you'd have to finish the work yourself anyway.

## Cost & latency

- Cold-start: each invocation boots a fresh Qwen session against the llama.cpp endpoint (~several seconds before the first tool call).
- No session reuse between calls — chain in a single prompt instead of two shell-outs when possible.
- Output is buffered to completion before returning. For long research jobs expect minutes, not seconds.

## Patterns

### Research a topic and ingest it (chained)

Two calls, each isolated:

```bash
# Step 1: prepare bundle
qwen -p "Use the sonar-researcher subagent to collect 8 sources on post-quantum cryptography signatures." --yolo

# Parse the BUNDLE_PATH from output, then:

# Step 2: ingest
qwen -p "Use the synapse-curator subagent to ingest $BUNDLE_PATH, compile proposals, and list them." --yolo
```

### One-shot search over the vault

```bash
qwen -p "Use the synapse-searcher subagent to find notes related to 'agent memory architectures' with mode=hybrid." --yolo
```

### Parse structured output

`sonar-researcher` and `synapse-curator` end every response with a handoff block:

```
BUNDLE_PATH: /root/.sonar/bundles/abc123/prepared_source_bundle.json
BUNDLE_ID: abc123
SOURCES_PREPARED: 7
SOURCES_REQUESTED: 8
```

Extract with `grep '^BUNDLE_PATH:' <(qwen -p "...")` or parse the JSON output format.

## Gotchas

- **No `--agent` flag exists.** The Qwen docs for subagents describe them as invoked by natural-language delegation from the main agent. Naming the subagent in the prompt is the supported pattern.
- **Without `--yolo`, Qwen hangs waiting for tool approval.** Shell-out has no TTY to answer the prompt.
- **Subagent definitions live in `/app/subagents/*.md`** inside the container (symlinked to `~/.qwen/agents/` for discovery). Editing them requires a container restart or re-symlink; image rebuild is not required.
- **Do not run two Qwen sessions concurrently against the same llama.cpp server** unless the server is configured for parallel slots — requests will serialize and the second will look hung.
- **Quote the prompt correctly.** The outer shell strips one layer of quoting; prefer single-quoted prompts with no embedded single quotes, or heredoc for long prompts.
