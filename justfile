# Invoice Pilot - Just commands

set shell := ["bash", "-c"]

# Display help message
help:
  @echo "Invoice Pilot - Just Commands"
  @echo "=============================="
  @echo ""
  @echo "Quick Start:"
  @echo "  just setup         - Create .venv and install the backend (editable)"
  @echo "  just migrate       - Create tables (needs just start-db first)"
  @echo "  just api           - Run the FastAPI service with autoreload"
  @echo "  just web           - Run the Vite dev server for the dashboard"
  @echo ""
  @echo "Backend:"
  @echo "  just cli ARGS      - Run the CLI (e.g. just cli config)"
  @echo "  just test          - Run pytest"
  @echo "  just lint          - Run ruff check + format --check"
  @echo "  just fmt           - Apply ruff formatting and autofixes"
  @echo ""
  @echo "Frontend:"
  @echo "  just web-install   - npm install in frontend/"
  @echo "  just web-build     - Production build to frontend/dist"
  @echo "  just web-deploy    - Build the image and serve it on port 8090"
  @echo "  just web-down      - Stop and remove that container"
  @echo "  just flows NAME    - Page through a docs/flows mockup (e.g. share-flow)"
  @echo ""
  @echo "Database:"
  @echo "  just start-db      - Start PostgreSQL with Docker"
  @echo "  just stop-db       - Stop PostgreSQL"
  @echo ""
  @echo "Maintenance:"
  @echo "  just clean         - Remove venv, caches and frontend build output"
  @echo ""
  @echo "First Time Setup:"
  @echo "  1. cp .env.example .env"
  @echo "  2. Edit .env with your Google / Unipile credentials"
  @echo "  3. just setup && just api"

# Create the virtualenv and install the backend in editable mode
setup:
  ./scripts/bootstrap.sh

# Create tables and backfill any invoices already on disk
migrate:
  python scripts/migrate_db.py

# Run the API service with autoreload
api:
  ./scripts/run_api.sh

# Run the CLI, e.g. `just cli config`
cli *ARGS:
  python -m backend {{ARGS}}

# Run the test suite
test:
  pytest

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
  cd frontend && npm install

# Run the Vite dev server (dashboard at http://localhost:5173)
web:
  cd frontend && npm run dev

# Production build of the frontend
web-build:
  cd frontend && npm run build

# Build the dashboard image and (re)start it on http://localhost:8090.
# The image builds the frontend itself, so this does not need web-build first.
# --build is not optional: the container holds a build rather than the source,
# so without it 8090 goes on serving the bundle from last time.
web-deploy:
  cd docker && docker compose --env-file .env up -d --build web
  @echo "Dashboard at http://localhost:8090 - needs the API on host port 8000"

# Stop and remove the dashboard container
web-down:
  cd docker && docker compose --env-file .env rm -sf web

# Serve one flow's mockups and open its paginated viewer (no name lists them)
flows *ARGS:
  python3 scripts/preview_flows.py {{ARGS}}

# Start PostgreSQL database with Docker
start-db:
  @echo "Starting PostgreSQL database..."
  cd docker && docker compose --env-file .env up -d postgres
  @echo "Waiting for database to be ready..."
  @sleep 5

# Stop PostgreSQL database
stop-db:
  @echo "Stopping PostgreSQL database..."
  cd docker && docker compose --env-file .env stop postgres
  @echo "Database stopped!"

# Remove virtualenv, caches and build output
clean:
  rm -rf .venv .pytest_cache .ruff_cache frontend/node_modules frontend/dist
  find . -name __pycache__ -type d -prune -exec rm -rf {} +
  @echo "Clean complete!"
