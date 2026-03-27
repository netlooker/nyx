# Nyx

Reproducible deployment of [OpenClaw](https://openclaw.ai) using a Nix-built Docker base layer.

## Quick Start

```bash
# 1. Configure (gitignored)
cp secrets/openclaw.json5.example secrets/openclaw.json5
# edit secrets/openclaw.json5 — add your bot token, inference endpoint

# 2. Build and run
just build   # multi-stage: Nix base layer + openclaw on top
just up
just logs
```

See [GUIDE.md](GUIDE.md) for full setup including Telegram/WhatsApp pairing.
See [ARCHITECTURE.md](ARCHITECTURE.md) for why it's built this way.

## Structure

```
flake.nix              — builds nyx-base-image (Nix-pinned toolchains)
brain/Dockerfile       — FROM nyx-base-image + npm install -g openclaw@latest
brain/docker-compose.yml
secrets/               — gitignored, config lives here
data/                  — gitignored, all openclaw state + agent sandboxes
justfile               — build workflow
```
