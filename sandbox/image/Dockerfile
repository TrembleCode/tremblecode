# tremblecode-sandbox:base — per-project agent sandbox.
# Agents run as long-lived Claude Code sessions inside tmux; the relay
# (mounted at /opt/tremblecode, source on host) manages sessions and messaging.
FROM ubuntu:24.04

ARG CLAUDE_CODE_VERSION=latest
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl git gnupg jq ripgrep tmux sudo \
    python3 python3-venv python3-pip \
    build-essential pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Node 22 (Claude Code + JS toolchains)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g pnpm @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION} \
    && rm -rf /var/lib/apt/lists/*

# uv for python projects built by agents
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh

# Runtime venv for the tremblecode relay/MCP server (source mounted at /opt/tremblecode)
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir \
       "fastapi>=0.115" "uvicorn>=0.32" "redis>=5.2" "httpx>=0.28" "pyyaml>=6" "mcp>=1.2"

ENV PYTHONPATH=/opt/tremblecode/src
ENV PYTHONUNBUFFERED=1

RUN printf '#!/bin/sh\nexec /opt/venv/bin/python -m tremblecode_runtime.hook "$@"\n' > /usr/local/bin/tremblecode-hook \
    && printf '#!/bin/sh\nexec /opt/venv/bin/python -m tremblecode_runtime.mcp_server "$@"\n' > /usr/local/bin/tremblecode-mcp \
    && printf '#!/bin/sh\nexec /opt/venv/bin/python -m tremblecode_runtime.relay "$@"\n' > /usr/local/bin/tremblecode-relay \
    && printf '#!/bin/bash\nwhile true; do /usr/local/bin/tremblecode-relay; echo "[tremblecode] relay exited ($?), restarting in 2s"; sleep 2; done\n' > /usr/local/bin/tremblecode-relay-loop \
    && chmod +x /usr/local/bin/tremblecode-*

# Non-root agent user (Claude Code refuses --dangerously-skip-permissions as root),
# with passwordless sudo so agents can install toolchains they need.
RUN userdel -r ubuntu 2>/dev/null || true \
    && useradd -m -u 1000 -s /bin/bash agent \
    && echo "agent ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/agent

USER agent
WORKDIR /home/agent

CMD ["/usr/local/bin/tremblecode-relay-loop"]
