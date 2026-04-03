# NYX

> *Ghost in the grid. Your AI agent, your hardware, your rules.*

Nyx is a Nix-backed deployment chassis for [OpenClaw](https://openclaw.ai) — an autonomous AI agent that lives on **your** infrastructure, speaks over Telegram and WhatsApp, and thinks with whatever inference engine you point it at.

No cloud subscriptions. No data leaving your rack. No surprises.

The base toolchain is compiled by Nix — Node.js, Python, git, build tools, and utilities are pinned by `flake.lock`. On top of that pinned base, OpenClaw and Qwen are installed in the container image at build time. Nyx captures the requested app versions in image metadata and keeps the runtime state in mounted volumes so rebuilds do not wipe the agent's memory, sessions, or tool config.

---

## The Philosophy: Clone → Config → Bake → Run

### 1. Clone

```bash
git clone <this-repo> && cd nyx
```

### 2. Config

Drop your credentials into the heavily-gitignored `secrets/openclaw.json5`:

```bash
cp cortex/openclaw.json5.example secrets/openclaw.json5
$EDITOR secrets/openclaw.json5
```

Wire up your inference node (Ollama, llama.cpp, any OpenAI-compatible endpoint) and your messaging channels (Telegram bot token, WhatsApp). Full config reference in [GUIDE.md](GUIDE.md).

### 3. Bake

```bash
just build
```

A single command. `just build` resolves the current OpenClaw and Qwen releases, passes those concrete versions into Docker, and labels the resulting image with the chosen app versions plus the selected Nix system. Stage 1 runs inside `nixos/nix` and produces the pinned base layer. Stage 2 keeps the current appliance model: Debian-slim runtime, Nix-pinned tools, OpenClaw on top.

The default image build is optimized for fast rebuilds and does not generate an SBOM. Nyx always writes `/app/build-info.json` and labels the image with the selected Nix system plus the resolved app versions. If you want the heavier compliance path, use `just build-sbom`.

### 4. Run

```bash
just up
just logs
```

Two volumes keep your agent alive across rebuilds:

| Host | Container | Purpose |
|---|---|---|
| `secrets/` | `/config` | Hot-reloadable config — edit on your machine, agent picks it up live |
| `data/` | `/data` | Agent memory, workspace, sessions, sandboxes, gh auth — your backup lives here |

Push the image to any cloud registry. Deploy to any orchestrator. It's just a container.

The appliance contract is the point:
- edit `secrets/openclaw.json5` on the host and OpenClaw hot-reloads it in place
- rebuild the image and the agent comes back with the same `/data` state
- tool config that insists on `$HOME` is reattached automatically by `entrypoint.sh`

---

## Structure

```
flake.nix              — Nix derivation: pins Node.js, Python, gcc, cmake + optional SBOM derivation
flake.lock             — Cryptographic lockfile — the single source of truth for versions
cortex/
  Dockerfile               — Multi-stage build: Nix base → Debian-slim + OpenClaw/Qwen metadata
  docker-compose.yml       — Volume mounts, port bindings, build args, env_file for secrets
  entrypoint.sh            — Symlinks tool configs into /data before openclaw starts
  openclaw.json5.example   — Template config — copy to secrets/ and fill in your values
secrets/               — Gitignored. Config, env vars, and credentials live here.
  openclaw.json5       — OpenClaw config (hot-reloaded)
  .env                 — Environment variables (gateway password, API keys)
data/                  — Gitignored. Agent memory, sessions, sandboxes, and tool state persist here.
justfile               — Task runner: build / build-sbom / build-base / up / down / logs / status / check
```

---

## Useful Commands

```bash
just build-base # build + load the standalone Nix base image
just build     # fast default build: pinned base + resolved app versions
just build-sbom # opt-in build that also generates the bombon SBOM artifact
just check     # validate compose config, shell syntax, flake outputs
just up        # start the agent
just down      # stop the agent
just logs      # tail live output
just rebuild   # full rebuild from scratch — no cache
just restart   # restart without rebuilding
just status    # show openclaw status (channels, sessions, context usage)
```

Agent dashboard at `http://localhost:18789` (enable `gateway.bind: 'lan'` + password via `secrets/.env`).

Set `NYX_NIX_SYSTEM=x86_64-linux` on x86 Docker hosts. Apple Silicon keeps the default `aarch64-linux`.

For SBOM lovers, `just build-sbom` turns the compliance path back on and writes `/app/sbom-base.json`.

---

## Deep Dives

- [GUIDE.md](GUIDE.md) — Telegram pairing, WhatsApp QR auth, config reference
- [ARCHITECTURE.md](ARCHITECTURE.md) — Why Nix + Docker, how the two-layer boundary works, hot-reload internals
