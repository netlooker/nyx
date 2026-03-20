# Use the official NixOS Nix image to guarantee ultimate build reproducibility
FROM nixos/nix:latest

# Set the working directory inside the container
WORKDIR /app

# Enable Nix flakes locally within the container context
RUN mkdir -p /etc/nix && echo "experimental-features = nix-command flakes" >> /etc/nix/nix.conf

# Copy the entire mono-repository footprint into the container
# This natively captures your custom `secrets/openclaw.json5` configuration!
COPY . /app

# Pre-build the OpenClaw AI agent natively INSIDE the isolated Nix development shell
# After compilation, Syft generates a CycloneDX Software Bill of Materials (SBOM) for the entire artifact
RUN nix develop ./nyxclaw_env --command bash -c "cd nyxclaw_env/openclaw && pnpm install && pnpm build && cd ../.. && syft scan dir:./nyxclaw_env/openclaw -o cyclonedx-json=/app/sbom.json"

# Hardcode the OpenClaw configuration path specifically targeting the baked-in config
ENV OPENCLAW_CONFIG_PATH=/app/nyxclaw_env/secrets/openclaw.json5

# Force all OpenClaw databases, workspaces, and downloaded files into a single, volume-mountable directory
ENV OPENCLAW_STATE_DIR=/data

# Expose the default OpenClaw Gateway & WebUI port
EXPOSE 18789

# Overwrite the container entrypoint to automatically trap any executed commands inside the safe Nix shell
ENTRYPOINT ["nix", "develop", "./nyxclaw_env", "--command", "bash", "-c"]

# The default runtime command launches the OpenClaw gateway framework
CMD ["cd nyxclaw_env/openclaw && pnpm start gateway"]
