# Node rather than Python because this service is a wrapper around the Claude
# Agent SDK, which is a Node package that spawns the Claude Code binary. The
# SDK ships that binary for the platform, so there is no separate CLI to
# install and nothing to fetch at runtime.
FROM node:22-slim

WORKDIR /app

# Claude Code keeps session state under $HOME/.claude and expects to write it.
# The credential is mounted read-only over one file inside, so the state is
# container-local and the real credential can only ever be read.
#
# As root, and deliberately. That credential is `-rw------- root root` on the
# host, and a bind mount keeps the host's ownership — so a non-root user in here
# cannot read it at all, which is how this first failed ("Not logged in").
# The alternatives were widening the permissions on a live credential file or
# copying it somewhere this user owns, and both are worse than root inside a
# single-purpose container that publishes no port and mounts nothing else.
RUN mkdir -p /root/.claude

COPY package.json package-lock.json* ./
RUN npm install --omit=dev --no-audit --no-fund

COPY src/ ./src/
COPY tests/ ./tests/

EXPOSE 8100
CMD ["node", "src/server.js"]
