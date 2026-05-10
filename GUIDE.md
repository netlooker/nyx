# Deployment Guide

## Prerequisites

- Docker with Compose
- `just` from your package manager or <https://just.systems/>

No Nix installation or shell activation is required. The runtime is built and
started entirely through Docker Compose.

## Step 1: Configure

The `secrets/` directory is gitignored. It stores credentials and local runtime overrides:

- `secrets/openclaw.json5` — OpenClaw config, hot-reloaded by the gateway
- `secrets/.env` — environment variables injected into the container
- `secrets/synapse.toml` — optional Synapse override
- `secrets/sonar.toml` — optional Sonar override

Create a gateway password:

```bash
mkdir -p secrets
echo "OPENCLAW_GATEWAY_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=')" > secrets/.env
```

Create and edit OpenClaw config:

```bash
cp container/openclaw.json5.example secrets/openclaw.json5
$EDITOR secrets/openclaw.json5
```

Minimum Telegram channel config:

```json5
channels: {
  telegram: {
    enabled: true,
    botToken: 'your-bot-token-from-@BotFather',
    dmPolicy: 'pairing',
  },
}
```

For local inference, configure an OpenAI-compatible provider such as llama.cpp:

```json5
models: {
  mode: 'merge',
  providers: {
    llamacpp: {
      baseUrl: 'http://192.168.1.x:8005/v1',
      api: 'openai-completions',
      apiKey: 'local_inference',
      models: [
        {
          id: 'your-model.gguf',
          name: 'Local Model',
          contextWindow: 262144,
          maxTokens: 32768,
          input: ['text', 'image'],
        },
      ],
    },
  },
},
```

Create Qwen Code config:

```bash
cp container/qwen.json5.example secrets/qwen-settings.json
$EDITOR secrets/qwen-settings.json
```

Use absolute MCP command paths in configs:

```json
"/usr/local/bin/synapse-mcp"
"/usr/local/bin/sonar-mcp"
"/usr/local/bin/scrapling"
```

## Step 2: Build

```bash
just build
```

The build uses `versions.env`, resolves floating selectors to concrete package versions or git commits, and records them in `/app/build-info.json`.

## Step 3: Start

```bash
just up
just logs
```

Dashboard: `http://localhost:18789` when `gateway.bind: 'lan'` and password auth are configured.

## Runtime Contract

- `secrets/` mounts to `/config`; OpenClaw can hot-reload config edits.
- `data/` mounts to `/data`; sessions, memory, sandboxes, browser caches, and tool state survive rebuilds.
- `entrypoint.sh` recreates tool config symlinks on every container start.

## Telegram Pairing

1. Send any message to your bot on Telegram.
2. Get the pairing PIN from logs:

   ```bash
   docker compose -f container/docker-compose.yml logs | grep -iE "pairing|pin|code" | tail -5
   ```

3. Approve:

   ```bash
   docker compose -f container/docker-compose.yml exec nyx \
     openclaw pairing approve telegram YOUR-PIN-HERE
   ```

## WhatsApp Pairing

```bash
docker compose -f container/docker-compose.yml exec -it nyx \
  openclaw channels login --channel whatsapp
```

Scan the QR code from WhatsApp -> Settings -> Linked Devices -> Link a Device. The session is saved under `/data`.

## Useful Commands

```bash
just build      # build image
just check      # validate compose, shell syntax, scripts, and Dockerfile contract
just up         # start
just down       # stop
just logs       # tail logs
just restart    # restart without rebuilding
just rebuild    # no-cache rebuild + start
just status     # show OpenClaw status
```

## Updating Tools

Edit `versions.env` to pin a specific version/ref, or leave a selector as `latest`/`main` and rerun:

```bash
just build
just restart
```

Inspect captured metadata:

```bash
docker image inspect nyx:latest --format '{{json .Config.Labels}}'
```
