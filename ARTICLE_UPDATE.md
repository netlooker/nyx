# // OPERATION: CORTEX UPGRADE
**TARGET:** NYX CORTEX (RUNNING INSTANCE)
**OBJECTIVE:** ZERO DATA LOSS UPDATE ACROSS ALL LAYERS
**OPERATOR:** NETRUNNER

Your cortex is live. Your agent is talking. Now the question every operator faces: *how do you upgrade without blowing up your state?*

Nyx has three independent layers. Each updates differently. Get this wrong and you're re-pairing Telegram and re-authing GitHub from scratch. Get it right and the agent doesn't miss a beat.

Here's the map.

---

## // THE THREE LAYERS

```
┌─────────────────────────────────┐
│  LAYER 3: OpenClaw + qwen-coder │  ← updates most often
├─────────────────────────────────┤
│  LAYER 2: Nix toolchain         │  ← updates rarely
│  (Node.js, Python, gcc, gh...)  │
├─────────────────────────────────┤
│  LAYER 1: Config + Data         │  ← never needs a rebuild
│  (secrets/, data/)              │
└─────────────────────────────────┘
```

Rule of thumb: **update the highest layer you need.** Don't rebuild what doesn't need rebuilding.

---

## // UPGRADE PATH 1: CONFIG HOT-RELOAD (INSTANT, NO REBUILD)

**When to use:** Changing model settings, adding channels, tweaking agent behavior, updating API keys.

The `secrets/` directory is mounted directly into the container. OpenClaw watches the config file and reloads it live. Edit on your Mac, the agent picks it up in seconds:

```bash
$EDITOR secrets/openclaw.json5
# done — agent reloads automatically
```

Verify it took effect:

```bash
just logs
# look for: [*] Config reloaded
```

**No restart. No rebuild. Zero downtime.**

---

## // UPGRADE PATH 2: OPENCLAW + QWEN-CODER (FAST, STAGE 2 ONLY)

**When to use:** New OpenClaw release, qwen-coder update, adding npm packages to the cortex.

OpenClaw and qwen-coder live in Stage 2 of the Docker build — the thin layer on top of the Nix base. Rebuilding Stage 2 is fast because Docker caches Stage 1 (the Nix toolchain). It only downloads and installs the new npm packages:

```bash
just build    # Stage 1 cache hit — only Stage 2 reruns
just restart  # swap the running container for the new image
```

Your `/data` volume is untouched. Sessions, workspace, gh auth — all intact.

Check what version landed:

```bash
docker compose -f cortex/docker-compose.yml exec cortex openclaw --version
```

---

## // UPGRADE PATH 3: NIX TOOLCHAIN (SLOWER, STAGE 1 RERUNS)

**When to use:** Updating Node.js, Python, gh CLI, ripgrep, or any other Nix-pinned tool. Security patches to the base layer.

The Nix toolchain is pinned by `flake.lock` — a cryptographic lockfile. Updating it pulls the latest versions from nixpkgs and re-locks them to new hashes. Stage 1 then reruns from scratch (takes a few minutes):

```bash
# Inside the nix dev shell (run `nix develop` first if needed):
nix flake update          # bumps flake.lock to latest nixpkgs
git add flake.lock
git commit -m "chore: bump nix flake"

just build                # Stage 1 reruns — full toolchain recompile
just restart
```

> **Why commit `flake.lock`?** The lockfile is your single source of truth. Committing it means anyone who clones the repo gets the exact same toolchain. Treat it like a `package-lock.json`.

---

## // UPGRADE PATH 4: FULL NUKE AND REBUILD (SCORCHED EARTH)

**When to use:** Something is broken and you want a clean slate. No cache, no layers, fresh bake from the ground up.

```bash
just rebuild   # = docker compose build --no-cache + up -d
```

This blows away every cached Docker layer and rebuilds everything from scratch: Stage 1 (Nix toolchain) + Stage 2 (OpenClaw). Takes the longest but guarantees a pristine image.

Your `/data` volume is **still untouched**. State survives even a full nuke.

---

## // THE DECISION TREE

```
Need to change config or API keys?
  └─ Edit secrets/openclaw.json5 directly → DONE (hot-reload)

New OpenClaw or qwen-coder version?
  └─ just build + just restart → DONE (minutes)

New Node.js / Python / system tool?
  └─ nix flake update + just build + just restart → DONE (longer)

Something is broken and nothing makes sense?
  └─ just rebuild → DONE (scorched earth, fresh start)
```

---

## // WHAT SURVIVES EVERY UPDATE

This is the critical part. No matter which upgrade path you take, everything in `/data` survives:

```
data/
  workspace/     ← agent files, reports, code — safe
  gh/            ← GitHub CLI auth token — safe
  qwen/          ← qwen-coder config — safe
  sessions/      ← Telegram/WhatsApp sessions — safe
  agents/        ← agent sandboxes — safe
```

The container is disposable. Your data is not. That's the architecture.

---

## // SYSTEM STATUS POST-UPGRADE

```bash
just logs
```

```
[*] Config loaded from /config/openclaw.json5
[*] Telegram uplink: ONLINE
[+] Gateway listening on :18789
[+] Agent cortex: READY
```

If you see that, the upgrade landed clean. Your agent is back online, state intact, mission continues.

---

*Nyx — Rebuild the cortex. Keep the ghost.*
