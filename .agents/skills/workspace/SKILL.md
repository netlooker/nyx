---
name: workspace
description: Persistent workspace folder structure, conventions, and where to put things.
user-invocable: true
disable-model-invocation: false
---

# Workspace Layout

The persistent workspace at `/data/workspace` survives container rebuilds. Everything outside `/data` is ephemeral.

## Folder structure

```
workspace/
├── projects/      — git repos (each manages its own venv/node_modules)
│   ├── synapse/           — semantic retrieval engine for markdown vaults
│   └── netlooker.github.io/  — static site
├── tools/         — CLIs, scripts, standalone utilities
│   └── arxiv-harvester/   — ArXiv paper fetcher (stdlib-only Python)
├── services/      — long-running processes with UI or API
├── vault/         — markdown knowledge base (indexed by Synapse)
├── ingestion_vault/ — ingested content (ArXiv papers as markdown)
├── cortex/        — agent state and working memory
├── memory/        — session memory files (YYYY-MM-DD.md)
├── WORKSPACE.md   — this structure's canonical reference
├── AGENTS.md      — agent behavior rules, memory management, red lines
├── SOUL.md        — core values and boundaries
├── IDENTITY.md    — agent identity template (name, creature, vibe)
├── USER.md        — user context (name, timezone)
├── BOOTSTRAP.md   — first-run setup guide
├── TOOLS.md       — environment-specific tool notes
└── HEARTBEAT.md   — active tasks and check-in schedule
```

## Rules

- **Projects**: clone repos into `projects/`. Each project owns its dependencies.
- **Tools**: install CLIs into `tools/`, one subdirectory per tool.
- **Services**: anything that exposes a port or runs continuously goes in `services/`.
- **Vault**: markdown notes for the knowledge base. Synapse indexes this folder.
- **Scratch files**: workspace root is OK temporarily — clean up when done.
- **No loose code** at the workspace root.

## Persistence boundaries

| Path | Persists | Purpose |
|------|----------|---------|
| `/data/workspace/` | Yes (volume) | All agent work |
| `/data/qwen/` | Yes (volume) | Qwen Code state and config |
| `/data/gh/` | Yes (volume) | GitHub CLI auth |
| `/config/` | Yes (bind mount) | Secrets, settings files |
| `/app/` | No (image) | Build artifacts, seed files |
| Everything else | No (image) | Container OS, tools, runtimes |

## Key integrations

- **Synapse** indexes `vault/` and `ingestion_vault/` — run `synapse_index` after adding notes
- **Qwen Code** sees the filesystem — `cd` to the right project before invoking
- **Git repos** in `projects/` can be pushed/pulled via `gh` (auth persists in `/data/gh/`)
