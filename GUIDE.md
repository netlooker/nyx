# NyxClaw: The Declarative AI Agent Environment

NyxClaw is a native, declarative integration of the [OpenClaw](https://github.com/openclaw/openclaw) agent framework powered by [Nix](https://nixos.org/). It replaces the heavy reliance on Docker containers and NVIDIA orchestrators by utilizing Nix's native `devShell` capabilities to provide a fully sandboxed, reproducible execution environment for your AI agents.

## Getting Started

### 1. Enter the Environment
Navigate to the `nyxclaw_env` directory. If you have `direnv` installed (and allowed via `direnv allow`), the environment will automatically load! Otherwise, manually spawn the declarative shell:
```bash
cd nyxclaw_env
nix develop
```
*Note: The environment is cross-platform optimized and compiles cleanly on both your local MacOS host (`aarch64-darwin`) and the production NixOS VM (`aarch64-linux`).*

### 2. Managing Dependencies
Unlike extremely rigid Nix python/node derivations, NyxClaw takes a pragmatic approach. Nix provides the underlying C++ compilers (`gcc`, `cmake`, `pkg-config`) and exact interpreters (`python3`, `nodejs`, `pnpm`), but leaves you free to use standard package managers sequentially!

*   **Node.js**: You can freely run `pnpm install` inside the `openclaw` directory.
*   **Python**: `direnv` automatically scaffolds a virtual environment (`.venv`) allowing for standard `pip install` workflows for your ML models.

### 3. The Native Nix OS Sandbox (No Docker Required)
By default, OpenClaw securely sandboxes external code execution by spinning up Docker containers (`docker run`). 

NyxClaw elegantly bypasses this overhead configuration! When you instantiate the shell via `nix develop` (or seamlessly enter via `direnv`), the Nix `shellHook` binds `<project>/secrets/openclaw.json5` safely to your environment using the native `OPENCLAW_CONFIG_PATH` flag.

If you don't have a configuration file, Nix will automatically copy `openclaw.example.json5` into your hidden `secrets/` folder during startup! 

*   **Zero Leakage:** The `secrets/` directory is locally ignored by Git. You can safely add your API keys right into `secrets/openclaw.json5`.
*   **Sandbox Disabled (`mode: 'off'`):** The default template disables Docker, relying squarely on the boundaries injected by our Nix environment. When your AI agent attempts to evaluate shell codes, it securely traps itself inside the compiler chains and node packages provided strictly by the pure environment.
*   **JSON5 Superpowers:** Unlike standard JSON, the `json5` format allows you to write single-line comments (`// API Key here`), use single quotes (`'off'`), and safely leave unquoted keys! This makes configuring OpenClaw manually vastly superior and error-resistant.

### 4. Launching the Agent
Once inside the Nix shell with Node dependencies compiled, you can execute the agent natively:
```bash
cd nyxclaw_env/openclaw
pnpm start --help
```

From here, you can link the agent to your designated messaging channels (Telegram, WhatsApp, Signal) or interface with it securely via the local terminal `pnpm start tui`!

Enjoy your lightning-fast, highly secure, Docker-free AI native operating system!
