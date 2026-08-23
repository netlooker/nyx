# syntax=docker/dockerfile:1

ARG UV_VERSION=0.12.5

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv-bin

FROM debian:bookworm-slim AS container

ARG NODE_MAJOR=22
ARG OPENCLAW_VERSION=latest
ARG QWEN_CODE_VERSION=latest
ARG SCRAPLING_VERSION=latest
ARG HERMES_REF=main
ARG HERMES_VERSION=main
ARG SYNAPSE_REF=main
ARG SYNAPSE_VERSION=main
ARG SONAR_REF=main
ARG SONAR_VERSION=main
ARG OPTIC_SPARK_REF=main
ARG OPTIC_SPARK_VERSION=main

ENV PATH=/usr/local/bin:/usr/bin:/bin
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV HOME=/root
ENV CI=true
ENV UV_TOOL_DIR=/opt/uv/tools
ENV UV_TOOL_BIN_DIR=/usr/local/bin

LABEL org.opencontainers.image.title="nyx" \
      org.opencontainers.image.description="Docker runtime for OpenClaw or Hermes with persistent /data state." \
      io.github.netlooker.nyx.build-info="/app/build-info.json" \
      io.github.netlooker.nyx.openclaw.version="${OPENCLAW_VERSION}" \
      io.github.netlooker.nyx.qwen-code.version="${QWEN_CODE_VERSION}" \
      io.github.netlooker.nyx.scrapling.version="${SCRAPLING_VERSION}" \
      io.github.netlooker.nyx.hermes.version="${HERMES_VERSION}" \
      io.github.netlooker.nyx.synapse.version="${SYNAPSE_VERSION}" \
      io.github.netlooker.nyx.sonar.version="${SONAR_VERSION}" \
      io.github.netlooker.nyx.optic-spark.version="${OPTIC_SPARK_VERSION}"

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
      golang-go \
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

COPY --from=uv-bin /uv /uvx /usr/local/bin/

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

# Optic-Spark CLI provides synchronous image generation over the API's async
# webhook protocol. Build the binary and provide a smart wrapper that applies
# environment defaults (OPTIC_SPARK_API_URL, OPTIC_SPARK_CALLBACK_HOST, OPTIC_SPARK_OUT_DIR).
RUN git clone https://github.com/netlooker/optic-spark.git /tmp/optic-spark && \
    cd /tmp/optic-spark && \
    git checkout "${OPTIC_SPARK_VERSION}" && \
    cd cli && \
    go build -o /usr/local/bin/optic-cli-bin . && \
    rm -rf /tmp/optic-spark /root/go/pkg/mod && \
    printf '#!/bin/sh\nset -eu\nhas_api=0\nhas_cb=0\nhas_out=0\nfor arg in "$@"; do\n  case "$arg" in\n    -api|--api|-api=*|--api=*) has_api=1 ;;\n    -callback-host|--callback-host|-callback-host=*|--callback-host=*) has_cb=1 ;;\n    -out|--out|-out=*|--out=*) has_out=1 ;;\n  esac\ndone\ncmd="/usr/local/bin/optic-cli-bin"\nif [ "$has_api" -eq 0 ]; then\n  set -- -api "${OPTIC_SPARK_API_URL:-http://192.168.1.x:7070}" "$@"\nfi\nif [ "$has_cb" -eq 0 ]; then\n  set -- -callback-host "${OPTIC_SPARK_CALLBACK_HOST:-http://192.168.1.x}" "$@"\nfi\nif [ "$has_out" -eq 0 ]; then\n  out_dir="${OPTIC_SPARK_OUT_DIR:-/data/workspace/images}"\n  mkdir -p "$out_dir"\n  set -- -out "$out_dir" "$@"\nfi\nexec "$cmd" "$@"\n' > /usr/local/bin/optic-cli && \
    chmod +x /usr/local/bin/optic-cli && \
    ln -sf /usr/local/bin/optic-cli /usr/local/bin/optic-spark

# Python tool layer. Synapse/Sonar refs are resolved to concrete commits by
# `just build`, but Docker still accepts branch names for direct manual builds.
# Hermes Agent requires HERMES_NIX_BUILD=1 to allow wheel building outside editable mode.
RUN if [ "${SCRAPLING_VERSION}" = "latest" ]; then \
      scrapling_spec="scrapling[all]"; \
    else \
      scrapling_spec="scrapling[all]==${SCRAPLING_VERSION}"; \
    fi && \
    uv tool install --python /usr/bin/python3 "$scrapling_spec" && \
    HERMES_NIX_BUILD=1 uv tool install --python 3.13 "hermes-agent[all] @ git+https://github.com/NousResearch/hermes-agent.git@${HERMES_VERSION}" && \
    uv tool install --python 3.12 "synapse[api] @ git+https://github.com/netlooker/synapse.git@${SYNAPSE_VERSION}" && \
    uv tool install --python 3.12 "sonar[mcp] @ git+https://github.com/netlooker/sonar.git@${SONAR_VERSION}" && \
    "${UV_TOOL_DIR}/scrapling/bin/python" -c "from importlib.metadata import version; print(version('scrapling'))" > /app-scrapling-version.txt && \
    "${UV_TOOL_DIR}/hermes-agent/bin/python" -c "from importlib.metadata import version; print(version('hermes-agent'))" > /app-hermes-version.txt

# Hermes currently reads static i18n strings from a top-level `locales/`
# directory, but the uv tool install from Git does not place those data files
# under site-packages. Copy them from the same resolved Hermes ref so gateway
# slash commands render text instead of dotted translation keys.
RUN git clone https://github.com/NousResearch/hermes-agent.git /tmp/hermes-agent && \
    cd /tmp/hermes-agent && \
    git checkout "${HERMES_VERSION}" && \
    mkdir -p "${UV_TOOL_DIR}/hermes-agent/lib/python3.13/site-packages/locales" && \
    cp -R locales/. "${UV_TOOL_DIR}/hermes-agent/lib/python3.13/site-packages/locales/" && \
    rm -rf /tmp/hermes-agent

# Compatibility wrappers for commands used by Nyx scripts and entrypoint logic.
RUN printf '#!/bin/sh\nexec /opt/uv/tools/synapse/bin/python -m uvicorn synapse.web_api:create_app --factory --host "${SYNAPSE_API_HOST:-0.0.0.0}" --port "${SYNAPSE_API_PORT:-8765}"\n' > /usr/local/bin/synapse-api-serve && \
    printf '#!/bin/sh\nexec /opt/uv/tools/sonar/bin/python "$@"\n' > /usr/local/bin/sonar-python && \
    chmod +x /usr/local/bin/synapse-api-serve /usr/local/bin/sonar-python

RUN mkdir -p /app && \
    node -e "const fs=require('fs'); const info={openclaw:{requested:process.env.OPENCLAW_VERSION,resolved:require('/usr/local/lib/node_modules/openclaw/package.json').version}, qwenCode:{requested:process.env.QWEN_CODE_VERSION,resolved:require('/usr/local/lib/node_modules/@qwen-code/qwen-code/package.json').version}, scrapling:{requested:process.env.SCRAPLING_VERSION,resolved:fs.readFileSync('/app-scrapling-version.txt','utf8').trim()}, hermes:{requested:process.env.HERMES_REF,resolved:process.env.HERMES_VERSION,packageVersion:fs.readFileSync('/app-hermes-version.txt','utf8').trim()}, synapse:{requested:process.env.SYNAPSE_REF,resolved:process.env.SYNAPSE_VERSION}, sonar:{requested:process.env.SONAR_REF,resolved:process.env.SONAR_VERSION}, opticSpark:{requested:process.env.OPTIC_SPARK_REF,resolved:process.env.OPTIC_SPARK_VERSION}}; fs.writeFileSync('/app/build-info.json', JSON.stringify(info,null,2));" && \
    rm -f /app-scrapling-version.txt /app-hermes-version.txt

COPY container/synapse.toml.example /app/synapse.toml.default
ENV SYNAPSE_CONFIG=/config/synapse.toml

COPY container/sonar.toml.example /app/sonar.toml.default
ENV SONAR_CONFIG=/config/sonar.toml

COPY container/hermes.yaml.example /app/hermes.yaml.default
COPY container/hermes-soul.md.example /app/hermes-soul.default

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
CMD ["nyx-orchestrator"]
