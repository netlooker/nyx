# Deployment Guide

## Prerequisites

- Docker running (Apple Silicon: aarch64)
- [Nix](https://nixos.org/download/) installed — used to get `just` and for the Docker build

## Step 1: Enter the dev shell

Clone the repo and enter the Nix dev shell. This pins all local tools (just, node, python, age) to exact versions:

```bash
git clone https://github.com/netlooker/nyx.git
cd nyx
nix develop
```

You'll land in a shell with `just` available. If you use [direnv](https://direnv.net/), run `direnv allow` once and it activates automatically on every `cd nyx`.

Set `NYX_NIX_SYSTEM` to match the Linux architecture Docker will build for:
- Apple Silicon Docker host: default `aarch64-linux`
- x86_64 Docker host: `NYX_NIX_SYSTEM=x86_64-linux`

## Step 2: Configure

The `secrets/` directory is gitignored — all credentials stay local. Two files live there:

- `secrets/openclaw.json5` — OpenClaw config (hot-reloaded by the gateway)
- `secrets/.env` — environment variables injected into the container

Optional runtime overrides can also live there:

- `secrets/synapse.toml` — override the baked Synapse default
- `secrets/sonar.toml` — override the baked Sonar default

### Gateway password

Create `secrets/.env` with your gateway password:

```bash
echo "OPENCLAW_GATEWAY_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=')" > secrets/.env
```

This keeps the password out of `openclaw.json5` (which the agent can read). The config just declares the auth mode:

```json5
gateway: {
  auth: { mode: 'password' },
}
```

### OpenClaw config

Edit `secrets/openclaw.json5`:

```bash
cp container/openclaw.json5.example secrets/openclaw.json5
$EDITOR secrets/openclaw.json5
```

For weaker local models, keep the example `tools.loopDetection` block enabled.
Nyx uses that to stop repeated no-progress tool loops, especially around schema
validation failures for MCP/tool calls.

Minimum required for Telegram:

```json5
channels: {
  telegram: {
    enabled: true,
    botToken: 'your-bot-token-from-@BotFather',
    dmPolicy: 'pairing',
  },
}
```

For local inference (llama.cpp):

```json5
models: {
  mode: 'merge',
  providers: {
    llamacpp: {
      baseUrl: 'http://192.168.1.x:8005/v1',  // your llama.cpp server IP
      api: 'openai-completions',
      apiKey: 'local_inference',
      models: [
        {
          id: 'your-model.gguf',
          name: 'Local Model',
          contextWindow: 262144,     // match your --ctx-size
          maxTokens: 32768,          // match your --batch-size
          input: ['text', 'image'],  // add 'image' if --mmproj is loaded
        },
      ],
    },
  },
},
```

## Step 3: Build

The Dockerfile is a multi-stage build: Stage 1 uses Nix to compile the pinned toolchain (Node.js, Python, gcc, etc.) inside a builder container; Stage 2 copies the result into a clean Debian-slim image and installs openclaw on top. Docker caches the Nix stage — it only reruns when `flake.nix` or `flake.lock` change.

```bash
just build
```

On x86_64 Docker hosts:

```bash
NYX_NIX_SYSTEM=x86_64-linux just build
```

If you want the heavier compliance path with the optional `bombon` SBOM:

```bash
just build-sbom
```

## Step 4: Start

```bash
just up
just logs
```

Dashboard available at `http://localhost:18789` if you set `gateway.bind: 'lan'` and a password in `secrets/.env`.

## Runtime Contract

The intended appliance behavior is:
- `secrets/openclaw.json5` is mounted as part of the `/config` directory, so OpenClaw can hot-reload config edits from the host
- `data/` is mounted to `/data`, so sessions, memory, sandboxes, and tool state survive rebuilds
- `entrypoint.sh` recreates tool config symlinks on every container start, so rebuilds do not orphan `$HOME`-bound tool state

## Step 5: Telegram Pairing

With `dmPolicy: 'pairing'`, the bot ignores all messages until your Telegram account is approved.

1. Send any message to your bot on Telegram (e.g. `/start`)
2. Get the pairing PIN from logs:

   ```bash
   docker compose -f container/docker-compose.yml logs | grep -iE "pairing|pin|code" | tail -5
   ```

3. Approve:

   ```bash
   docker compose -f container/docker-compose.yml exec nyx \
     openclaw pairing approve telegram YOUR-PIN-HERE
   ```

## Step 6: WhatsApp Pairing

WhatsApp requires a QR code scan for initial auth (Baileys-based, expires every 60s):

```bash
docker compose -f container/docker-compose.yml exec -it nyx \
  openclaw channels login --channel whatsapp
```

1. Wait for the QR code to render in your terminal
2. On your phone: **WhatsApp → Settings → Linked Devices → Link a Device**
3. Scan the QR code

The session is saved to `/data` and survives container restarts.

## Useful Commands

```bash
just build-base   # build + load the standalone Nix base image
just build-sbom   # build image + optional bombon SBOM artifact
just up          # start
just down        # stop
just check       # validate compose config, shell syntax, flake outputs
just logs        # tail logs
just restart     # restart container without rebuilding
just rebuild     # full rebuild from scratch + start
just status      # show channels, sessions, context window usage
```

## Updating OpenClaw

`just build` resolves the current OpenClaw and Qwen package versions before calling Docker, then passes those concrete versions into the image build. To pick up the newest release:

```bash
just build       # rebuilds the container with latest openclaw
just restart
```

The Nix base layer is Docker-cached and does not need to be rebuilt for this.

To inspect the captured build metadata after a build:

```bash
docker image inspect nyx:latest --format '{{json .Config.Labels}}'
```

The default build sets SBOM metadata to disabled. If you build with `just build-sbom`, the labels will point to `/app/sbom-base.json`.
