# CloudCLI (siteboon/claudecodeui) — the web UI for the Claude Code CLI.
# Not part of the InvoicePilot stack; it just lives here so the image and its
# compose file sit beside the project's other docker files.
#
#   cd docker && docker compose -f compose.cloudcli.yml up -d --build
FROM node:24-bookworm-slim

# python3/make/g++ build node-pty, which CloudCLI's postinstall compiles.
# git and ripgrep are for the Claude Code session running inside the UI.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 make g++ git ca-certificates ripgrep \
    && rm -rf /var/lib/apt/lists/*

# Pinned to the version already installed on the host, so the container and
# `cloudcli` on the command line stay the same build. --allow-scripts is not
# optional: without it npm skips the postinstall that builds better-sqlite3,
# bcrypt and node-pty, and the server starts with no working session terminal.
RUN npm install -g --allow-scripts=@cloudcli-ai/cloudcli,bcrypt,better-sqlite3,node-pty \
        @cloudcli-ai/cloudcli@1.37.1

# The host's bin directory goes last, so the image's own cloudcli wins over the
# copy visible on the /home/clickhouse mount. The claude binary is still found
# there, and CLAUDE_CLI_PATH in the compose file names it outright.
ENV PATH="${PATH}:/home/clickhouse/.local/bin" \
    SERVER_PORT=3011 \
    HOST=0.0.0.0

EXPOSE 3011

CMD ["cloudcli"]
