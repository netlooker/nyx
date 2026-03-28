# Nyx — task runner
# Install just: nix develop (it's in the devShell)

# Build the cortex container (includes Nix base layer via multi-stage build)
build:
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
    docker compose -f cortex/docker-compose.yml build --no-cache
    docker compose -f cortex/docker-compose.yml up -d

# Restart without rebuilding
restart:
    docker compose -f cortex/docker-compose.yml restart
