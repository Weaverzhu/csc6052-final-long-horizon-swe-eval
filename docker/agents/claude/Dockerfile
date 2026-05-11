FROM node:22-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    NPM_CONFIG_UPDATE_NOTIFIER=false \
    HOME=/claude-home \
    DISABLE_TELEMETRY=1

RUN if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i 's|http://deb.debian.org/debian|http://mirrors.tuna.tsinghua.edu.cn/debian|g; s|http://security.debian.org/debian-security|http://mirrors.tuna.tsinghua.edu.cn/debian-security|g' /etc/apt/sources.list.d/debian.sources; \
    fi \
    && if [ -f /etc/apt/sources.list ]; then \
        sed -i 's|http://deb.debian.org/debian|http://mirrors.tuna.tsinghua.edu.cn/debian|g; s|http://security.debian.org/debian-security|http://mirrors.tuna.tsinghua.edu.cn/debian-security|g' /etc/apt/sources.list; \
    fi \
    && apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates git python-is-python3 python3 python3-pip python3-venv ripgrep sqlite3 \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --break-system-packages --upgrade pip

RUN python3 -m pip install --break-system-packages uv

RUN npm install -g @anthropic-ai/claude-code

RUN mkdir -p /claude-home/.claude /workspace \
    && chown -R node:node /claude-home /workspace

COPY entrypoint.sh /usr/local/bin/claude-agent-entrypoint
RUN chmod +x /usr/local/bin/claude-agent-entrypoint

USER node
WORKDIR /workspace

ENTRYPOINT ["/usr/local/bin/claude-agent-entrypoint"]
CMD ["claude"]
