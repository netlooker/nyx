# Deployment Guide

## Prerequisites

- Docker running (Apple Silicon: aarch64)
- `just` installed (`nix develop` drops you into a shell with it)
- `secrets/openclaw.json5` configured (see below)

## Step 1: Configure

Edit `secrets/openclaw.json5`. This file is gitignored — your credentials stay local.

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
      baseUrl: 'http://192.168.1.x:8008/v1',  // your llama.cpp server IP
      api: 'openai-completions',
      apiKey: 'local_inference',
      models: [
        { id: 'your-model.gguf', name: 'Local Model' },
      ],
    },
  },
},
```

## Step 2: Build

The Dockerfile is a multi-stage build: Stage 1 uses Nix to compile the pinned toolchain (Node.js, Python, gcc, etc.) inside a builder container; Stage 2 copies the result into a clean Debian-slim image and installs openclaw on top. Docker caches the Nix stage — it only reruns when `flake.nix` or `flake.lock` change.

```bash
just build
```

## Step 3: Start

```bash
just up
just logs
```

Dashboard available at `http://localhost:18789` if you set `gateway.bind: 'lan'` and a password.

## Step 5: Telegram Pairing

With `dmPolicy: 'pairing'`, the bot ignores all messages until your Telegram account is approved.

1. Send any message to your bot on Telegram (e.g. `/start`)
2. Get the pairing PIN from logs:

   ```bash
   docker compose -f cortex/docker-compose.yml logs | grep -iE "pairing|pin|code" | tail -5
   ```

3. Approve:

   ```bash
   docker compose -f cortex/docker-compose.yml exec cortex \
     openclaw pairing approve telegram YOUR-PIN-HERE
   ```

## Step 6: WhatsApp Pairing

WhatsApp requires a QR code scan for initial auth (Baileys-based, expires every 60s):

```bash
docker compose -f cortex/docker-compose.yml exec -it cortex \
  openclaw channels login --channel whatsapp
```

1. Wait for the QR code to render in your terminal
2. On your phone: **WhatsApp → Settings → Linked Devices → Link a Device**
3. Scan the QR code

The session is saved to `/data` and survives container restarts.

## Useful Commands

```bash
just up          # start
just down        # stop
just logs        # tail logs
just restart     # restart container without rebuilding
just rebuild     # full rebuild from scratch + start
```

## Updating OpenClaw

OpenClaw is installed via `npm install -g openclaw@latest`. To update:

```bash
just build       # rebuilds the cortex layer with latest openclaw
just restart
```

The Nix base layer is Docker-cached and does not need to be rebuilt for this.
