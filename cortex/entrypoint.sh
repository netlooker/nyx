#!/bin/sh
# Symlink ephemeral tool config dirs into the persistent /data volume.
# Runs at container start, after volume mounts — before openclaw.

# qwen-coder: hardcodes $HOME/.qwen, no env override available
mkdir -p /data/qwen
ln -sf /data/qwen /root/.qwen

exec "$@"
