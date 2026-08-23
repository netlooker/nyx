# Architecture: Docker-Only Appliance

## Runtime Shape

Nyx is a plain Docker Compose appliance. The main image starts from `debian:bookworm-slim` and installs:

- Node.js 22 from NodeSource
- OpenClaw and Qwen Code with npm
- Hermes, Scrapling, Synapse, and Sonar with uv
- common runtime tools with apt

This keeps one system libc and one system library owner. Python wheels, Playwright, npm packages, and OS packages all run against Debian's runtime instead of a mixed packaging ABI surface.

## Version Resolution

`versions.env` contains requested selectors. `just build` resolves floating selectors before Docker runs:

- npm packages via `npm view`
- Scrapling via PyPI JSON
- Hermes, Synapse, and Sonar refs via `git ls-remote`

Docker receives concrete build args and writes `/app/build-info.json` with requested and resolved values. Image labels point to that metadata and expose the selected app versions.

SBOM generation is intentionally out of scope for this appliance pass. The
tracked build contract is the image plus Docker labels and `/app/build-info.json`.

## Persistent State

Config is mounted as a directory (`secrets/` -> `/config`), not a single file. The selected orchestrator reads config from there without per-file bind mount churn.

Runtime state is mounted as `data/` -> `/data`:

- OpenClaw databases, sessions, sandboxes, and downloads
- Hermes state under `/data/hermes`
- agent workspace under `/data/workspace`
- GitHub CLI auth under `/data/gh`
- Qwen Code config under `/data/qwen`
- Scrapling browser backends under `/data/scrapling`

The container is disposable. The data volume is the appliance state.

## Entrypoint Duties

`container/entrypoint.sh` runs before the selected orchestrator starts. It:

- creates the workspace directory structure
- symlinks Qwen's hardcoded `$HOME/.qwen` to `/data/qwen`
- ensures `/config/synapse.toml` and `/config/sonar.toml` exist
- starts the Synapse admin console when enabled
- symlinks image-baked skills/subagents into the workspace
- downloads Scrapling browser backends on first boot in the background
- dispatches to `openclaw gateway run` or `hermes gateway run` when `CMD` is `nyx-orchestrator`

## Tool Paths

Image-installed tools use stable absolute paths under `/usr/local/bin`, for example:

- `/usr/local/bin/openclaw`
- `/usr/local/bin/hermes`
- `/usr/local/bin/qwen`
- `/usr/local/bin/synapse-mcp`
- `/usr/local/bin/sonar-mcp`
- `/usr/local/bin/scrapling`

Config examples prefer these absolute paths so agent subprocesses are not sensitive to shell PATH inheritance.

## Host Requirements

The host only needs Docker with Compose and `just`. The repository does not
ship or require a local package-manager environment; all runtime tools are
installed into the image.
