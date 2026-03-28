# // OPERATION: NYX CORTEX
**TARGET ARCHITECTURE:** APPLE SILICON (AARCH64)
**PAYLOAD:** OPENCLAW AGENT + QWEN-CODER + GH CLI
**ENGINE:** NIX MULTI-STAGE DOCKER (MATHEMATICALLY DETERMINISTIC)
**OPERATOR:** NETRUNNER

Wake up, netrunner. You're tired of your AI agent phoning home to corporate servers, leaking your codebase into some faceless training pipeline, going dark when the subscription lapses. You want a ghost that runs on *your* silicon, speaks through your encrypted channels, and answers only to you.

This is Nyx. A self-sovereign AI cortex. Reproducible to the hash. Deployed in four moves.

---

## // PHASE 1: THE CLONE (PULL THE BLUEPRINT)

The entire cortex is codified. Every dependency locked to a cryptographic hash in `flake.lock`. No version drift. No supply chain surprises.

**A note on Nix — it does two things here:**

- **On your Mac:** `nix develop` drops you into a hardened shell with every local tool pinned (`just`, `node`, `python`, `age`). This is how you drive the project.
- **Inside Docker:** When you run `just build`, Stage 1 of the Dockerfile spins up a `nixos/nix` container *within Docker* and runs `nix build` to compile the entire toolchain — Node.js, Python, gcc, ripgrep, the lot — cryptographically pinned. You never run this manually. Docker handles it.

Two uses of Nix. One for your local environment. One baked invisibly into the container build.

**[INSTALL NIX — ONE COMMAND:]**

```bash
curl -sSfL https://artifacts.nixos.org/nix-installer | sh -s -- install
```

Then pull the blueprint and enter the dev shell:

```bash
git clone https://github.com/netlooker/nyx.git
cd nyx
nix develop
```

You'll see:

```
nyx dev shell (aarch64-darwin)
```

You're in. The shell carries `just`, `node`, `python`, `age`. From here you control the cortex.

---

## // PHASE 2: THE CONFIG (WIRE THE NEURAL LINK)

The agent is blind until you feed it credentials. The config file is gitignored by design — your keys never touch the network:

```bash
cp secrets/openclaw.json5.example secrets/openclaw.json5
$EDITOR secrets/openclaw.json5
```

**[MINIMUM CONFIG — TELEGRAM UPLINK:]**
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
    workspace: '/data/workspace',  // survives rebuilds — mounted from your Mac
  },
},
```

**[OPTIONAL — WIRE IN A LOCAL INFERENCE NODE:]**
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

No cloud endpoint required. Point it at Ollama, llama.cpp, or any OpenAI-compatible socket on your LAN.

---

## // PHASE 3: THE FORGE (BAKE THE CORTEX)

This is where the magic happens. One command. Two stages. Zero ambiguity.

```bash
just build
```

**Stage 1 — Nix Builder (automatic, inside Docker):** Docker spins up a `nixos/nix` container internally and runs `nix build`. Nix resolves the full dependency graph — Node.js, Python 3, gcc, cmake, ripgrep, bat, gh CLI, the lot — and pins every single binary to a cryptographic hash. You don't touch this. It just happens. A cryptographic SBOM ships baked into `/app/sbom-base.json` so you can prove exactly what's running inside.

**Stage 2 — Cortex:** Drops the Nix store into a clean `debian:bookworm-slim`. Layers openclaw and qwen-coder on top using the pinned Node.js. Configures the entrypoint to symlink tool configs into your persistent `/data` volume before the agent boots.

Docker caches Stage 1. It only reruns when `flake.nix` or `flake.lock` change. Hot-swapping OpenClaw versions is instant — Stage 2 only.

Watch for the build to complete, then you're holding a hardened image: `nyx-cortex:latest`.

---

## // PHASE 4: BOOT SEQUENCE (IGNITE THE CORTEX)

```bash
just up
just logs
```

**[EXPECTED BOOT OUTPUT:]**
```
[*] INITIATING NYX CORTEX...
[*] Config loaded from /config/openclaw.json5
[*] Telegram uplink: ONLINE
[+] Gateway listening on :18789
[+] Agent cortex: READY
```

Two volumes keep the agent alive across rebuilds and power cycles:

| Host Path | Container Path | What Lives There |
|---|---|---|
| `secrets/` | `/config` | Hot-reloadable config — edit on your Mac, agent reloads live |
| `data/` | `/data` | Agent workspace, sessions, gh auth, qwen-coder state — your backup |

Edit `secrets/openclaw.json5` on your Mac and the agent picks it up instantly. No rebuild. No restart. The directory mount bypasses the EBUSY inode lock that file mounts trigger on atomic renames.

---

## // PHASE 5: JACK IN (TELEGRAM PAIRING)

With `dmPolicy: 'pairing'`, the agent is a ghost — invisible to everyone until *you* authorize them. First contact:

1. Fire a message at your bot on Telegram — anything, `/start` works
2. Rip the pairing PIN from the logs:

```bash
docker compose -f cortex/docker-compose.yml logs | grep -iE "pairing|pin|code" | tail -5
```

3. Authorize the uplink:

```bash
docker compose -f cortex/docker-compose.yml exec cortex \
  openclaw pairing approve telegram YOUR-PIN-HERE
```

The bot responds. You're wired in. The cortex is yours.

---

## // PHASE 6: PERSISTENCE (YOUR DATA SURVIVES THE REBUILD)

The cortex is stateless by design — you can nuke and rebuild the image at any time. Everything that matters lives in `~/projects/nyx/data/` on your Mac:

```
data/
  workspace/     ← agent files, reports, code it wrote
  gh/            ← GitHub CLI auth (GH_CONFIG_DIR)
  qwen/          ← qwen-coder config (symlinked from /root/.qwen on boot)
  sessions/      ← Telegram/WhatsApp sessions
  agents/        ← agent sandboxes
```

Run `just rebuild` — full no-cache bake from scratch. The agent boots, the entrypoint symlinks `/root/.qwen → /data/qwen`, and it picks up right where it left off. No re-auth. No lost state. No lost work.

---

## // SYSTEM STATUS

```
[+] CORTEX: ONLINE
[+] UPLINK: TELEGRAM / WHATSAPP
[+] INFERENCE: LOCAL LAN NODE
[+] STATE: PERSISTENT (/data)
[+] TOOLCHAIN: CRYPTOGRAPHICALLY PINNED
[+] SBOM: /app/sbom-base.json
[+] DATA EXFIL: ZERO
```

Your agent is sovereign, netrunner. It lives on your silicon, thinks on your hardware, and backs up to your disk. The corporate grid has no reach here.

```bash
just up
```

---

*Nyx — Ghost in the grid. Your AI agent, your hardware, your rules.*
