# Nyx — task runner
# Install just from your package manager: https://just.systems/

set dotenv-load := false

_resolve_env:
    #!/usr/bin/env bash
    set -euo pipefail
    set -a
    source versions.env
    set +a
    openclaw_version="${OPENCLAW_VERSION:-latest}"
    if [ "$openclaw_version" = "latest" ]; then
      openclaw_version="$(npm view openclaw version)"
    fi
    qwen_code_version="${QWEN_CODE_VERSION:-latest}"
    if [ "$qwen_code_version" = "latest" ]; then
      qwen_code_version="$(npm view @qwen-code/qwen-code version)"
    fi
    scrapling_version="${SCRAPLING_VERSION:-latest}"
    if [ "$scrapling_version" = "latest" ]; then
      scrapling_version="$(curl -fsSL https://pypi.org/pypi/scrapling/json | jq -r .info.version)"
    fi
    synapse_ref="${SYNAPSE_REF:-main}"
    synapse_version="$(git ls-remote https://github.com/netlooker/synapse.git "$synapse_ref" | awk '{print $1}')"
    if [ -z "$synapse_version" ]; then
      synapse_version="$synapse_ref"
    fi
    sonar_ref="${SONAR_REF:-main}"
    sonar_version="$(git ls-remote https://github.com/netlooker/sonar.git "$sonar_ref" | awk '{print $1}')"
    if [ -z "$sonar_version" ]; then
      sonar_version="$sonar_ref"
    fi
    printf 'export NODE_MAJOR=%q\n' "${NODE_MAJOR:-22}"
    printf 'export UV_VERSION=%q\n' "${UV_VERSION:-0.11.2}"
    printf 'export OPENCLAW_VERSION=%q\n' "$openclaw_version"
    printf 'export QWEN_CODE_VERSION=%q\n' "$qwen_code_version"
    printf 'export SCRAPLING_VERSION=%q\n' "$scrapling_version"
    printf 'export SYNAPSE_REF=%q\n' "$synapse_ref"
    printf 'export SYNAPSE_VERSION=%q\n' "$synapse_version"
    printf 'export SONAR_REF=%q\n' "$sonar_ref"
    printf 'export SONAR_VERSION=%q\n' "$sonar_version"

# Build the Docker image with concrete, metadata-recorded tool versions.
build:
    #!/usr/bin/env bash
    set -euo pipefail
    eval "$(just _resolve_env)"
    docker compose -f container/docker-compose.yml build

# Start the stack
up:
    docker compose -f container/docker-compose.yml up -d

# Stop the stack
down:
    docker compose -f container/docker-compose.yml down

# Tail logs
logs:
    docker compose -f container/docker-compose.yml logs -f

# Rebuild and restart without Docker cache
rebuild:
    #!/usr/bin/env bash
    set -euo pipefail
    eval "$(just _resolve_env)"
    docker compose -f container/docker-compose.yml build --no-cache
    docker compose -f container/docker-compose.yml up -d

# Restart without rebuilding
restart:
    docker compose -f container/docker-compose.yml restart

# Show OpenClaw status (channels, sessions, context usage)
status:
    docker compose -f container/docker-compose.yml exec nyx openclaw status

# Validate the repo contract without mutating tracked files
check:
    docker compose -f container/docker-compose.yml config >/dev/null
    sh -n container/entrypoint.sh
    python3 -m py_compile scripts/e2e_openclaw_sonar_synapse.py
    grep -q 'io.github.netlooker.nyx.build-info' container/Dockerfile
    grep -q '/usr/local/bin/synapse-mcp' container/openclaw.json5.example
    grep -q '/usr/local/bin/sonar-mcp' container/openclaw.json5.example

# Prepare the deterministic-Sonar -> OpenClaw TUI -> Synapse e2e run layout and prompt
e2e-sonar-synapse-prepare:
    python3 scripts/e2e_openclaw_sonar_synapse.py prepare

# Rebuild Nyx, restart the stack, and prepare the deterministic-Sonar -> OpenClaw/Synapse e2e run
e2e-sonar-synapse-prepare-rebuild:
    python3 scripts/e2e_openclaw_sonar_synapse.py prepare --rebuild

# Re-run only the deterministic Sonar source-collection phase for an existing test id
e2e-sonar-synapse-collect-sources TEST_ID:
    python3 scripts/e2e_openclaw_sonar_synapse.py collect-sources --test-id {{TEST_ID}}

# Verify a completed deterministic-Sonar -> OpenClaw/Synapse e2e run
e2e-sonar-synapse-verify TEST_ID:
    python3 scripts/e2e_openclaw_sonar_synapse.py verify --test-id {{TEST_ID}}
