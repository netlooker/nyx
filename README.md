# NYX

> *Ghost in the grid. Your AI agent, your hardware, your rules.*

Nyx is a reproducible deployment chassis for [OpenClaw](https://openclaw.ai) — an autonomous AI agent that lives on **your** infrastructure, speaks over Telegram and WhatsApp, and thinks with whatever inference engine you point it at.

No cloud subscriptions. No data leaving your rack. No surprises.

The base OS is compiled by Nix — every binary pinned, every dependency hashed, every version locked to the nanosecond. A cryptographic SBOM ships inside the image so you can prove exactly what's running. On top of that pristine foundation, OpenClaw is layered in via Docker. One command bakes the whole stack.

---

## The Philosophy: Clone → Config → Bake → Run

### 1. Clone

```bash
git clone <this-repo> && cd nyx
```

### 2. Config

Drop your credentials into the heavily-gitignored `secrets/openclaw.json5`:

```bash
cp secrets/openclaw.json5.example secrets/openclaw.json5
$EDITOR secrets/openclaw.json5
```

Wire up your inference node (Ollama, llama.cpp, any OpenAI-compatible endpoint) and your messaging channels (Telegram bot token, WhatsApp). Full config reference in [GUIDE.md](GUIDE.md).

### 3. Bake

```bash
just build
```

A single command. Stage 1 runs inside `nixos/nix` — Nix resolves the dependency graph, pins every compiler and runtime to a cryptographic hash, and hands off a mathematically deterministic toolchain. Stage 2 layers OpenClaw on top using that pinned Node.js. Docker caches Stage 1 — it only reruns when `flake.nix` or `flake.lock` change. Hot-swapping OpenClaw versions is instant.

The resulting image carries a full SBOM. You can audit every binary in the base layer.

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

---

## Structure

```
flake.nix              — Nix derivation: pins Node.js, Python, gcc, cmake + generates SBOM
flake.lock             — Cryptographic lockfile — the single source of truth for versions
cortex/
  Dockerfile           — Multi-stage build: Nix base → Debian-slim + openclaw
  docker-compose.yml   — Volume mounts, port bindings
  entrypoint.sh        — Symlinks tool configs into /data before openclaw starts
secrets/               — Gitignored. Your keys live here.
data/                  — Gitignored. Agent memory persists here.
justfile               — Task runner: build / up / down / logs / rebuild
```

---

## Useful Commands

```bash
just build     # compile the full stack (Nix base + openclaw)
just up        # start the agent
just down      # stop the agent
just logs      # tail live output
just rebuild   # full rebuild from scratch — no cache
just restart   # restart without rebuilding
```

Agent dashboard at `http://localhost:18789` (enable `gateway.bind: 'lan'` + password in config).

---

## Deep Dives

- [GUIDE.md](GUIDE.md) — Telegram pairing, WhatsApp QR auth, config reference
- [ARCHITECTURE.md](ARCHITECTURE.md) — Why Nix + Docker, how the two-layer boundary works, hot-reload internals
