# syntax=docker/dockerfile:1

ARG UV_VERSION=0.11.2

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv-bin

FROM debian:bookworm-slim AS container

ARG NODE_MAJOR=22
ARG OPENCLAW_VERSION=latest
ARG QWEN_CODE_VERSION=latest
ARG SCRAPLING_VERSION=latest
ARG SYNAPSE_REF=main
ARG SYNAPSE_VERSION=main
ARG SONAR_REF=main
ARG SONAR_VERSION=main

ENV PATH=/usr/local/bin:/usr/bin:/bin
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV HOME=/root
ENV CI=true
ENV UV_TOOL_DIR=/opt/uv/tools
ENV UV_TOOL_BIN_DIR=/usr/local/bin

LABEL org.opencontainers.image.title="nyx" \
      org.opencontainers.image.description="Docker runtime for OpenClaw with persistent /data state." \
      io.github.netlooker.nyx.build-info="/app/build-info.json" \
      io.github.netlooker.nyx.openclaw.version="${OPENCLAW_VERSION}" \
      io.github.netlooker.nyx.qwen-code.version="${QWEN_CODE_VERSION}" \
      io.github.netlooker.nyx.scrapling.version="${SCRAPLING_VERSION}" \
      io.github.netlooker.nyx.synapse.version="${SYNAPSE_VERSION}" \
      io.github.netlooker.nyx.sonar.version="${SONAR_VERSION}"

COPY --from=uv-bin /uv /uvx /usr/local/bin/

# System runtime and utility surface. Node comes from NodeSource because
# OpenClaw requires Node >=22.14.0 and Debian bookworm's stock nodejs is older.
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates curl gnupg && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL "https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key" | \
      gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    printf 'deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_%s.x nodistro main\n' "${NODE_MAJOR}" > /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
      bash \
      bat \
      build-essential \
      cmake \
      curl \
      exiftool \
      fd-find \
      ffmpeg \
      file \
      findutils \
      gawk \
      gh \
      git \
      gnupg \
      htop \
      imagemagick \
      jq \
      less \
      libstdc++6 \
      nodejs \
      openssh-client \
      openssl \
      pandoc \
      pkg-config \
      python3 \
      python3-venv \
      ripgrep \
      sqlite3 \
      tree \
      unzip \
      wget \
      xz-utils \
      yq \
      zip && \
    ln -sf /usr/bin/fdfind /usr/local/bin/fd && \
    ln -sf /usr/bin/batcat /usr/local/bin/bat && \
    rm -rf /var/lib/apt/lists/*

# Install Playwright's Debian shared-library dependencies without downloading
# browser bundles into the image. `scrapling install` downloads Chromium and
# Camoufox into /data/scrapling on first boot.
RUN uv tool install --python /usr/bin/python3 "playwright" && \
    python_exec="${UV_TOOL_DIR}/playwright/bin/python" && \
    "$python_exec" -m playwright install-deps chromium && \
    uv tool uninstall playwright && \
    rm -rf /var/lib/apt/lists/*

# OpenClaw and Qwen Code are npm app-layer tools. The justfile resolves
# floating selectors to concrete versions before Docker runs.
RUN npm config set prefix /usr/local && \
    npm install -g "openclaw@${OPENCLAW_VERSION}" && \
    npm install -g "grammy" "@grammyjs/runner" "@grammyjs/transformer-throttler" && \
    npm install -g "@qwen-code/qwen-code@${QWEN_CODE_VERSION}"

# Python tool layer. Synapse/Sonar refs are resolved to concrete commits by
# `just build`, but Docker still accepts branch names for direct manual builds.
RUN if [ "${SCRAPLING_VERSION}" = "latest" ]; then \
      scrapling_spec="scrapling[all]"; \
    else \
      scrapling_spec="scrapling[all]==${SCRAPLING_VERSION}"; \
    fi && \
    uv tool install --python /usr/bin/python3 "$scrapling_spec" && \
    uv tool install --python 3.12 "synapse[api] @ git+https://github.com/netlooker/synapse.git@${SYNAPSE_VERSION}" && \
    uv tool install --python 3.12 "sonar[mcp] @ git+https://github.com/netlooker/sonar.git@${SONAR_VERSION}" && \
    "${UV_TOOL_DIR}/scrapling/bin/python" -c "from importlib.metadata import version; print(version('scrapling'))" > /app-scrapling-version.txt

# Compatibility wrappers for commands used by Nyx scripts and entrypoint logic.
RUN printf '#!/bin/sh\nexec /opt/uv/tools/synapse/bin/python -m uvicorn synapse.web_api:create_app --factory --host "${SYNAPSE_API_HOST:-0.0.0.0}" --port "${SYNAPSE_API_PORT:-8765}"\n' > /usr/local/bin/synapse-api-serve && \
    printf '#!/bin/sh\nexec /opt/uv/tools/sonar/bin/python "$@"\n' > /usr/local/bin/sonar-python && \
    chmod +x /usr/local/bin/synapse-api-serve /usr/local/bin/sonar-python

RUN mkdir -p /app && \
    node -e "const fs=require('fs'); const info={openclaw:{requested:process.env.OPENCLAW_VERSION,resolved:require('/usr/local/lib/node_modules/openclaw/package.json').version}, qwenCode:{requested:process.env.QWEN_CODE_VERSION,resolved:require('/usr/local/lib/node_modules/@qwen-code/qwen-code/package.json').version}, scrapling:{requested:process.env.SCRAPLING_VERSION,resolved:fs.readFileSync('/app-scrapling-version.txt','utf8').trim()}, synapse:{requested:process.env.SYNAPSE_REF,resolved:process.env.SYNAPSE_VERSION}, sonar:{requested:process.env.SONAR_REF,resolved:process.env.SONAR_VERSION}}; fs.writeFileSync('/app/build-info.json', JSON.stringify(info,null,2));" && \
    rm -f /app-scrapling-version.txt

COPY container/synapse.toml.example /app/synapse.toml.default
ENV SYNAPSE_CONFIG=/config/synapse.toml

COPY container/sonar.toml.example /app/sonar.toml.default
ENV SONAR_CONFIG=/config/sonar.toml

ENV OPENCLAW_CONFIG_PATH=/config/openclaw.json5
ENV GH_CONFIG_DIR=/data/gh
ENV OPENCLAW_STATE_DIR=/data

EXPOSE 18789

COPY container/WORKSPACE.md /app/WORKSPACE.md
COPY .agents/skills /app/skills
COPY .agents/subagents /app/subagents

COPY container/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["openclaw", "gateway", "run"]
