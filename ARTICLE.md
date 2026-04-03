# // OPERATION: NYX CORTEX
**TARGET ARCHITECTURE:** APPLE SILICON (AARCH64)
**PAYLOAD:** OPENCLAW AGENT + QWEN-CODER + GH CLI
**ENGINE:** NIX MULTI-STAGE DOCKER (MATHEMATICALLY DETERMINISTIC)
**OPERATOR:** NETRUNNER

Wake up, netrunner. You're tired of your AI agent phoning home to corporate servers, leaking your codebase into some faceless training pipeline, going dark when the subscription lapses. You want a ghost that runs on *your* silicon, speaks through your encrypted channels, and answers only to you.

This is Nyx. A self-sovereign AI cortex. Clone it, configure it, bake it, run it. Four moves and your agent is live.

---

## // PHASE 0: PRIME THE FORGE (INSTALL NIX)

Before anything else, you need one tool: **Nix**. Think of it as a package manager with a superpower — it pins every dependency to a cryptographic hash so the build is identical on every machine, every time. No "works on my machine." No version drift.

```bash
curl -sSfL https://artifacts.nixos.org/nix-installer | sh -s -- install
```

That's it. Nix is now on your Mac.

> **What Nix actually does in this project — the short version:**
> 1. On your Mac: gives you the tools to drive the project (`just`, `node`, etc.)
> 2. Inside the Docker build: compiles the entire container toolchain with every binary pinned to a hash — automatically, you never touch it

---

## // PHASE 1: THE CLONE (PULL THE BLUEPRINT)

Pull the repo and enter the Nix dev shell. This gives you a local environment with every tool pinned — no manual installs needed:

```bash
git clone https://github.com/netlooker/nyx.git
cd nyx
nix develop
```

You'll see:

```
nyx dev shell (aarch64-darwin)
```

You're in. Your terminal now has `just` (the task runner), `node`, `python`, and `age`. Use `just` for everything from here.

> **Tip:** Install [direnv](https://direnv.net/) and run `direnv allow` once — the dev shell activates automatically every time you `cd` into the project.

---

## // PHASE 2: THE CONFIG (WIRE THE NEURAL LINK)

The agent is blind until you feed it credentials. The config file is gitignored by design — your keys never leave your machine:

```bash
cp cortex/openclaw.json5.example secrets/openclaw.json5
$EDITOR secrets/openclaw.json5
```

**[MINIMUM CONFIG — TELEGRAM UPLINK:]**

Get a bot token from [@BotFather](https://t.me/BotFather) on Telegram, then wire it in:

```json5
channels: {
  telegram: {
    enabled: true,
    botToken: 'your-token-from-@BotFather',
    dmPolicy: 'pairing',   // nobody talks to your agent without your approval
  },
},
agents: {
  defaults: {
    workspace: '/data/workspace',  // agent files survive rebuilds
  },
},
```

**[OPTIONAL — LOCAL INFERENCE NODE:]**

Skip the cloud. Point the agent at a local model running on your LAN via Ollama, llama.cpp, or any OpenAI-compatible endpoint:

```json5
models: {
  mode: 'merge',
  providers: {
    llamacpp: {
      baseUrl: 'http://192.168.1.x:8008/v1',
      api: 'openai-completions',
      apiKey: 'local_inference',
      models: [
        { id: 'your-model.gguf', name: 'Local Model' },
      ],
    },
  },
},
```

---

## // PHASE 3: THE FORGE (BAKE THE CORTEX)

One command builds the entire stack:

```bash
just build
```

Under the hood this runs a two-stage Docker build:

- **Stage 1 (automatic):** A `nixos/nix` container spins up *inside* Docker and compiles the full toolchain — Node.js, Python, gcc, ripgrep, gh CLI, and more — with every binary pinned to a hash. You don't touch this. Docker handles it and caches the result.
- **Stage 2:** The compiled toolchain gets dropped into a clean, minimal Debian image. OpenClaw and qwen-coder are installed on top. The result is `nyx-cortex:latest`.

The cache is smart: Stage 1 only reruns if you change the Nix config files (`flake.nix` / `flake.lock`). Updating OpenClaw or qwen-coder only reruns Stage 2 — fast.

---

## // PHASE 4: BOOT SEQUENCE (IGNITE THE CORTEX)

```bash
just up
just logs
```

Watch the cortex come online:

```
[*] Config loaded from /config/openclaw.json5
[*] Telegram uplink: ONLINE
[+] Gateway listening on :18789
[+] Agent cortex: READY
```

Two volumes connect your Mac to the running container:

| What | On Your Mac | Inside Container |
|---|---|---|
| Config | `secrets/` | `/config` |
| All agent data | `data/` | `/data` |

Edit the config on your Mac — the agent picks it up live, no restart needed. All agent data (files, sessions, auth tokens) lives in `data/` on your Mac and survives container rebuilds.

---

## // PHASE 5: JACK IN (TELEGRAM PAIRING)

With `dmPolicy: 'pairing'`, the agent is a ghost — it ignores everyone until *you* authorize them. First contact:

1. Send any message to your bot on Telegram — `/start` works
2. Grab the pairing PIN from the logs:

```bash
docker compose -f cortex/docker-compose.yml logs | grep -iE "pairing|pin|code" | tail -5
```

3. Authorize the connection:

```bash
docker compose -f cortex/docker-compose.yml exec cortex \
  openclaw pairing approve telegram YOUR-PIN-HERE
```

The bot responds. You're wired in. The cortex is yours.

---

## // PHASE 6: PERSISTENCE (YOUR DATA SURVIVES THE REBUILD)

The container is disposable. Your data is not. Everything that matters lives in `~/projects/nyx/data/` on your Mac:

```
data/
  workspace/     ← files the agent created, reports, code
  gh/            ← GitHub CLI auth token
  qwen/          ← qwen-coder config
  sessions/      ← Telegram/WhatsApp login sessions
  agents/        ← agent sandboxes
```

Nuke and rebuild anytime with `just rebuild`. The agent boots, reconnects to your data volume, and picks up exactly where it left off. No re-auth. No lost work.

---

## // USEFUL COMMANDS

```bash
just build     # bake the full image (Nix base + openclaw)
just up        # start the cortex
just down      # shut it down
just logs      # tail live output
just restart   # restart without rebuilding
just rebuild   # full rebuild from scratch, no cache
```

Agent dashboard at `http://localhost:18789` — enable it with `gateway.bind: 'lan'` + a password in your config.

---

## // SYSTEM STATUS

```
[+] CORTEX: ONLINE
[+] UPLINK: TELEGRAM / WHATSAPP
[+] INFERENCE: LOCAL LAN NODE
[+] STATE: PERSISTENT (/data)
[+] TOOLCHAIN: CRYPTOGRAPHICALLY PINNED
[+] DATA EXFIL: ZERO
```

Your agent is sovereign, netrunner. It lives on your silicon, thinks on your hardware, backs up to your disk. The corporate grid has no reach here.

```bash
just up
```

---

*Nyx — Ghost in the grid. Your AI agent, your hardware, your rules.*
