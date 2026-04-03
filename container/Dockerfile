# syntax=docker/dockerfile:1

ARG NYX_NIX_SYSTEM=aarch64-linux
ARG OPENCLAW_VERSION=latest
ARG QWEN_CODE_VERSION=latest
ARG ENABLE_SBOM=false
ARG SBOM_PATH=

###############################################################################
# Stage 1: Nix Builder
#
# Builds the pinned toolchain (Node.js, Python, gcc, etc.) using Nix.
# Docker caches this layer — only rebuilds when flake.nix or flake.lock change.
# Pinned: Node.js, Python, gcc, cmake, jq, ripgrep, bat, eza, htop, fd, zip/unzip
###############################################################################
FROM nixos/nix:2.25.3 AS nix-builder
ARG NYX_NIX_SYSTEM

RUN echo 'experimental-features = nix-command flakes' >> /etc/nix/nix.conf

WORKDIR /build
COPY flake.nix flake.lock ./

# Build the selected Linux system's pinned base content.
RUN nix build ".#packages.${NYX_NIX_SYSTEM}.base-content" --out-link /nix-content

FROM nix-builder AS sbom-builder
ARG NYX_NIX_SYSTEM
ARG ENABLE_SBOM

# Opt-in SBOM generation only. The default build path skips bombon entirely.
RUN if [ "$ENABLE_SBOM" = "true" ]; then \
      nix build ".#packages.${NYX_NIX_SYSTEM}.sbom-dir" --out-link /sbom-dir; \
    else \
      mkdir -p /sbom-dir/app && \
      printf '{\n  "enabled": false,\n  "message": "SBOM generation is disabled for the default build. Use ENABLE_SBOM=true or just build-sbom."\n}\n' > /sbom-dir/app/sbom-status.json; \
    fi

###############################################################################
# Stage 2: Container
#
# Minimal Debian base + Nix store from Stage 1 + openclaw on top.
# The Nix store must stay at /nix/store — all Nix binaries use absolute paths.
###############################################################################
FROM debian:bookworm-slim AS container
ARG NYX_NIX_SYSTEM
ARG OPENCLAW_VERSION
ARG QWEN_CODE_VERSION
ARG ENABLE_SBOM
ARG SBOM_PATH

# Import the Nix store with all pinned packages
COPY --from=nix-builder /nix/store /nix/store

# The content layer: symlinks from /nix-env/bin → /nix/store/…/bin/node etc.
COPY --from=nix-builder /nix-content /nix-env
COPY --from=sbom-builder /sbom-dir/app /app

# Expose Nix tools on PATH and set SSL certs
ENV PATH=/nix-env/bin:/usr/local/bin:/usr/bin:/bin
ENV SSL_CERT_FILE=/nix-env/etc/ssl/certs/ca-bundle.crt
ENV HOME=/root
ENV CI=true

LABEL org.opencontainers.image.title="nyx" \
      org.opencontainers.image.description="Hybrid Nix + Docker runtime for OpenClaw with persistent /data state." \
      org.opencontainers.image.sbom="${SBOM_PATH}" \
      io.github.netlooker.nyx.build-info="/app/build-info.json" \
      io.github.netlooker.nyx.nix-system="${NYX_NIX_SYSTEM}" \
      io.github.netlooker.nyx.sbom.enabled="${ENABLE_SBOM}" \
      io.github.netlooker.nyx.sbom.path="${SBOM_PATH}" \
      io.github.netlooker.nyx.openclaw.version="${OPENCLAW_VERSION}" \
      io.github.netlooker.nyx.qwen-code.version="${QWEN_CODE_VERSION}"

# FHS compat: npm scripts and shebangs expect /bin/sh and /usr/bin/env
RUN ln -sf /nix-env/bin/bash /bin/sh && \
    ln -sf /nix-env/bin/env /usr/bin/env

# Redirect npm global prefix to /usr/local so the binary lands in /usr/local/bin
# (already on PATH). Without this, npm uses the Nix store's node prefix which has
# a hash-based path unknown at runtime. just build resolves latest tags to concrete
# versions before invoking docker compose so labels and build-info stay auditable.
RUN npm config set prefix /usr/local && \
    npm install -g "openclaw@${OPENCLAW_VERSION}" && \
    npm install -g "@qwen-code/qwen-code@${QWEN_CODE_VERSION}" && \
    node -e "const fs=require('fs'); const sbomEnabled=process.env.ENABLE_SBOM === 'true'; const info={nixSystem: process.env.NYX_NIX_SYSTEM, openclaw: {requested: process.env.OPENCLAW_VERSION, resolved: require('/usr/local/lib/node_modules/openclaw/package.json').version}, qwenCode: {requested: process.env.QWEN_CODE_VERSION, resolved: require('/usr/local/lib/node_modules/@qwen-code/qwen-code/package.json').version}, sbom: {enabled: sbomEnabled, path: sbomEnabled ? process.env.SBOM_PATH : null, statusPath: sbomEnabled ? null : '/app/sbom-status.json'}}; fs.writeFileSync('/app/build-info.json', JSON.stringify(info, null, 2));"

# Config mounted from host (directory mount, not file — avoids EBUSY on rename)
ENV OPENCLAW_CONFIG_PATH=/config/openclaw.json5

# Persist gh CLI auth across rebuilds — token survives in the /data volume
ENV GH_CONFIG_DIR=/data/gh

# All openclaw state: databases, agent sandboxes, sessions, downloaded files.
# Mounted as a volume so it survives container rebuilds and is backed up on Mac.
ENV OPENCLAW_STATE_DIR=/data

EXPOSE 18789

# Workspace instructions — seeded into /data/workspace on first boot by entrypoint.sh
COPY container/WORKSPACE.md /app/WORKSPACE.md

# Entrypoint creates workspace structure, seeds docs, and symlinks tool configs.
COPY container/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["openclaw", "gateway", "run"]
