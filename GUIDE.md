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
Once your configurations are perfect, bake the entire environment into a strictly isolated, production-ready Docker container!
```bash
docker build -t nyxclaw-agent -f nyxclaw_env/Dockerfile .
```
*Behind the scenes, the Dockerfile triggers the absolute reproducibility of a pure Nix shell to compile your agent natively without any host pollution!*

### Step 3: Start the Agent
Run your immutable agent container anywhere! It possesses standard bridge networking out-of-the-box (allowing it to hit public internet APIs or route to a local `http://192.168.1.x:11434` Ollama instance):
```bash
docker run -d --name nyxclaw-bot nyxclaw-agent
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
