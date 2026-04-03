#!/bin/sh
# Runs at container start, after volume mounts — before openclaw.

# Workspace structure: services (long-running UIs/APIs), tools (CLIs),
# projects (git repos the agent works on).
mkdir -p /data/workspace/services /data/workspace/tools /data/workspace/projects

# Seed workspace instructions on first boot (won't overwrite edits)
[ ! -f /data/workspace/WORKSPACE.md ] && cp /app/WORKSPACE.md /data/workspace/WORKSPACE.md

# Symlink ephemeral tool config dirs into the persistent /data volume.
# qwen-coder: hardcodes $HOME/.qwen, no env override available
mkdir -p /data/qwen
ln -sf /data/qwen /root/.qwen

exec "$@"
