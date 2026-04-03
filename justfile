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

# Build the cortex container (includes Nix base layer via multi-stage build)
build:
    system="${NYX_NIX_SYSTEM:-aarch64-linux}"; \
    openclaw_version="${OPENCLAW_VERSION:-$(npm view openclaw version)}"; \
    qwen_code_version="${QWEN_CODE_VERSION:-$(npm view @qwen-code/qwen-code version)}"; \
    NYX_NIX_SYSTEM="$system" OPENCLAW_VERSION="$openclaw_version" QWEN_CODE_VERSION="$qwen_code_version" ENABLE_SBOM=false SBOM_PATH="" \
      docker compose -f cortex/docker-compose.yml build

# Build the cortex container with the optional bombon SBOM path enabled
build-sbom:
    system="${NYX_NIX_SYSTEM:-aarch64-linux}"; \
    openclaw_version="${OPENCLAW_VERSION:-$(npm view openclaw version)}"; \
    qwen_code_version="${QWEN_CODE_VERSION:-$(npm view @qwen-code/qwen-code version)}"; \
    NYX_NIX_SYSTEM="$system" OPENCLAW_VERSION="$openclaw_version" QWEN_CODE_VERSION="$qwen_code_version" ENABLE_SBOM=true SBOM_PATH="/app/sbom-base.json" \
      docker compose -f cortex/docker-compose.yml build

# Start the cortex
up:
    docker compose -f cortex/docker-compose.yml up -d

# Stop the cortex
down:
    docker compose -f cortex/docker-compose.yml down

# Tail logs
logs:
    docker compose -f cortex/docker-compose.yml logs -f

# Rebuild and restart (no cache)
rebuild:
    system="${NYX_NIX_SYSTEM:-aarch64-linux}"; \
    openclaw_version="${OPENCLAW_VERSION:-$(npm view openclaw version)}"; \
    qwen_code_version="${QWEN_CODE_VERSION:-$(npm view @qwen-code/qwen-code version)}"; \
    NYX_NIX_SYSTEM="$system" OPENCLAW_VERSION="$openclaw_version" QWEN_CODE_VERSION="$qwen_code_version" ENABLE_SBOM=false SBOM_PATH="" \
      docker compose -f cortex/docker-compose.yml build --no-cache
    docker compose -f cortex/docker-compose.yml up -d

# Rebuild and restart with SBOM generation enabled
rebuild-sbom:
    system="${NYX_NIX_SYSTEM:-aarch64-linux}"; \
    openclaw_version="${OPENCLAW_VERSION:-$(npm view openclaw version)}"; \
    qwen_code_version="${QWEN_CODE_VERSION:-$(npm view @qwen-code/qwen-code version)}"; \
    NYX_NIX_SYSTEM="$system" OPENCLAW_VERSION="$openclaw_version" QWEN_CODE_VERSION="$qwen_code_version" ENABLE_SBOM=true SBOM_PATH="/app/sbom-base.json" \
      docker compose -f cortex/docker-compose.yml build --no-cache
    docker compose -f cortex/docker-compose.yml up -d

# Restart without rebuilding
restart:
    docker compose -f cortex/docker-compose.yml restart

# Show openclaw status (channels, sessions, context usage)
status:
    docker compose -f cortex/docker-compose.yml exec cortex openclaw status

# Validate the repo contract without mutating tracked files
check:
    system="${NYX_NIX_SYSTEM:-aarch64-linux}"; \
    docker compose -f cortex/docker-compose.yml config >/dev/null && \
    sh -n cortex/entrypoint.sh && \
    nix flake show --all-systems >/dev/null && \
    nix eval --raw ".#packages.$system.base-content.name" >/dev/null && \
    rg -q 'io.github.netlooker.nyx.build-info' cortex/Dockerfile

# Validate the optional SBOM derivation separately from the default build path
check-sbom:
    system="${NYX_NIX_SYSTEM:-aarch64-linux}"; \
    nix eval --raw ".#packages.$system.sbom-dir.name" >/dev/null
