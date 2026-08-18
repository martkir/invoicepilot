# Node rather than Python because this service is a wrapper around the Claude
# Agent SDK, which is a Node package that spawns the Claude Code binary. The
# SDK ships that binary for the platform, so there is no separate CLI to
# install and nothing to fetch at runtime.
FROM node:22-slim

WORKDIR /app

# Its own HOME, writable, and not the one holding the mounted credential. Claude
# Code keeps session state under $HOME/.claude and expects to write it; the
# credential file inside is mounted read-only over the top, so state is
# container-local and the real credential can only ever be read.
ENV HOME=/home/drafter
RUN useradd --create-home --home-dir /home/drafter drafter \
    && mkdir -p /home/drafter/.claude \
    && chown -R drafter:drafter /home/drafter

COPY package.json package-lock.json* ./
RUN npm install --omit=dev --no-audit --no-fund

COPY src/ ./src/
COPY tests/ ./tests/

RUN chown -R drafter:drafter /app
USER drafter

EXPOSE 8100
CMD ["node", "src/server.js"]
