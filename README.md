# NyxClaw 🐾

Welcome to the **NyxClaw** repository—a fully declarative, mathematically reproducible, and securely sandboxed integration of the [OpenClaw](https://github.com/openclaw/openclaw) AI agent framework, powered entirely by Nix!

By abandoning traditional, bloated Docker containers in favor of Nix's native `devShell` and functional dependencies, NyxClaw achieves:
* **True Reproducibility:** Every dependency (Python, Node.js, C++ compilers) is locked. It compiles byte-for-byte identical on `aarch64-darwin` (Mac) and `aarch64-linux` (NixOS).
* **Native Sandboxing:** Code executed by the AI agent is inherently trapped within the exact toolchains provided by the pure Nix environment.
* **Declarative Configuration:** Out-of-band JSON5 secret injection (`OPENCLAW_CONFIG_PATH`) keeps your API keys off the GitHub repository and out of the `/nix/store`.

## Repository Structure

To keep the system architecture clean, this repository is split into two primary environments:

### 1. The NyxClaw Agent Environment (`/nyxclaw_env`)
This is the core of the project. It contains the Nix Flake necessary to bootstrap the OpenClaw agent natively, compile its dependencies, and run it. It also includes the `Dockerfile` for our "Clone & Bake" production deployment pipeline.

👉 **Start Here:** Read the [NyxClaw Declarative Guide](GUIDE.md) to learn how to instantly launch OpenClaw using `nix develop` or deploy it using Docker.

### 2. The NixOS System Configuration (`/nixos-config`)
For users who want to run NyxClaw on a dedicated, bare-metal virtual machine, we provide a mathematically reproducible NixOS system configuration optimized for VMware Fusion on Apple Silicon.

👉 **System Setup:** Read the [NixOS Installation Manual](nixos-config/README.md) for instructions on bootstrapping the base operating system from a live USB.

---
*Built securely for the modern AI engineering stack.*
