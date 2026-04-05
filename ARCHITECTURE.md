# Architecture: Base Layer Transparency

## The Problem with Pure Nix for Node Apps

Nix guarantees reproducibility through fixed-output derivations (FOD) — cryptographic hashes of every dependency's source tree. This works beautifully for stable C/Python ecosystems.

It breaks for fast-moving npm packages like OpenClaw. Every transitive dependency update shatters the FOD hash. Maintaining those hashes manually is operationally fatal for end users.

## The Solution: Two Explicit Layers

Rather than fighting npm with Nix purity, we split the container across two boundaries:

### Layer 1: OS Base (Pure Nix — multi-stage builder)
`container/Dockerfile` Stage 1 uses `nixos/nix` to build the `base-content` derivation from `flake.nix`. This produces a directory of symlinks into the Nix store containing:
- Exact, pinned versions of Node.js, Python, gcc, cmake, git
- An optional `bombon`-generated cryptographic SBOM of the full dependency graph

This stage has zero transitive app-layer network dependencies — it is the pinned, auditable part of the image and Docker-cached. It only reruns when `flake.nix` or `flake.lock` change.

### Layer 2: Application (Docker)
Stage 2 starts from `debian:bookworm-slim`, copies `/nix/store` from the builder, and runs:
```
npm install -g openclaw@<resolved-version> @qwen-code/qwen-code@<resolved-version>
```

This uses the Nix-pinned Node.js (via PATH → `/nix-env/bin`), so the runtime version is still controlled by `flake.lock`. npm handles its own dependency graph, and `just build` resolves floating tags to concrete versions before invoking Docker so the resulting image is labeled with the actual app versions used.

**Synapse** lives one layer earlier — it's a `buildPythonApplication` derivation inside `flake.nix`, pinned by `fetchFromGitHub` rev + sha256, built into the Nix store alongside git/jq/ripgrep, and included in `basePaths`. The `synapse-mcp`, `synapse-index`, and `synapse-search` binaries land on PATH via `/nix-env/bin` with zero stage-2 work. Bumping synapse is a one-shot flow: `just update-synapse` fetches the latest `main` commit, prefetches its tarball hash via `nix-prefetch-github`, and rewrites `flake.nix` in place. `just build` then reads the resolved rev via `nix eval .#synapse.src.rev` and forwards it as a metadata label (`io.github.netlooker.nyx.synapse.version`) — the value is documentation only, the actual pin lives in the flake. This placement is deliberate: synapse is a slow-moving first-party dependency that belongs in the reproducible base layer, not the thin app layer.

**SearXNG** sits on the other side of that boundary for now. It is not pinned in `flake.nix` and it is not installed into the Nyx image. Instead, Nyx runs it as a private compose sidecar with a tracked `container/searxng/settings.yml` and an internal service URL (`http://searxng:8080`). That separation is intentional: Sonar can be battle-tested against a live-web substrate inside the Nyx stack without coupling Nyx startup, rebuilds, or failure modes to SearXNG more tightly than necessary.

Debian is intentional here. It is the compatibility layer for the current appliance model: a simple runtime base with Nix-pinned tools and a floating npm-installed app layer. A fully Nix-native runtime image stays possible, but it becomes a cleaner trade once OpenClaw/Qwen are packaged as fixed-input derivations instead of `latest` npm installs.

### The Boundary Matters for Agent Workspaces
OpenClaw's agent sandboxes live under `OPENCLAW_STATE_DIR` (`/data`, volume-mounted). When an agent installs packages for a coding task, it works in its own sandbox directory with its own `node_modules` and Python venvs. The container's global `openclaw` installation is never touched.

```
/usr/local/lib/node_modules/openclaw/  ← container (Nix-controlled Node + npm install)
/data/sandboxes/<agent>/node_modules/  ← agent workspace (isolated, disposable)
```

## Configuration Hot-Reloading

Config is mounted as a **directory** (`secrets/` → `/config`), not a single file.

Why: OpenClaw rewrites its config atomically via `rename()`. A file-level bind mount locks the inode — `rename()` gets `EBUSY` and crashes the container. A directory mount gives OpenClaw the namespace it needs to perform the swap cleanly.

Result: edit `secrets/openclaw.json5` on your Mac → OpenClaw hot-reloads inside the container via `fs.watch`. No rebuild required.

## Secrets Management

Credentials are split across two gitignored files in `secrets/`:

- `secrets/openclaw.json5` — agent config (hot-reloaded, readable by the agent)
- `secrets/.env` — environment variables injected via `env_file` in docker-compose (gateway password, API keys)

Sensitive values like `OPENCLAW_GATEWAY_PASSWORD` belong in `.env`, not in the JSON5 config. The agent can read its own config file — anything in there is visible to it.

## Tool Config Persistence (entrypoint.sh)

The entrypoint (`container/entrypoint.sh`) runs before openclaw starts, after the `/data` volume is mounted. It handles two things:

**1. Workspace structure.** Creates `services/`, `tools/`, `projects/`, and `vault/` under `/data/workspace` and seeds `WORKSPACE.md` on first boot (from `container/WORKSPACE.md` baked into the image at `/app/WORKSPACE.md`). The seed is a one-time copy — manual edits to the workspace copy are preserved. The `vault/` directory is the default Synapse index target.

**2. Agent skills.** Skills are baked into `/app/skills` at build time (from `.agents/skills/` in the repo) and symlinked into `/data/workspace/.agents/skills`. The symlink points at the image copy, so container rebuilds deliver updated skills automatically. Skills teach the agent how to use GitHub CLI, Qwen Code, Synapse MCP tools, and navigate the workspace.

**3. Tool config symlinks.** Some tools hardcode `$HOME/.<toolname>` with no env override:

```sh
mkdir -p /data/qwen
ln -sf /data/qwen /root/.qwen
```

The tool sees `~/.qwen` as normal. The data actually lives on the persistent volume. Adding support for a new tool follows the same pattern — one `mkdir` and one `ln -sf` in `entrypoint.sh`.

## Data Persistence

`data/` on Mac → `/data` in the container. Contains:
- OpenClaw databases and session state
- Agent sandbox directories
- Downloaded files and memory
- Agent workspace (`/data/workspace`) — structured as `services/` (long-running UIs/APIs), `tools/` (CLIs), `projects/` (git repos)
- GitHub CLI auth (`/data/gh`) — `gh` token survives rebuilds
- Qwen-Coder config (`/data/qwen`) — `qwen` settings survive rebuilds

The container is ephemeral. The data is not.

That persistence contract is the product:
- rebuild the image and the agent comes back with the same `/data`
- rebuild the image and agent skills are updated via the `/app/skills` symlink
- restart the container and hardcoded tool config is reattached automatically
- edit host config under `secrets/` and OpenClaw hot-reloads it without an image rebuild

## Build Metadata and Optional SBOM Discovery

Nyx always writes `/app/build-info.json` with the selected Nix system plus the requested and resolved OpenClaw/Qwen versions. By default, the build skips `bombon` so rebuilds stay fast. If you opt in with the SBOM build path, Nyx also publishes the base-layer SBOM at `/app/sbom-base.json` and points to it from image metadata.

For users, that means:
- inspect the image labels to discover the build-info location and whether SBOM generation was enabled
- inspect `/app/build-info.json` if you need the exact resolved app versions used at build time
- use the SBOM-specific build path only when you actually need the heavier compliance artifact
