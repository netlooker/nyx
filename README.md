# NYX

> *Ghost in the grid. Your AI agent, your hardware, your rules.*

Nyx is a Docker Compose deployment chassis for [OpenClaw](https://openclaw.ai) or [Hermes Agent](https://github.com/NousResearch/hermes-agent) — autonomous agents that live on **your** infrastructure and think with whatever inference engine you point them at.

No cloud subscriptions. No data leaving your rack. No surprises.

The runtime image is a plain Debian-based container. OpenClaw and Qwen Code are installed with npm, Hermes/Synapse/Sonar/Scrapling are installed with uv, and selected versions are captured in Docker labels plus `/app/build-info.json`. Persistent state lives in mounted volumes, so rebuilds do not wipe agent memory, sessions, tool config, or browser backends.

## Orchestrator Architecture

- **OpenClaw** — orchestrator option for conversations, messaging channels, tool use, and long-running tasks.
- **Hermes Agent** — orchestrator option for gateway conversations, MCP integrations, toolsets, and long-running tasks.
- **Qwen Code** — a headless sub-agent. OpenClaw and Hermes can delegate heavy or independent tasks to Qwen via CLI.

All agents share the same local inference server: llama.cpp, Ollama, or any OpenAI-compatible endpoint.

## Clone, Config, Build, Run

Prerequisites are Docker with Compose and `just`. There is no project-level
Nix setup step.

```bash
git clone <this-repo> && cd nyx
```

Create local config under the gitignored `secrets/` directory:

```bash
mkdir -p secrets
cp container/openclaw.json5.example secrets/openclaw.json5
cp container/hermes.yaml.example secrets/hermes.yaml
cp container/hermes.env.example secrets/hermes.env
cp container/qwen.json5.example secrets/qwen-settings.json
# optional overrides
cp container/synapse.toml.example secrets/synapse.toml
cp container/sonar.toml.example secrets/sonar.toml
printf 'NYX_ORCHESTRATOR=openclaw\n' > secrets/.env
$EDITOR secrets/openclaw.json5
$EDITOR secrets/hermes.yaml
$EDITOR secrets/qwen-settings.json
```

Set `NYX_ORCHESTRATOR=openclaw` or `NYX_ORCHESTRATOR=hermes` in `secrets/.env`.

`openclaw.json5` configures OpenClaw mode. `hermes.yaml` and `hermes.env` configure Hermes mode. `qwen-settings.json` configures the Qwen Code sub-agent. Prefer absolute MCP command paths such as `/usr/local/bin/sonar-mcp` and `/usr/local/bin/synapse-mcp`.

Build and run:

```bash
just build
just up
just logs
```

The OpenClaw dashboard is available at `http://localhost:18789` when gateway binding/auth are enabled in config. Hermes mode does not expose a Nyx-managed dashboard in this pass.

## Version Selection

Tracked defaults live in `versions.env`:

```dotenv
NODE_MAJOR=22
UV_VERSION=0.12.5
OPENCLAW_VERSION=latest
QWEN_CODE_VERSION=latest
SCRAPLING_VERSION=latest
HERMES_REF=main
SYNAPSE_REF=main
SONAR_REF=main
```

`just build` resolves floating selectors to concrete versions or commits before Docker runs, then records the resolved values in image labels and `/app/build-info.json`.

## Runtime Contract

| Host | Container | Purpose |
|---|---|---|
| `secrets/` | `/config` | Orchestrator config and local overrides |
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
  entrypoint.sh         — workspace/config setup before the selected orchestrator starts
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
