# Backend image: the FastAPI service.
# Build from the repo root:  docker build -f docker/Dockerfile -t invoicepilot .
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependency layer first, so source edits don't reinstall the world.
COPY pyproject.toml ./
COPY backend/__init__.py backend/__init__.py
RUN pip install --upgrade pip && pip install .

COPY backend/ backend/
COPY templates/ templates/

EXPOSE 8000

CMD ["uvicorn", "backend.services.api:api", "--host", "0.0.0.0", "--port", "8000"]
