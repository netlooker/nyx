# PRD: Axon — Context Engineering Proxy for Nyx

## Problem

OpenClaw talks to llama.cpp (Qwen3.5-35B, 262K context window) over the OpenAI-compatible `/v1/chat/completions` endpoint. Nothing manages what goes into that window.

Specific waste patterns in agentic loops:

- **System prompt repetition.** Every request includes the full system prompt (10K-30K tokens). In a 40-call tool-use loop, that's up to 800K tokens of repeated content. The llama.cpp KV cache already holds it — but the agent has no visibility into this.
- **Verbose tool output.** Shell commands, file reads, and git operations produce raw output included verbatim in conversation history. Much of it is noise.
- **Stale history.** As conversations grow, early turns that established context get buried under dozens of tool call/response pairs that no longer matter.
- **No budget awareness.** The agent estimates context usage from session file size (`bytes / 4`). That's a heuristic, not a measurement.

### Why Not RTK

RTK (already in our Nix toolchain) compresses shell output. But its auto-rewrite hook silently transforms command output without the agent knowing. Result: the agent makes extra tool calls to recover stripped information. Benchmarks show +18% cost increase, +50% output tokens, +26% duration. The input savings are dwarfed by output increases. See [rtk-ai/rtk#582](https://github.com/rtk-ai/rtk/issues/582).

The lesson: **silent compression is counterproductive.** The agent must know what was compressed.

### Why Not MetaClaw

MetaClaw is a 29-module Python proxy that injects skills, collects RL training data, and rewrites prompts. It solves a different (larger) problem with proportionally larger complexity: FastAPI server, multiple RL backends, teacher distillation, scheduler, idle detection. The RL training value is unproven, and the proxy adds latency to every LLM call on the critical path.

The lesson: **complexity without proven value is liability.**

---

## Vision

Axon is a lightweight HTTP proxy between OpenClaw and llama.cpp. It intercepts `/v1/chat/completions` requests, understands the token budget, and makes intelligent decisions about what to keep, compress, summarize, or evict — then forwards the optimized request to the inference server.

Three principles:

1. **Agent-aware.** The agent knows Axon exists. Compressions are visible. The agent can mark content as important. Axon reports budget status in response headers.
2. **Minimal.** Single Go binary. One TOML config file. No database. No RL. No framework.
3. **Fail-open.** If Axon crashes, OpenClaw can point directly at llama.cpp by changing one line in `openclaw.json5` (hot-reloaded, no rebuild).

---

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌─────────────────────────────┐
│  OpenClaw    │────>│    Axon      │────>│  llama.cpp                  │
│  (cortex)    │<────│  :8018       │<────│  192.168.129.130:8008       │
│  :18789      │     │              │     │  Qwen3.5-35B · 262K ctx    │
└──────────────┘     └──────────────┘     └─────────────────────────────┘
    Container           Container              Host / bare-metal
```

### Integration Point

OpenClaw discovers the LLM via `secrets/openclaw.json5`:

```json5
// Before Axon — direct to llama.cpp:
llamacpp: { baseUrl: 'http://192.168.129.130:8008/v1' }

// With Axon — proxy:
llamacpp: { baseUrl: 'http://axon:8018/v1' }
```

Axon forwards to the real llama.cpp endpoint configured in `axon.toml`. Hot-reload `openclaw.json5` to switch between direct and proxied mode — no rebuild needed.

### Proxy Surface

| Endpoint | Behavior |
|----------|----------|
| `POST /v1/chat/completions` | Intercept → analyze → optimize → forward → relay response |
| `GET /v1/models` | Passthrough |
| `POST /v1/embeddings` | Passthrough |
| `GET /axon/status` | Current session token budget breakdown |
| `GET /axon/health` | Liveness check (for Docker healthcheck) |
| `GET /axon/log` | Recent optimization decisions |

Streaming (`stream: true`) is required — OpenClaw uses SSE for chat completions. Axon optimizes the input (request rewriting) and relays the output stream byte-for-byte.

### Language: Go

Single static binary. Excellent HTTP proxy primitives (`net/http/httputil`). Goroutines handle concurrency without complexity. Nix can build it deterministically. Fast enough for the <10ms latency target.

Not Rust (unnecessary performance ceiling for an HTTP proxy, longer dev time). Not Python (explicitly rejected — this is not MetaClaw). Not Node.js (event loop contention under proxy load).

### State

Axon is near-stateless:

| Data | Storage | Lifetime |
|------|---------|----------|
| System prompt hash → token count | In-memory map | Ephemeral (rebuilds on restart) |
| Session token counts | In-memory | Ephemeral |
| Tool output dedup cache | In-memory with TTL | Ephemeral |
| Decision log | `/data/axon/decisions.jsonl` | Persistent (on `/data` volume) |
| Configuration | `/config/axon.toml` | Mounted from host |

No database. No SQLite. No external dependencies.

---

## Features

### P0 — Token Counting & Budget Tracking

The foundation. Everything else depends on knowing how many tokens are in the window.

- Tokenize each request's `messages` array using llama.cpp's `/tokenize` endpoint (already available). Cache results by content SHA-256 to avoid re-tokenizing unchanged content.
- Track per-request breakdown: system prompt tokens, conversation history tokens, tool output tokens, available headroom.
- Report via response headers:
  - `X-Axon-Tokens-In` — total input tokens forwarded
  - `X-Axon-Tokens-Saved` — tokens removed by optimizations
  - `X-Axon-Budget-Pct` — percentage of context window used
  - `X-Axon-Actions` — what Axon did (e.g., `truncated:5,compressed:2`)
- Expose `GET /axon/status` with current session budget.

**This alone replaces the agent's current `bytes / 4` heuristic** with actual token counts. The existing heartbeat and context threshold protocols (`HEARTBEAT.md`, `CONTEXT-QUICK-REF.md`) become accurate instead of approximate.

### P0 — System Prompt Deduplication Awareness

The single highest-value insight from the RTK #582 analysis: system prompts are 98% of input token volume in agentic loops.

Axon doesn't strip the system prompt (llama.cpp expects it for KV cache matching). But it:
- Hashes the system prompt. If unchanged from the previous request in the same session, reports the **effective** new tokens (conversation delta only) separately from raw total.
- Detects system prompt changes (OpenClaw hot-reload, skill injection) and logs them.
- Gives the agent and operator a realistic picture: "This request is 180K raw tokens, but only 12K are new since the last call."

### P1 — Intelligent Context Truncation

When total context exceeds a configurable threshold (default: 80% of window):

- Preserve: system prompt (always), most recent N turns (default: 10), the first turn (user's original intent), any turn the agent marked with `[KEEP]`.
- Truncate: oldest non-preserved turns, starting from the second turn.
- Replace truncated turns with a single marker: `[Axon: summarized N older turns — context at X%]`.
- Truncate from the **middle**, not the beginning — this preserves a stable prefix for llama.cpp KV cache reuse.

### P1 — Agent-Aware Tool Output Compression

RTK's approach (compress everything silently) fails. Axon's approach:

- **Never** compress silently. All compression produces visible markers.
- Auto-compress tool outputs above a token threshold (configurable, default: 2000 tokens). Compression: strip ANSI codes, deduplicate repeated lines, collapse whitespace, truncate with `[…N lines omitted…]`.
- The agent sees the markers and can request full output if needed.
- The agent can also explicitly request compression via a flag in tool call metadata.

### P2 — Smart Caching

- **Prefix stability.** Arrange message truncation to preserve a stable prefix (system prompt + early turns) that maximizes llama.cpp KV cache hits. This is a structural optimization: truncate from the middle, not the edges.
- **Tool output dedup.** If the same command returns identical output within a TTL (default: 30s), annotate the second occurrence as `[same as previous output]` instead of repeating it.
- **System prompt cache.** Hash → token count map avoids re-tokenizing the same prompt on every request.

### P3 — Observability Dashboard

- `GET /axon/status` — per-session token breakdown (system, conversation, tools, headroom).
- `GET /axon/log` — recent decisions with timestamps, token counts, actions taken.
- JSON structured logging to stdout — container-friendly, parseable.
- Every optimization decision logged: what was truncated/compressed, why, token counts before and after.

### P4 — Budget-Aware Context Injection

Inject small, factual context snippets when the budget allows — not skill injection (OpenClaw handles that), but ambient orientation:

```toml
[[inject.rules]]
trigger = "budget_below_pct"
threshold = 50
source = "file"
path = "/data/workspace/CONTEXT-QUICK-REF.md"
max_tokens = 500
```

Only inject if there's room. Always mark injected content clearly. This helps the agent reorient after long sessions without wasting budget when context is tight.

---

## Configuration

`secrets/axon.toml`:

```toml
[server]
listen = "0.0.0.0:8018"

[upstream]
url = "http://192.168.129.130:8008"
tokenize_endpoint = "/tokenize"

[context]
window_size = 262144
max_output = 32768
truncation_threshold_pct = 80
preserve_recent_turns = 10
preserve_first_turn = true

[compression]
auto_compress_above_tokens = 2000
strip_ansi = true
dedup_lines = true

[cache]
system_prompt_cache = true
tool_output_dedup_ttl_seconds = 30

[observability]
log_format = "json"
decision_log_path = "/data/axon/decisions.jsonl"

[inject]
enabled = false
```

---

## Nyx Integration

### docker-compose.yml

```yaml
services:
  cortex:
    depends_on:
      - axon
    # openclaw.json5 baseUrl → http://axon:8018/v1

  axon:
    image: nyx-axon:latest
    build:
      context: ..
      dockerfile: axon/Dockerfile
    restart: unless-stopped
    volumes:
      - ../secrets/axon.toml:/config/axon.toml:ro
      - ../data:/data
    ports:
      - "8018:8018"
```

### entrypoint.sh

Add `mkdir -p /data/axon` for the decision log directory.

### Nix

Phase 1: separate Dockerfile (no flake.nix changes). Phase 2+: add the Go binary to `flake.nix` as a Nix-built package in `basePaths` for full toolchain pinning.

### Heartbeat Integration

Update `inference-check.sh` to query `http://axon:8018/axon/status` instead of estimating from file size. The context thresholds in `HEARTBEAT.md` and `CONTEXT-QUICK-REF.md` remain valid — they just get accurate numbers.

---

## Non-Goals

- **RL training.** Axon does not collect training data or compute rewards.
- **Model routing.** One upstream. Not a load balancer.
- **Prompt engineering.** Manages context budget and structure, does not rewrite agent instructions.
- **General API gateway.** Understands OpenAI chat completions format specifically.
- **Replacing OpenClaw session management.** OpenClaw manages sessions and channels. Axon manages token budget of individual LLM requests.

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Context utilization visibility | `bytes / 4` estimate | Actual token counts per request |
| Context-exceeded errors | Unknown | Zero (truncation prevents overflow) |
| Agent task completion rate | Baseline | No degradation |
| Proxy latency overhead | N/A | <10ms p99 (excluding tokenization) |
| System prompt overhead visibility | 0% (invisible) | Effective vs. raw token reporting |
| Extra tool calls from compression | +50% (RTK baseline) | <2% increase |

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| **Silent compression costs more** (RTK lesson) | All compressions produce visible markers. Agent can mark `[KEEP]`. Conservative defaults. Phase 1 is observe-only. |
| **Complexity without value** (MetaClaw lesson) | Phase 1 is pure passthrough + counting. If counting reveals no actionable waste, project pauses. Single binary, one config file. |
| **Single point of failure** | Stateless (caches rebuild on restart). `restart: unless-stopped`. Hot-swap to direct llama.cpp by editing `openclaw.json5`. Health check endpoint for Docker. |
| **Tokenization accuracy** | Use llama.cpp's own `/tokenize` endpoint. Cache by content hash. Accept approximate counts from cache, accurate from endpoint. |
| **Streaming compatibility** | Go's `net/http` supports unbuffered SSE relay. Optimization happens on input only — output stream is byte-for-byte passthrough. |

---

## Roadmap

### Phase 1: Observe (weeks 1-2)

Transparent passthrough proxy with token counting. Zero modifications to requests.

- Go HTTP proxy: `/v1/chat/completions` passthrough with SSE streaming
- Token counting via llama.cpp `/tokenize` with hash-based caching
- Response headers: `X-Axon-Tokens-In`, `X-Axon-Budget-Pct`
- `GET /axon/status`, `GET /axon/health`
- JSON structured logging
- Dockerfile + docker-compose integration
- `axon.toml` configuration

**Exit gate:** Deploy in Nyx. Agent operates normally. One week of observability data reveals actual context utilization patterns and waste.

### Phase 2: Manage (weeks 3-4)

Context management based on Phase 1 data.

- System prompt hash caching
- Configurable context truncation at budget threshold
- Importance-based turn preservation
- Agent-visible truncation markers + `[KEEP]` support
- Tool output compression (ANSI strip, line dedup, truncation markers)
- Update `inference-check.sh` to query Axon

**Exit gate:** Measurable reduction in context waste. No increase in tool call volume. Agent task completion unchanged.

### Phase 3: Cache (weeks 5-6)

Optimize for llama.cpp KV cache.

- Prefix-stable message ordering (truncate middle, preserve edges)
- Tool output dedup with TTL
- KV cache hit rate tracking (via llama.cpp `/slots` if available)

**Exit gate:** Measurable reduction in time-to-first-token on sequential requests.

### Phase 4: Inject (week 7)

Budget-aware context injection.

- File-based injection rules in `axon.toml`
- Budget threshold triggers
- Injection content marked clearly

**Exit gate:** Agent demonstrates improved orientation after session resets.

---

## Open Questions

1. **Tokenizer locality.** Using llama.cpp `/tokenize` adds a network round trip per unique content. Should Axon embed a local Qwen tokenizer for speed? Tradeoff: accuracy (llama.cpp is authoritative) vs. latency (local is faster).

2. **Session identity.** How does Axon identify which requests belong to the same session? Options: parse session ID from OpenClaw headers, hash system prompt + first message as fingerprint, or use a configurable header.

3. **Multi-model support.** If Nyx ever runs multiple models (different context windows), Axon needs per-model budget config. Out of scope for Phase 1, but the config structure should accommodate it.

4. **Abstractive summarization.** Phase 1-2 use extractive compaction (keep key lines, drop noise). Phase 3+ could use the LLM itself to summarize older turns. This uses inference capacity — worth it? Needs benchmarking.
