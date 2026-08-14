#!/usr/bin/env bash
# Create a virtualenv and install the project in editable mode.
set -euo pipefail

cd "$(dirname "$0")/.."

if command -v uv >/dev/null 2>&1; then
  uv venv
  uv pip install -e ".[dev]"
else
  python3 -m venv .venv
  ./.venv/bin/pip install --upgrade pip
  ./.venv/bin/pip install -e ".[dev]"
fi

echo "Done. Activate with: source .venv/bin/activate"
