# Sonar -> Synapse E2E

This is the hybrid Nyx end-to-end scenario for:

1. rebuilding Nyx from the current repo state
2. driving the main interaction through `openclaw tui`
3. forcing the agent to use Sonar to find 5 scientific papers
4. ingesting those papers into a dedicated Synapse vault + DB
5. extracting grounded cross-paper insights
6. verifying the result from persisted artifacts, the Synapse DB, and the OpenClaw session log

## What It Creates

Each run gets a unique id and a dedicated subtree under:

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
    summary.json
    summary.md
    final_answer.md
    selected_sources.json
    sonar_shortlist.json
    tool_events.json
    db_summary.json
  manifest.json
  synapse.sqlite
```

The harness never uses the shared `/data/workspace/vault` or its existing `.synapse.sqlite`.

## Commands

Prepare a run against the current live stack:

```bash
just e2e-sonar-synapse-prepare
```

Prepare a run and rebuild Nyx first:

```bash
just e2e-sonar-synapse-prepare-rebuild
```

That prints the generated `test_id` and writes the exact interactive TUI command to:

```text
data/workspace/e2e/<test_id>/artifacts/openclaw-tui-command.sh
```

Run that command as-is. It opens `openclaw tui` with:

- a dedicated session key
- the canonical operator prompt already injected
- the required Sonar -> Synapse constraints baked in

After the TUI scenario finishes, verify it:

```bash
just e2e-sonar-synapse-verify <test_id>
```

## What The Verifier Checks

- active OpenClaw and Qwen configs both declare `sonar` and `synapse`
- Nyx and SearXNG containers are running
- the gateway is reachable
- rebuilt container exposes:
  - `/app/skills/sonar/SKILL.md`
  - `/app/skills/synapse/SKILL.md`
  - `sonar-mcp`
  - `synapse-mcp`
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
- the session transcript includes the expected tool calls:
  - `sonar__sonar_health`
  - `sonar__sonar_search`
  - `sonar__sonar_fetch`
  - `sonar__sonar_extract`
  - `synapse__synapse_health`
  - `synapse__synapse_index`
  - `synapse__synapse_search`
- `synapse_health`, `synapse_index`, and `synapse_search` target the dedicated vault/DB
- the final answer contains:
  - exactly 5 selected papers
  - 3-5 cross-paper insights
  - citations back to note filenames or source URLs

## Rebuild Requirement

The current live container must be rebuilt before this e2e is considered valid if it does not expose:

- the `sonar` skill under `/app/skills`
- the `sonar-mcp` binary
- an active OpenClaw MCP server entry for `sonar`

`just e2e-sonar-synapse-prepare-rebuild` is the intended entrypoint for a clean validation pass.
