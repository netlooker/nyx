# Nyx — task runner
# Install just: nix develop (it's in the devShell)

# Build and load the standalone Nix base image tarball
build-base:
    system="${NYX_NIX_SYSTEM:-aarch64-linux}"; \
    nix build ".#packages.$system.base-image" && \
    docker load < result

# Build and load the standalone Nix base image tarball with an SBOM artifact
build-base-sbom:
    system="${NYX_NIX_SYSTEM:-aarch64-linux}"; \
    nix build ".#packages.$system.base-image-sbom" && \
    docker load < result

# Build the container (includes Nix base layer via multi-stage build)
build:
    system="${NYX_NIX_SYSTEM:-aarch64-linux}"; \
    openclaw_version="${OPENCLAW_VERSION:-$(npm view openclaw version)}"; \
    qwen_code_version="${QWEN_CODE_VERSION:-$(npm view @qwen-code/qwen-code version)}"; \
    synapse_version="${SYNAPSE_VERSION:-$(nix eval --raw ".#packages.$system.synapse.src.rev")}"; \
    NYX_NIX_SYSTEM="$system" OPENCLAW_VERSION="$openclaw_version" QWEN_CODE_VERSION="$qwen_code_version" SYNAPSE_VERSION="$synapse_version" ENABLE_SBOM=false SBOM_PATH="" \
      docker compose -f container/docker-compose.yml build

# Build the container with the optional bombon SBOM path enabled
build-sbom:
    system="${NYX_NIX_SYSTEM:-aarch64-linux}"; \
    openclaw_version="${OPENCLAW_VERSION:-$(npm view openclaw version)}"; \
    qwen_code_version="${QWEN_CODE_VERSION:-$(npm view @qwen-code/qwen-code version)}"; \
    synapse_version="${SYNAPSE_VERSION:-$(nix eval --raw ".#packages.$system.synapse.src.rev")}"; \
    NYX_NIX_SYSTEM="$system" OPENCLAW_VERSION="$openclaw_version" QWEN_CODE_VERSION="$qwen_code_version" SYNAPSE_VERSION="$synapse_version" ENABLE_SBOM=true SBOM_PATH="/app/sbom-base.json" \
      docker compose -f container/docker-compose.yml build

# Start the container
up:
    docker compose -f container/docker-compose.yml up -d

# Stop the container
down:
    docker compose -f container/docker-compose.yml down

# Tail logs
logs:
    docker compose -f container/docker-compose.yml logs -f

# Rebuild and restart (no cache)
rebuild:
    system="${NYX_NIX_SYSTEM:-aarch64-linux}"; \
    openclaw_version="${OPENCLAW_VERSION:-$(npm view openclaw version)}"; \
    qwen_code_version="${QWEN_CODE_VERSION:-$(npm view @qwen-code/qwen-code version)}"; \
    synapse_version="${SYNAPSE_VERSION:-$(nix eval --raw ".#packages.$system.synapse.src.rev")}"; \
    NYX_NIX_SYSTEM="$system" OPENCLAW_VERSION="$openclaw_version" QWEN_CODE_VERSION="$qwen_code_version" SYNAPSE_VERSION="$synapse_version" ENABLE_SBOM=false SBOM_PATH="" \
      docker compose -f container/docker-compose.yml build --no-cache
    docker compose -f container/docker-compose.yml up -d

# Rebuild and restart with SBOM generation enabled
rebuild-sbom:
    system="${NYX_NIX_SYSTEM:-aarch64-linux}"; \
    openclaw_version="${OPENCLAW_VERSION:-$(npm view openclaw version)}"; \
    qwen_code_version="${QWEN_CODE_VERSION:-$(npm view @qwen-code/qwen-code version)}"; \
    synapse_version="${SYNAPSE_VERSION:-$(nix eval --raw ".#packages.$system.synapse.src.rev")}"; \
    NYX_NIX_SYSTEM="$system" OPENCLAW_VERSION="$openclaw_version" QWEN_CODE_VERSION="$qwen_code_version" SYNAPSE_VERSION="$synapse_version" ENABLE_SBOM=true SBOM_PATH="/app/sbom-base.json" \
      docker compose -f container/docker-compose.yml build --no-cache
    docker compose -f container/docker-compose.yml up -d

# Restart without rebuilding
restart:
    docker compose -f container/docker-compose.yml restart

# Show openclaw status (channels, sessions, context usage)
status:
    docker compose -f container/docker-compose.yml exec nyx openclaw status

# Validate the repo contract without mutating tracked files
check:
    system="${NYX_NIX_SYSTEM:-aarch64-linux}"; \
    docker compose -f container/docker-compose.yml config >/dev/null && \
    sh -n container/entrypoint.sh && \
    nix flake show --all-systems >/dev/null && \
    nix eval --raw ".#packages.$system.base-content.name" >/dev/null && \
    grep -q 'io.github.netlooker.nyx.build-info' container/Dockerfile

# Validate the optional SBOM derivation separately from the default build path
check-sbom:
    system="${NYX_NIX_SYSTEM:-aarch64-linux}"; \
    nix eval --raw ".#packages.$system.sbom-dir.name" >/dev/null

# Bump synapse to the latest main commit and rewrite flake.nix (rev + hash + version date)
update-synapse:
    #!/usr/bin/env bash
    set -euo pipefail
    new_rev="$(git ls-remote https://github.com/netlooker/synapse.git main | cut -f1)"
    echo "latest main: $new_rev"
    current_rev="$(grep -oE 'rev = "[0-9a-f]{40}"' flake.nix | head -1 | cut -d'"' -f2)"
    if [ "$new_rev" = "$current_rev" ]; then
      echo "already up to date ($current_rev)"
      exit 0
    fi
    echo "prefetching sha256…"
    prefetch="$(nix shell nixpkgs#nix-prefetch-github --command nix-prefetch-github netlooker synapse --rev "$new_rev")"
    new_hash="$(printf '%s' "$prefetch" | grep -oE '"hash": "[^"]+"' | cut -d'"' -f4)"
    old_hash="$(grep -oE 'hash = "sha256-[^"]+"' flake.nix | head -1 | cut -d'"' -f2)"
    today="$(date +%Y-%m-%d)"
    echo "rev:  $current_rev → $new_rev"
    echo "hash: $old_hash → $new_hash"
    sed -i.bak \
      -e "s|rev = \"$current_rev\"|rev = \"$new_rev\"|" \
      -e "s|hash = \"$old_hash\"|hash = \"$new_hash\"|" \
      -e "s|version = \"0-unstable-[0-9-]\{10\}\"|version = \"0-unstable-$today\"|" \
      flake.nix
    rm -f flake.nix.bak
    echo "flake.nix updated — run 'just build' to rebuild the image"
