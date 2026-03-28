# Architecture: Base Layer Transparency

## The Problem with Pure Nix for Node Apps

Nix guarantees reproducibility through fixed-output derivations (FOD) — cryptographic hashes of every dependency's source tree. This works beautifully for stable C/Python ecosystems.

It breaks for fast-moving npm packages like OpenClaw. Every transitive dependency update shatters the FOD hash. Maintaining those hashes manually is operationally fatal for end users.

## The Solution: Two Explicit Layers

Rather than fighting npm with Nix purity, we split the container across two boundaries:

### Layer 1: OS Base (Pure Nix — multi-stage builder)
`cortex/Dockerfile` Stage 1 uses `nixos/nix` to build the `base-content` derivation from `flake.nix`. This produces a directory of symlinks into the Nix store containing:
- Exact, pinned versions of Node.js, Python, gcc, cmake, git
- A `bombon`-generated cryptographic SBOM of the full dependency graph

This stage has zero transitive network dependencies — it's mathematically deterministic and Docker-cached. It only reruns when `flake.nix` or `flake.lock` change.

### Layer 2: Application (Docker)
Stage 2 starts from `debian:bookworm-slim`, copies `/nix/store` from the builder, and runs:
```
npm install -g openclaw@latest @qwen-code/qwen-code@latest
```

This uses the Nix-pinned Node.js (via PATH → `/nix-env/bin`), so the runtime version is still controlled by `flake.lock`. npm handles its own dependency graph — no FOD hash maintenance required.

Everything is self-contained in a single `docker compose build`. No separate base-image build step.

### The Boundary Matters for Agent Workspaces
OpenClaw's agent sandboxes live under `OPENCLAW_STATE_DIR` (`/data`, volume-mounted). When an agent installs packages for a coding task, it works in its own sandbox directory with its own `node_modules` and Python venvs. The cortex's global `openclaw` installation is never touched.

```
/usr/local/lib/node_modules/openclaw/  ← cortex (Nix-controlled Node + npm install)
/data/sandboxes/<agent>/node_modules/  ← agent workspace (isolated, disposable)
```

## Configuration Hot-Reloading

Config is mounted as a **directory** (`secrets/` → `/config`), not a single file.

Why: OpenClaw rewrites its config atomically via `rename()`. A file-level bind mount locks the inode — `rename()` gets `EBUSY` and crashes the container. A directory mount gives OpenClaw the namespace it needs to perform the swap cleanly.

Result: edit `secrets/openclaw.json5` on your Mac → OpenClaw hot-reloads inside the container via `fs.watch`. No rebuild required.

## Data Persistence

`data/` on Mac → `/data` in the container. Contains:
- OpenClaw databases and session state
- Agent sandbox directories
- Downloaded files and memory
- Agent workspace (`/data/workspace`) — personality, notes, memory files survive rebuilds
- GitHub CLI auth (`/data/gh`) — `gh` token survives rebuilds

The container is ephemeral. The data is not.
