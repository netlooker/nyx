# NyxClaw 🐾

Welcome to the **NyxClaw** repository—a fully declarative, mathematically reproducible, and securely sandboxed integration of the [OpenClaw](https://github.com/openclaw/openclaw) AI agent framework, powered entirely by Nix!

By abandoning traditional, bloated Docker containers in favor of Nix's native `devShell` and functional dependencies, NyxClaw achieves:
* **True Reproducibility:** Every dependency (Python, Node.js, C++ compilers) is locked. It compiles byte-for-byte identical on `aarch64-darwin` (Mac) and `aarch64-linux` (NixOS).
* **Native Sandboxing:** Code executed by the AI agent is inherently trapped within the exact toolchains provided by the pure Nix environment.
* **Declarative Configuration:** Out-of-band JSON5 secret injection (`OPENCLAW_CONFIG_PATH`) keeps your API keys off the GitHub repository and out of the `/nix/store`.

## Repository Structure

To keep the system architecture clean, this repository is split into two primary environments:

# NyxClaw 🐾

Welcome to the **NyxClaw** repository—a fully declarative, mathematically reproducible, and securely sandboxed integration of the [OpenClaw](https://github.com/openclaw/openclaw) AI agent framework.

NyxClaw utilizes the massive power of **Nix** strictly to build the ultimate, immutable **Docker Image**. This gives you the speed and usability of standard Docker deployments, but completely eliminates traditional Docker build rot and vulnerabilities!

## The User Story (Clone & Bake)

Our deployment philosophy is radically simple: **Clone, Config, and Bake.** 

1. **Clone:** Fork or clone this repository to your local machine.
2. **Config:** Add your local inference nodes (like Ollama or LLama.cpp) and messaging channels (Telegram, WhatsApp) into your heavily-ignored `secrets/openclaw.json5` configuration.
3. **Bake the OS:** Navigate into `nyxclaw_env` and run `nix build .#base-image && docker load -i result`. This uses pure Nix to dynamically generate a mathematically pristine OS base containing your compilers and a cryptographic `bombon` SBOM.
4. **Bake the Agent:** Return to the root and run `docker build -t nyxclaw-agent -f nyxclaw_env/Dockerfile .`. This imperative build seamlessly inherits your pure OS!
5. **Run:** Deploy the container anywhere! Map the internal `/data` volume to your host to ensure the agent's memory, downloaded files, and SQLite databases persist forever between reboots.

The resulting Docker Image can be pushed to any cloud provider or orchestrator, fully equipped with native bridge networking to communicate with your APIs!

👉 **Deploy Now:** Read the [NyxClaw Deployment Manual](GUIDE.md) to instantly build your agent!

---
*Built securely for the modern AI engineering stack.*
