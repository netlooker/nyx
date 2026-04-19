#!/bin/sh
# Runs at container start, after volume mounts — before openclaw.

# Workspace structure: services (long-running UIs/APIs), tools (CLIs),
# projects (git repos the agent works on).
mkdir -p /data/workspace/services /data/workspace/tools /data/workspace/projects

# Make the runtime command surface explicit for shells, maintenance commands,
# and child processes that do not preserve the Dockerfile PATH verbatim.
export PATH=/nix-env/bin:/usr/local/bin:/usr/bin:/bin

# Seed workspace instructions on first boot (won't overwrite edits)
[ ! -f /data/workspace/WORKSPACE.md ] && cp /app/WORKSPACE.md /data/workspace/WORKSPACE.md

# Symlink ephemeral tool config dirs into the persistent /data volume.
# qwen-code: hardcodes $HOME/.qwen, no env override available
mkdir -p /data/qwen
ln -sf /data/qwen /root/.qwen

# Inject qwen-code settings from config mount (secrets/) if present.
# The file must be valid JSON (strip comments from qwen.json5.example).
# Force-remove first: qwen may have written a regular file that ln -sf won't replace.
if [ -f /config/qwen-settings.json ]; then
  rm -f /data/qwen/settings.json
  ln -sf /config/qwen-settings.json /data/qwen/settings.json
fi

# Synapse vault — indexed by the built-in synapse-mcp server. Created on
# first boot so synapse_index has a target even before the user adds notes.
mkdir -p /data/workspace/vault

# Ensure /config has a concrete config for each tool — either user-supplied
# (bind-mounted from secrets/) or a symlink to the image default. This means
# MCP env vars can always point at /config/<tool>.toml and it will resolve
# whether the user provides an override or not. Without this, `docker compose
# exec` sessions that skip entrypoint.sh would inherit Dockerfile ENV defaults
# pointing at image-baked configs with placeholder IPs.
if [ -f /config/synapse.toml ]; then
  echo "[nyx] synapse config: /config/synapse.toml (user override)"
else
  ln -sf /app/synapse.toml.default /config/synapse.toml
  echo "[nyx] synapse config: /config/synapse.toml -> /app/synapse.toml.default (image default)"
fi
export SYNAPSE_CONFIG=/config/synapse.toml

if [ -f /config/sonar.toml ]; then
  echo "[nyx] sonar config: /config/sonar.toml (user override)"
else
  ln -sf /app/sonar.toml.default /config/sonar.toml
  echo "[nyx] sonar config: /config/sonar.toml -> /app/sonar.toml.default (image default)"
fi
export SONAR_CONFIG=/config/sonar.toml

# Synapse admin console — the web UI for the compiled knowledge layer.
# Disabled via SYNAPSE_API_ENABLED=false if the port or process is unwanted.
if [ "${SYNAPSE_API_ENABLED:-true}" = "true" ]; then
  echo "[nyx] synapse admin console: 0.0.0.0:${SYNAPSE_API_PORT:-8765}"
  synapse-api-serve &
fi

# Ship agent skills from image into workspace.
# Skills are baked into /app/skills at build time and symlinked into the
# workspace's .agents/skills/ directory so agents pick them up automatically.
# The symlink points at the image copy — container rebuild delivers new skills.
mkdir -p /data/workspace/.agents
ln -sfn /app/skills /data/workspace/.agents/skills
ln -sfn /app/subagents /data/workspace/.agents/subagents

# Scrapling: browser backends (Playwright chromium, Camoufox) are downloaded
# on first boot rather than baked into the image (~500MB). Symlink their
# cache dirs into /data so they survive rebuilds. Install runs in the
# background so container startup stays fast — failures leave no marker,
# so the next boot will retry.
mkdir -p /data/scrapling/ms-playwright /data/scrapling/camoufox /root/.cache
ln -sfn /data/scrapling/ms-playwright /root/.cache/ms-playwright
ln -sfn /data/scrapling/camoufox /root/.cache/camoufox
if [ ! -f /data/scrapling/.installed ]; then
  echo "[nyx] scrapling: downloading browser backends in background (first boot, ~500MB)…"
  (scrapling install && touch /data/scrapling/.installed && \
    echo "[nyx] scrapling: browser backends ready") &
fi

# Ship sub-agents into the qwen-code agents directory.
# Qwen Code looks for agent definitions in ~/.qwen/agents/ (user-level) and
# <project>/.qwen/agents/ (project-level). We use both: user-level for global
# availability, project-level for workspace sessions.
mkdir -p /root/.qwen/agents /data/workspace/.qwen/agents
for agent in /app/subagents/*.md; do
  [ -f "$agent" ] || continue
  ln -sf "$agent" "/root/.qwen/agents/$(basename "$agent")"
  ln -sf "$agent" "/data/workspace/.qwen/agents/$(basename "$agent")"
done

exec "$@"
