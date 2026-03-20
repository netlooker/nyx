# NyxClaw: Cloud-Native AI Agent Deployment

NyxClaw is a highly-optimized, declarative environment for deploying the [OpenClaw](https://github.com/openclaw/openclaw) agent framework natively as an immutable Docker container. 

Instead of dealing with unpredictable toolchains or complex Dockerfiles, NyxClaw uses **Nix** under the hood to mathematically calculate and compile your agent's dependencies into a perfectly sealed, production-ready artifact that you can deploy anywhere!

## The "Clone & Bake" Pipeline

Ready to deploy your agent to a VPS, Kubernetes, or cloud provider? NyxClaw uses an immutable "Clone & Bake" workflow.

### Step 1: Clone & Configure
First, clone the repository and scaffold your local configuration file. 
```bash
git clone https://github.com/netlooker/nyx.git
cd nyx
cp nyxclaw_env/openclaw.example.json5 nyxclaw_env/secrets/openclaw.json5
```

Open `secrets/openclaw.json5` in your editor. This file is natively git-ignored to keep your secrets safe.
* **Add Providers**: Uncomment local nodes (`models.providers.ollama`) or add API keys (`openai`, `anthropic`).
* **Add Channels**: Uncomment `channels.telegram` and add your `botToken`.

### Step 2: Bake the Container
NyxClaw utilizes a "Base Layer Transparency" pattern. First, we use Nix to deterministically calculate and compile a pure Operating System and Toolchain base image containing mathematical hashes for every dependency.

1. Generate the foundational pure OS base image securely. To avoid Mac/Windows architecture mismatches, we run the Nix build identically inside a disposable Linux container:
   ```bash
   cd nyx
   docker run --rm -v $(pwd):/app -w /app/nyxclaw_env nixos/nix:latest sh -c "mkdir -p /etc/nix && echo 'experimental-features = nix-command flakes' >> /etc/nix/nix.conf && nix build .#base-image && cp -L result nyxclaw-base-image.tar.gz"
   docker load -i nyxclaw_env/nyxclaw-base-image.tar.gz
   ```
2. Once your configurations are perfect, bake the complete agent application on top of the foundation! Navigate to the **root** of your repository:
   ```bash
   cd ../
   docker build -t nyxclaw-agent -f nyxclaw_env/Dockerfile .
   ```
   *Behind the scenes, this standard Docker build is empowered by the mathematical guarantees of the base image. It natively inherits all locked toolchains and embeds an Application Layer SBOM inside `/app/sbom-app.json`.*

### Step 3: Security Auditing & SBOMs (Optional)
The NyxClaw architecture natively produces dual-layered Software Bill of Materials for your security scanners (like Trivy or Grype).
* **The OS SBOM:** The foundational OS layer generates a pure `bombon` SBOM. You can extract it directly from the base image structure.
* **The App SBOM:** To extract the dynamic `cyclonedx-json` metadata strictly containing the Node module tree of the openclaw agent:
   ```bash
   docker run --rm --entrypoint cat nyxclaw-agent /app/sbom-app.json > sbom-app.json
   ```

### Step 4: Start the Agent
Run your immutable agent container. NyxClaw uses `/data` internally to store all agent memories, SQLite databases, and downloaded files. We map this to `./nyx-data` on your host so your agent never suffers amnesia between restarts!
   
   **Standard Gateway (Backgrounded):**
   ```bash
   docker run -d -v ./nyx-data:/data --name nyxclaw-bot nyxclaw-agent
   ```

   **Web UI Mode (Browser Interface):** 
   If you uncommented the `gateway` block in `openclaw.json5` (binding to `0.0.0.0` and setting a password), map port `18789` to your host to access the Web UI:
   ```bash
   docker run -d -v ./nyx-data:/data -p 18789:18789 --name nyxclaw-bot nyxclaw-agent
   ```
   *Navigate to `http://localhost:18789` in your browser and use the password you configured to authorize!*

   **Interactive Terminal / TUI Mode:** 
   If you didn't configure a messenger like Telegram, you can run the agent locally via its incredible Terminal UI (skip the `-d` and use `-it`, and override the default `gateway` command with `tui`):
   ```bash
   docker run -it -v ./nyx-data:/data nyxclaw-agent pnpm start tui
   ```

If using Telegram, send a message to your bot. Check the container logs for the pairing code to securely bind your account:
```bash
docker logs -f nyxclaw-bot
```

---

## Advanced: Local Native Development
For AI engineers developing custom capabilities or experimenting with the framework locally (without rebuilding Docker containers constantly), NyxClaw provides a pure development harness.

### Enter the Environment
Navigate to the `nyxclaw_env` directory and spawn the Nix shell:
```bash
cd nyxclaw_env
nix develop
```
*Nix provides the exact underlying C++ compilers and interpreters (`python3`, `nodejs`, `pnpm`), locking local development parity with the Docker container.*

### Run Natively
Once inside the Nix shell with Node dependencies compiled (`pnpm install && pnpm build`), you can execute the agent natively without Docker:
```bash
cd openclaw
pnpm start gateway
```

Enjoy your lightning-fast, highly secure, natively compiled agent framework!
