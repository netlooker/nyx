# NYX

> *Ghost in the grid. Your AI agent, your hardware, your rules.*

Nyx is a Docker Compose deployment chassis for [OpenClaw](https://openclaw.ai) — an autonomous AI agent that lives on **your** infrastructure, speaks over Telegram and WhatsApp, and thinks with whatever inference engine you point it at.

No cloud subscriptions. No data leaving your rack. No surprises.

The runtime image is a plain Debian-based container. OpenClaw and Qwen Code are installed with npm, Synapse/Sonar/Scrapling are installed with uv, and selected versions are captured in Docker labels plus `/app/build-info.json`. Persistent state lives in mounted volumes, so rebuilds do not wipe agent memory, sessions, tool config, or browser backends.

## Dual-Agent Architecture

- **OpenClaw** — the primary agent. Handles conversations, messaging channels, tool use, and long-running tasks.
- **Qwen Code** — a headless sub-agent. OpenClaw delegates heavy or independent tasks to Qwen via CLI (`qwen -p "task" --output-format text`).

Both agents share the same local inference server: llama.cpp, Ollama, or any OpenAI-compatible endpoint.

## Clone, Config, Build, Run

Prerequisites are Docker with Compose and `just`. There is no project-level
Nix setup step.

```bash
git clone <this-repo> && cd nyx
```

Create local config under the gitignored `secrets/` directory:

```bash
cp container/openclaw.json5.example secrets/openclaw.json5
cp container/qwen.json5.example secrets/qwen-settings.json
# optional overrides
cp container/synapse.toml.example secrets/synapse.toml
cp container/sonar.toml.example secrets/sonar.toml
$EDITOR secrets/openclaw.json5
$EDITOR secrets/qwen-settings.json
```

`openclaw.json5` is the primary config. `qwen-settings.json` configures the Qwen Code sub-agent. Prefer absolute MCP command paths such as `/usr/local/bin/sonar-mcp` and `/usr/local/bin/synapse-mcp`.

Build and run:

```bash
just build
just up
just logs
```

The dashboard is available at `http://localhost:18789` when gateway binding/auth are enabled in config.

## Version Selection

Tracked defaults live in `versions.env`:

```dotenv
NODE_MAJOR=22
UV_VERSION=0.11.2
OPENCLAW_VERSION=latest
QWEN_CODE_VERSION=latest
SCRAPLING_VERSION=latest
SYNAPSE_REF=main
SONAR_REF=main
```

`just build` resolves floating selectors to concrete versions or commits before Docker runs, then records the resolved values in image labels and `/app/build-info.json`.

## Runtime Contract

| Host | Container | Purpose |
|---|---|---|
| `secrets/` | `/config` | Hot-reloadable config |
| `data/` | `/data` | Agent state, sessions, sandboxes, gh auth, Scrapling browser caches |

`just up` also starts a private `searxng` sidecar on the internal compose network. Sonar reaches it at `http://searxng:8080`.

## Structure

```text
versions.env            — build selectors resolved by just
.agents/skills/         — agent skills shipped with the image
.github/workflows/      — CI: checks, image build, metadata verification
container/
  Dockerfile            — Debian runtime + npm/uv installed tools
  docker-compose.yml    — volume mounts, ports, build args, env_file
  entrypoint.sh         — workspace/config setup before OpenClaw starts
  *.example             — config templates
  searxng/settings.yml  — private SearXNG sidecar defaults
  WORKSPACE.md          — seeded into /data/workspace on first boot
secrets/                — gitignored credentials and config
data/                   — gitignored persistent runtime state
justfile                — build / up / down / logs / status / check
```

## Useful Commands

```bash
just build
just check
just up
just down
just logs
just restart
just rebuild
just status
just e2e-sonar-synapse-prepare
just e2e-sonar-synapse-prepare-rebuild
just e2e-sonar-synapse-collect-sources <test_id>
just e2e-sonar-synapse-verify <test_id>
```

## Deep Dives

- [GUIDE.md](GUIDE.md) — setup, pairing, and config reference
- [ARCHITECTURE.md](ARCHITECTURE.md) — Docker runtime, persistence, and metadata
- [E2E_SONAR_SYNAPSE.md](E2E_SONAR_SYNAPSE.md) — deterministic Sonar collection plus TUI/Synapse verification
- [patches/openclaw-2026.5.7-llamacpp-usage.md](patches/openclaw-2026.5.7-llamacpp-usage.md) — temporary OpenClaw `2026.5.7` llama.cpp streaming usage workaround
- [PRD.md](PRD.md) — product requirements and design notes
