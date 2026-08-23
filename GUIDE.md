# Deployment Guide

## Prerequisites

- Docker with Compose
- `just` from your package manager or <https://just.systems/>

No Nix installation or shell activation is required. The runtime is built and
started entirely through Docker Compose.

## Step 1: Configure

The `secrets/` directory is gitignored. It stores credentials and local runtime overrides:

- `secrets/openclaw.json5` — OpenClaw config, hot-reloaded by the gateway
- `secrets/hermes.yaml` — Hermes config when `NYX_ORCHESTRATOR=hermes`
- `secrets/hermes.env` — Hermes environment variables and platform secrets
- `secrets/.env` — environment variables injected into the container
- `secrets/synapse.toml` — optional Synapse override
- `secrets/sonar.toml` — optional Sonar override

Create the orchestrator selection and shared env file:

```bash
mkdir -p secrets
printf 'NYX_ORCHESTRATOR=openclaw\n' > secrets/.env
printf 'OPENCLAW_GATEWAY_PASSWORD=%s\n' "$(openssl rand -base64 24 | tr -d '/+=')" >> secrets/.env
```

Create and edit orchestrator config:

```bash
cp container/openclaw.json5.example secrets/openclaw.json5
cp container/hermes.yaml.example secrets/hermes.yaml
cp container/hermes.env.example secrets/hermes.env
$EDITOR secrets/openclaw.json5
$EDITOR secrets/hermes.yaml
```

Set `NYX_ORCHESTRATOR=openclaw` or `NYX_ORCHESTRATOR=hermes` in `secrets/.env`.

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
      request: {
        // Required for trusted LAN/private-IP llama.cpp endpoints when
        // OpenClaw uses its guarded transport path.
        allowPrivateNetwork: true,
      },
      models: [
        {
          id: 'your-model.gguf',
          name: 'Local Model',
          contextWindow: 131072,
          maxTokens: 12288,
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

### Optic-Spark Image Generation

The Optic-Spark API accepts image generation jobs at the DGX/LAN endpoint (`http://192.168.1.x:7070`), and delivers results by POSTing back to the CLI's temporary webhook server. When `optic-cli` runs inside the Nyx container, the callback address must be an address reachable from the remote Optic-Spark host.

Nyx builds `optic-cli` (and alias `optic-spark`) with pre-wired defaults:
- `OPTIC_SPARK_API_URL` (e.g. `http://192.168.1.x:7070` configured in `secrets/.env`)
- `OPTIC_SPARK_CALLBACK_HOST` (e.g. `http://192.168.1.x` configured in `secrets/.env`)
- `OPTIC_SPARK_OUT_DIR` (default `/data/workspace/images`)

Published callback ports `17070-17170` are constrained to match the container's ephemeral port range. Agents and users can run simple commands without specifying manual IPs:

```bash
docker compose -f container/docker-compose.yml exec nyx optic-cli \
  -prompt "A highly detailed cyberpunk server room, glowing neon lights, cinematic" \
  -aspect 16:9 \
  -format png
```

If your Nyx host has a different LAN IP, set `OPTIC_SPARK_CALLBACK_HOST=http://<your-host-ip>` in `secrets/.env`. If callback ports conflict locally, set `OPTIC_SPARK_CALLBACK_PORT_MIN` and `OPTIC_SPARK_CALLBACK_PORT_MAX` in `secrets/.env` and restart Nyx.

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

OpenClaw dashboard: `http://localhost:18789` when `gateway.bind: 'lan'` and password auth are configured. Hermes mode does not expose a Nyx-managed dashboard in this pass.

## Runtime Contract

- `secrets/` mounts to `/config`; the selected orchestrator reads its config from there.
- `data/` mounts to `/data`; sessions, memory, sandboxes, browser caches, and tool state survive rebuilds.
- `entrypoint.sh` recreates tool config symlinks on every container start and then dispatches to OpenClaw or Hermes based on `NYX_ORCHESTRATOR`.

## OpenClaw Pairing

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

## Hermes Runtime

With `NYX_ORCHESTRATOR=hermes`, Nyx sets `HERMES_HOME=/data/hermes`, links `secrets/hermes.yaml` to `/data/hermes/config.yaml`, links `secrets/hermes.env` to `/data/hermes/.env` when present, and starts:

```bash
hermes gateway run
```

## Useful Commands

```bash
just build      # build image
just check      # validate compose, shell syntax, scripts, and Dockerfile contract
just up         # start
just down       # stop
just logs       # tail logs
just restart    # restart without rebuilding
just rebuild    # no-cache rebuild + start
just status     # show OpenClaw or Hermes status
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

Before rebuilding or upgrading OpenClaw, review the local llama.cpp usage
workaround in
[`patches/openclaw-2026.5.7-llamacpp-usage.md`](patches/openclaw-2026.5.7-llamacpp-usage.md).
OpenClaw `2026.5.7` can otherwise lose streamed usage metadata from
self-hosted OpenAI-compatible llama.cpp endpoints, causing `unknown/262k (?)`
context status on fresh sessions.
