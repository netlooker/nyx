# Sonar -> Synapse E2E

This e2e is now intentionally split into two phases:

1. a deterministic, model-agnostic Sonar collection phase
2. a smaller `openclaw tui` phase that only writes notes, runs Synapse, and synthesizes insights

That split exists because the fragile part was not Sonar itself. Sonar is already deterministic. The fragile part was asking the live model in TUI to drive `sonar_search` / `sonar_fetch` / `sonar_extract` correctly for a long multi-step paper-selection flow.

## Why This Flow

The goal is still the same:

1. isolate a run under `data/workspace/e2e/<test_id>/`
2. find exactly 5 scientific papers relevant to the query
3. ingest them into a dedicated vault and dedicated Synapse DB
4. extract grounded cross-paper insights
5. verify everything from persisted artifacts, the Synapse DB, and the OpenClaw session log

What changed is who does what:

- Sonar collection is done by the harness directly, without relying on the chat model
- the TUI phase is narrower and more stable across models like Qwen

## What It Creates

Each run gets a unique subtree under:

```text
data/workspace/e2e/<test_id>/
  ingestion_vault/
    paper-01.md
    paper-02.md
    paper-03.md
    paper-04.md
    paper-05.md
  artifacts/
    prompt.txt
    openclaw-tui-command.sh
    preflight.json
    source_manifest.json
    source_collection.log
    sources/
      paper-01.json
      paper-01.txt
      ...
      paper-05.json
      paper-05.txt
    summary.json
    summary.md
    final_answer.md
    selected_sources.json
    sonar_shortlist.json
    tool_events.json
    db_summary.json
  manifest.json
  sonar.sqlite
  synapse.sqlite
```

The harness never uses the shared `/data/workspace/vault`, `/data/workspace/ingestion_vault`, or any old Synapse DB.

## Commands

Prepare a run against the current live stack:

```bash
just e2e-sonar-synapse-prepare
```

This does all of the following by default:

- creates the isolated run layout
- optionally validates the stack with preflight
- runs deterministic Sonar paper collection into `artifacts/source_manifest.json`
- writes the canonical TUI prompt and exact `openclaw tui` launch script

Prepare a run and rebuild Nyx first:

```bash
just e2e-sonar-synapse-prepare-rebuild
```

If you need to re-run only the deterministic Sonar collection phase for an existing run:

```bash
just e2e-sonar-synapse-collect-sources <test_id>
```

The generated TUI command is written to:

```text
data/workspace/e2e/<test_id>/artifacts/openclaw-tui-command.sh
```

Run that command as-is. It opens `openclaw tui` with:

- a dedicated session key
- the canonical operator prompt already injected
- instructions to consume only the prepared source manifest and source files
- the Synapse-only task flow baked in
- a longer agent timeout

If a run times out or stalls, do not reuse the same session. Generate a fresh `test_id` and run the newly generated command.

After the TUI phase finishes, verify it:

```bash
just e2e-sonar-synapse-verify <test_id>
```

## Phase 1: Deterministic Sonar Collection

The harness runs Sonar directly inside the Nyx container with a dedicated per-run `sonar.sqlite`.

It:

- checks Sonar runtime readiness
- runs several paper-oriented searches
- filters toward direct paper landing pages
- fetches and extracts candidate papers
- persists exactly 5 selected sources under `artifacts/sources/`
- records the fixed input set in `artifacts/source_manifest.json`

This phase is model-agnostic. No LLM is involved in Sonar search, fetch, or extraction.

The current collector is intentionally conservative:

- it prefers direct `arxiv.org/abs/...` pages
- it rejects weak or non-paper-like results
- it fails if it cannot produce 5 extractable direct paper pages

## Phase 2: OpenClaw TUI + Synapse

The TUI prompt no longer asks the model to search the web. It instead tells the agent to:

1. read `artifacts/source_manifest.json`
2. read the prepared `paper-0N.json` or `paper-0N.txt` files
3. call `synapse_health_for_workspace(workspace="current")`
4. write exactly 5 markdown notes into the dedicated `ingestion_vault`
5. call `synapse_index_for_workspace(workspace="current")`
6. call `synapse_search_for_workspace(workspace="current", mode="hybrid")`
7. optionally call `synapse_discover`
8. produce 3-5 grounded cross-paper insights

The narrowed prompt now prefers the pathless workspace facade from Synapse `a3b4dc8`, because local-model runtimes were repeatedly corrupting raw filesystem-path fields before the request ever reached the MCP server.

This reduction is what makes the e2e more model-tolerant. The model only has to do note synthesis, indexing, retrieval, and final explanation.

## What The Verifier Checks

- active OpenClaw and Qwen configs both declare `sonar` and `synapse`
- Nyx and SearXNG containers are running
- the gateway is reachable
- rebuilt container exposes:
  - `/app/skills/sonar/SKILL.md`
  - `/app/skills/synapse/SKILL.md`
  - `sonar-mcp`
  - `synapse-mcp`
- the prepared source manifest exists and names exactly 5 selected sources
- each prepared source JSON and text artifact exists
- exactly 5 notes exist under the dedicated ingestion vault
- filenames match `paper-01.md` through `paper-05.md`
- each note contains:
  - `TEST_ID`
  - `QUERY`
  - `SOURCE_URL`
  - `TITLE`
  - `AUTHORS`
  - `PUBLISHED`
  - `RETRIEVED_AT`
  - `## Abstract`
  - `## Extract`
  - `## Why Selected`
- the dedicated Synapse DB exists
- the DB contains exactly 5 indexed documents and chunk rows
- the session transcript includes the expected Synapse tool calls:
  - `synapse__synapse_health_for_workspace`
  - `synapse__synapse_index_for_workspace`
  - `synapse__synapse_search_for_workspace`
- the workspace-handle Synapse calls all use `workspace="current"`
- `synapse_search_for_workspace` uses `mode="hybrid"` with a real top-level `query`
- the final answer contains:
  - exactly 5 selected papers
  - 3-5 cross-paper insights
  - citations back to note filenames or source URLs

The verifier does not require `sonar_*` tool calls in the transcript anymore, because Sonar now runs deterministically before the TUI phase.

## Rebuild Requirement

`just e2e-sonar-synapse-prepare-rebuild` is still the cleanest entrypoint when the live container is stale.

A valid rebuilt image should expose:

- the `sonar` and `synapse` skills under `/app/skills`
- the `sonar-mcp` and `synapse-mcp` binaries
- active MCP registrations for both `sonar` and `synapse`

## Practical Notes

- If you want to debug only the TUI/Synapse phase, you can reuse an existing run and skip source collection.
- If deterministic source collection fails, inspect `artifacts/source_collection.log` and `artifacts/source_manifest.json` first.
- If the model still misbehaves during the TUI phase, the prepared source manifest keeps the failure surface small and reproducible.
