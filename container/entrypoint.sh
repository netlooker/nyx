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

# If the user supplied a custom synapse.toml via secrets/, point SYNAPSE_CONFIG
# at it. Otherwise the image default at /app/synapse.toml.default (set via
# ENV in the Dockerfile) stays in effect.
if [ -f /config/synapse.toml ]; then
  export SYNAPSE_CONFIG=/config/synapse.toml
  echo "[nyx] synapse config: /config/synapse.toml (user override)"
else
  echo "[nyx] synapse config: ${SYNAPSE_CONFIG:-/app/synapse.toml.default} (image default)"
fi

# If the user supplied a custom sonar.toml via secrets/, point SONAR_CONFIG at
# it. Otherwise the image default at /app/sonar.toml.default (set via ENV in
# the Dockerfile) stays in effect.
if [ -f /config/sonar.toml ]; then
  export SONAR_CONFIG=/config/sonar.toml
  echo "[nyx] sonar config: /config/sonar.toml (user override)"
else
  echo "[nyx] sonar config: ${SONAR_CONFIG:-/app/sonar.toml.default} (image default)"
fi

# Ship agent skills from image into workspace.
# Skills are baked into /app/skills at build time and symlinked into the
# workspace's .agents/skills/ directory so agents pick them up automatically.
# The symlink points at the image copy — container rebuild delivers new skills.
mkdir -p /data/workspace/.agents
ln -sfn /app/skills /data/workspace/.agents/skills

exec "$@"
