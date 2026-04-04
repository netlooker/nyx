#!/bin/sh
# Runs at container start, after volume mounts — before openclaw.

# Workspace structure: services (long-running UIs/APIs), tools (CLIs),
# projects (git repos the agent works on).
mkdir -p /data/workspace/services /data/workspace/tools /data/workspace/projects

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

# Ship agent skills from image into workspace.
# Skills are baked into /app/skills at build time and symlinked into the
# workspace's .agents/skills/ directory so agents pick them up automatically.
# The symlink points at the image copy — container rebuild delivers new skills.
mkdir -p /data/workspace/.agents
ln -sfn /app/skills /data/workspace/.agents/skills

exec "$@"
