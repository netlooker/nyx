# Inherit practically perfect toolchains from our mathematically pure Nix base layer
# This base image is generated manually via: `nix build .#base-image && docker load -i result`
FROM nyxclaw-base-image:latest

# Set the working directory inside the container
WORKDIR /app

# Copy the entire mono-repository footprint into the container
# This natively captures your custom `secrets/openclaw.json5` configuration!
COPY . /app

# The Unix environment is generated natively by the Base Layer.
# We assign a valid home directory since mathematically pure Nix layers do not ship a traditional `/root` user.
ENV HOME=/app

# Suppress all interactive prompts so pnpm can forcefully overwrite injected Mac modules directories
ENV CI=true

# Execute pnpm identically to how you would structure standard Docker workflows!
# Note: Since the Nix OS mathematically guarantees our pnpm version inherently, we purge the Corepack 
# `packageManager` directive from package.json to avoid FHS binary dynamic linker `ENOENT` crashing!
RUN cd nyxclaw_env/openclaw && node -e "let fs=require('fs'); let p=JSON.parse(fs.readFileSync('package.json')); delete p.packageManager; fs.writeFileSync('package.json', JSON.stringify(p, null, 2))" && pnpm install && pnpm build && cd ../.. && syft scan dir:./nyxclaw_env/openclaw -o cyclonedx-json=/app/sbom-app.json

# Hardcode the OpenClaw configuration path specifically targeting the baked-in config
ENV OPENCLAW_CONFIG_PATH=/app/nyxclaw_env/secrets/openclaw.json5

# Force all OpenClaw databases, workspaces, and downloaded files into a single, volume-mountable directory
ENV OPENCLAW_STATE_DIR=/data

# Expose the default OpenClaw Gateway & WebUI port
EXPOSE 18789

# The default runtime command launches the OpenClaw gateway securely through pure Node execution!
CMD ["bash", "-c", "cd nyxclaw_env/openclaw && pnpm start gateway"]
