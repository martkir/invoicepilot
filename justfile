# Invoice Pilot - Just commands

set shell := ["bash", "-c"]

api_dir := "services/api"
web_dir := "services/web"

# Display help message
help:
  @echo "Invoice Pilot - Just Commands"
  @echo "=============================="
  @echo ""
  @echo "Quick Start:"
  @echo "  just setup         - Create .venv and install the api service (editable)"
  @echo "  just migrate       - Create tables (needs just start-db first)"
  @echo "  just api           - Run the FastAPI service with autoreload"
  @echo "  just web           - Run the Vite dev server for the dashboard"
  @echo ""
  @echo "API service:"
  @echo "  just cli ARGS      - Run the CLI (e.g. just cli config)"
  @echo "  just test          - Run pytest"
  @echo "  just lint          - Run ruff check + format --check"
  @echo "  just fmt           - Apply ruff formatting and autofixes"
  @echo ""
  @echo "Web service:"
  @echo "  just web-install   - npm install in services/web/"
  @echo "  just web-build     - Production build to services/web/dist"
  @echo "  just web-deploy    - Build the image and serve it on port 8090"
  @echo "  just web-down      - Stop and remove that container"
  @echo "  just flows NAME    - Page through a docs/flows mockup (e.g. share-flow)"
  @echo ""
  @echo "Database:"
  @echo "  just start-db      - Start PostgreSQL with Docker"
  @echo "  just stop-db       - Stop PostgreSQL"
  @echo ""
  @echo "Deploy (everything in Docker, nothing on the host):"
  @echo "  just deploy        - Build and start postgres + api + dashboard"
  @echo "  just deploy-logs   - Follow their logs"
  @echo "  just deploy-down   - Stop them (volumes survive)"
  @echo ""
  @echo "Maintenance:"
  @echo "  just clean         - Remove venv, caches and frontend build output"
  @echo ""
  @echo "First Time Setup:"
  @echo "  1. cp services/api/.env.example services/api/.env   # backend credentials"
  @echo "  2. cp .env.example .env                             # compose credentials"
  @echo "  3. just setup && just api"

# Create the virtualenv and install the api service in editable mode
setup:
  #!/usr/bin/env bash
  set -euo pipefail
  if command -v uv >/dev/null 2>&1; then
    uv venv
    uv pip install -e "{{api_dir}}[dev]"
  else
    python3 -m venv .venv
    ./.venv/bin/pip install --upgrade pip
    ./.venv/bin/pip install -e "{{api_dir}}[dev]"
  fi
  echo "Done. Activate with: source .venv/bin/activate"

# Create tables and backfill any invoices already on disk
migrate:
  invoicepilot migrate

# Run the API service with autoreload
api:
  cd {{api_dir}} && exec uvicorn invoicepilot.app:api --reload \
    --host "${API_HOST:-127.0.0.1}" --port "${API_PORT:-8000}"

# Run the CLI, e.g. `just cli config`
cli *ARGS:
  python -m invoicepilot {{ARGS}}

# Run the test suite
test:
  cd {{api_dir}} && pytest

# Lint without modifying files
lint:
  ruff check .
  ruff format --check .

# Apply formatting and safe autofixes
fmt:
  ruff check --fix .
  ruff format .

# Install frontend dependencies
web-install:
  cd {{web_dir}} && npm install

# Run the Vite dev server (dashboard at http://localhost:5173)
web:
  cd {{web_dir}} && npm run dev

# Production build of the frontend
web-build:
  cd {{web_dir}} && npm run build

# Build the dashboard image and (re)start it on http://localhost:8090.
# The image builds the frontend itself, so this does not need web-build first.
# --build is not optional: the container holds a build rather than the source,
# so without it 8090 goes on serving the bundle from last time.
web-deploy:
  docker compose up -d --build web
  @echo "Dashboard at http://localhost:8090 - needs the API on host port 8000"

# Stop and remove the dashboard container
web-down:
  docker compose rm -sf web

# Serve one flow's mockups and open its paginated viewer (no name lists them)
flows *ARGS:
  python3 tools/preview_flows.py {{ARGS}}

# Start PostgreSQL database with Docker
start-db:
  @echo "Starting PostgreSQL database..."
  docker compose up -d postgres
  @echo "Waiting for database to be ready..."
  @sleep 5

# Stop PostgreSQL database
stop-db:
  @echo "Stopping PostgreSQL database..."
  docker compose stop postgres
  @echo "Database stopped!"

# Build and start the deployed stack: postgres, api and dashboard, all in Docker
deploy:
  docker compose -f compose.prod.yml up -d --build
  @echo "Dashboard on loopback only, at WEB_LOCAL_PORT from .env (default 8090)."
  @echo "Put it on the internet with deploy/caddy-public.caddy."

# The drafter, on the host. `npm install` in services/drafter first.
# Point the api at it with DRAFTER_URL=http://127.0.0.1:8100.
drafter:
  cd services/drafter && npm start

# Follow the deployed stack's logs
deploy-logs *ARGS:
  docker compose -f compose.prod.yml logs -f {{ARGS}}

# Stop the deployed stack. Volumes survive: the invoices are in one of them.
deploy-down:
  docker compose -f compose.prod.yml down

# Remove virtualenv, caches and build output
clean:
  rm -rf .venv .pytest_cache .ruff_cache {{web_dir}}/node_modules {{web_dir}}/dist
  find . -name __pycache__ -type d -prune -exec rm -rf {} +
  @echo "Clean complete!"
