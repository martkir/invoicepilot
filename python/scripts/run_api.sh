#!/usr/bin/env bash
# Run the API service with autoreload.
set -euo pipefail

cd "$(dirname "$0")/.."

exec uvicorn app.services.api:api --reload \
  --host "${API_HOST:-127.0.0.1}" \
  --port "${API_PORT:-8000}"
