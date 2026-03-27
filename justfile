# Nyx — task runner
# Install just: nix develop (it's in the devShell)

# Build the brain container (includes Nix base layer via multi-stage build)
build:
    docker compose -f brain/docker-compose.yml build

# Start the brain
up:
    docker compose -f brain/docker-compose.yml up -d

# Stop the brain
down:
    docker compose -f brain/docker-compose.yml down

# Tail logs
logs:
    docker compose -f brain/docker-compose.yml logs -f

# Rebuild and restart (no cache)
rebuild:
    docker compose -f brain/docker-compose.yml build --no-cache
    docker compose -f brain/docker-compose.yml up -d

# Restart without rebuilding
restart:
    docker compose -f brain/docker-compose.yml restart
