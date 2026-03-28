# syntax=docker/dockerfile:1

###############################################################################
# Stage 1: Nix Builder
#
# Builds the pinned toolchain (Node.js, Python, gcc, etc.) using Nix.
# Docker caches this layer — only rebuilds when flake.nix or flake.lock change.
# Pinned: Node.js, Python, gcc, cmake, jq, ripgrep, bat, eza, htop, fd, zip/unzip
###############################################################################
FROM nixos/nix:2.25.3 AS nix-builder

RUN echo 'experimental-features = nix-command flakes' >> /etc/nix/nix.conf

WORKDIR /build
COPY flake.nix flake.lock ./

# Build the content derivation for Linux/ARM64 (aarch64-linux on Apple Silicon).
# Output: a directory of symlinks pointing into the Nix store.
RUN nix build '.#packages.aarch64-linux.base-content' --out-link /nix-content

###############################################################################
# Stage 2: Cortex
#
# Minimal Debian base + Nix store from Stage 1 + openclaw on top.
# The Nix store must stay at /nix/store — all Nix binaries use absolute paths.
###############################################################################
FROM debian:bookworm-slim AS cortex

# Import the Nix store with all pinned packages
COPY --from=nix-builder /nix/store /nix/store

# The content layer: symlinks from /nix-env/bin → /nix/store/…/bin/node etc.
COPY --from=nix-builder /nix-content /nix-env

# Expose Nix tools on PATH and set SSL certs
ENV PATH=/nix-env/bin:/usr/local/bin:/usr/bin:/bin
ENV SSL_CERT_FILE=/nix-env/etc/ssl/certs/ca-bundle.crt
ENV HOME=/root
ENV CI=true

# FHS compat: npm scripts and shebangs expect /bin/sh and /usr/bin/env
RUN ln -sf /nix-env/bin/bash /bin/sh && \
    ln -sf /nix-env/bin/env /usr/bin/env

# Redirect npm global prefix to /usr/local so the binary lands in /usr/local/bin
# (already on PATH). Without this, npm uses the Nix store's node prefix which has
# a hash-based path unknown at runtime.
RUN npm config set prefix /usr/local && \
    npm install -g openclaw@latest && \
    npm install -g @qwen-code/qwen-code@latest

# Config mounted from host (directory mount, not file — avoids EBUSY on rename)
ENV OPENCLAW_CONFIG_PATH=/config/openclaw.json5

# Persist gh CLI auth across rebuilds — token survives in the /data volume
ENV GH_CONFIG_DIR=/data/gh

# All openclaw state: databases, agent sandboxes, sessions, downloaded files.
# Mounted as a volume so it survives container rebuilds and is backed up on Mac.
ENV OPENCLAW_STATE_DIR=/data

EXPOSE 18789

CMD ["openclaw", "gateway", "run"]
