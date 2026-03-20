# Architectural Thesis: The Pragmatic Hybrid Container

When containerizing the **NyxClaw** AI Gateway, we faced a philosophical crossroad: Should we enforce absolute Nix purity across the entire stack, or rely entirely on imperative Dockerfiles? 

We chose a highly specialized **Hybrid Architecture** known as **Base Layer Transparency**. 

## The Purity Problem: Fast-Moving Monorepos
In a pure Nix derivation (`pkgs.dockerTools`), the build sandbox completely strips network access to guarantee strict functional determinism. To compile the expansive [OpenClaw](https://github.com/openclaw/openclaw) TypeScript framework inside this sandbox, we would be forced to use `buildNpmPackage` or `dream2nix`. 

This requires maintaining fixed-output derivation (FOD) cryptographic hashes for an absolutely massive `pnpm-workspace` block. Every single time an upstream ecosystem package updates a deep transitive dependency, the Nix build shatters until the specific tree hash is painstakingly regenerated. Expecting end-users to manage Node.js cryptographic lockfiles just to deploy an AI agent is operationally fatal.

## The Solution: Base Layer Transparency

Instead of forcing Nix to battle the chaotic NPM dependencies, we explicitly split the container architecture across two operational boundaries: **The O/S Foundation (Pure)** and **The Application Space (Impure)**.

### 1. The Pure OS Base (`bombon` SBOM)
We use Nix exclusively for what it is unequivocally best at: **Toolchain Reproducibility**. 

Our `flake.nix` dynamically executes `dockerTools.buildLayeredImage` to produce a naked Docker container holding *only* the C++ compilers (required for compiling native Node modules like `sqlite3` and WebSocket bindings), the exact Node.js interpreter, Python 3 environments, and `pnpm`. 

Because this foundational layer has zero transitive network dependencies, it is mathematically pure. This allows us to inject the [`bombon`](https://github.com/nikstur/bombon) generator directly into the Flake evaluation. Nix introspectively traverses the entire C/Python base dependency graph and bakes the resulting Software Bill of Materials (SBOM) natively into the Docker OCI Metadata Labels (`Config.Labels["SBOM"]`).

### 2. The Application Space (`syft` SBOM)
We then utilize an imperative `Dockerfile` which natively inherits from our pure Nix image (`FROM nyxclaw-base-image`). 

During the `docker build` phase, we execute `pnpm install` *with* network access. We bypass the brutal lockfile FOD hashing entirely, granting instantaneous and friction-free builds. 

Because we lose the pure Nix `bombon` graph generation in this imperative layer, we appended `syft` to the underlying Nix environment. Immediately following compilation, the Dockerfile executes a `syft scan` natively across the active node workspace, dynamically generating a secondary CycloneDX cryptographic SBOM specifically covering the application space (`/app/sbom.json`).

## The Result
1. **Total Transparency:** We achieve cryptographic awareness across both the O/S layer (via Nix declarative labels) and the App layer (via dynamic Syft scans).
2. **Zero Maintenance Friction:** The pure C++ base layer rarely changes, meaning the Nix hashes stay perfectly intact, while the fast-moving `pnpm` ecosystem builds seamlessly via standard Docker network access.
3. **The Best of Both Worlds:** Nix purists retain perfect, auditable control over system binaries, and developers retain the immediate workflow iteration of `docker build`.
