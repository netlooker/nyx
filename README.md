# NyxClaw 🐾

Welcome to the **NyxClaw** repository—a fully declarative, mathematically reproducible, and securely sandboxed integration of the [OpenClaw](https://github.com/openclaw/openclaw) AI agent framework.

NyxClaw utilizes the massive power of **Nix** strictly to build the ultimate, immutable **Docker Image**. This gives you the speed and usability of standard Docker deployments, but completely eliminates traditional Docker build rot and vulnerabilities!

## The User Story (Clone & Bake)

Our deployment philosophy is radically simple: **Clone, Config, and Bake.** 

1. **Clone:** Fork or clone this repository to your local machine.
2. **Config:** Add your local inference nodes (like Ollama or LLama.cpp) and messaging channels (Telegram, WhatsApp) into your heavily-ignored `secrets/openclaw.json5` configuration.
3. **Bake the OS:** In the root directory, run `docker run --rm -v $(pwd):/app -w /app/nyxclaw_env nixos/nix:latest sh -c "mkdir -p /etc/nix && echo 'experimental-features = nix-command flakes' >> /etc/nix/nix.conf && nix build .#base-image && cp -L result nyxclaw-base-image.tar.gz"` followed by `docker load -i nyxclaw_env/nyxclaw-base-image.tar.gz`. This generates a mathematically pristine OS base containing your compilers and a cryptographic `bombon` SBOM.
4. **Bake the Agent:** Return to the root and run `docker build -t nyxclaw-agent -f nyxclaw_env/Dockerfile .`. This imperative build seamlessly inherits your pure OS!
5. **Run:** Deploy the container anywhere! Map the internal `/data` volume to your host to ensure the agent's memory persists forever, and map your `secrets/` directory so you can hot-reload your runtime configuration (`openclaw.json5`) without rebuilding! (`docker run -d -v ./nyx-data:/data -v $(pwd)/nyxclaw_env/secrets:/app/nyxclaw_env/secrets nyxclaw-agent`).

The resulting Docker Image can be pushed to any cloud provider or orchestrator, fully equipped with native bridge networking to communicate with your APIs!

👉 **Deploy Now:** Read the [NyxClaw Deployment Manual](GUIDE.md) to instantly build your agent!

---
*Built securely for the modern AI engineering stack.*
