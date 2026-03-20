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
# This guarantees that Node/Python versions and compilation chains exactly match the host OS blueprint
RUN nix develop ./nyxclaw_env --command bash -c "cd nyxclaw_env/openclaw && pnpm install && pnpm build"

# Hardcode the OpenClaw configuration path specifically targeting the baked-in config
ENV OPENCLAW_CONFIG_PATH=/app/nyxclaw_env/secrets/openclaw.json5

# Expose the default OpenClaw Gateway & WebUI port
EXPOSE 18789

# Overwrite the container entrypoint to automatically trap any executed commands inside the safe Nix shell
ENTRYPOINT ["nix", "develop", "./nyxclaw_env", "--command", "bash", "-c"]

# The default runtime command launches the OpenClaw gateway framework
CMD ["cd nyxclaw_env/openclaw && pnpm start gateway"]
