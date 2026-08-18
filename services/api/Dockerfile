# API image: the FastAPI service.
# Build from this directory:  docker build -t invoicepilot services/api
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependency layer first, so source edits don't reinstall the world. The
# __init__ alone is enough for hatchling to build a wheel and for pip to
# resolve everything in [project.dependencies].
COPY pyproject.toml ./
COPY src/invoicepilot/__init__.py src/invoicepilot/__init__.py
RUN pip install --upgrade pip && pip install .

# The real source, reinstalled over the placeholder. --no-deps because the
# layer above already has them, and this must not re-resolve on every edit.
# A second install rather than a plain COPY: under a src/ layout the package
# is not importable from the working directory, so it has to be installed.
COPY src/ src/
RUN pip install --no-deps --force-reinstall .

COPY entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

# Where invoice_store writes. Set outright rather than left to the default in
# core/config.py: that default points at this service's directory in a
# checkout, which is not where the package lives once it is installed here.
# The path matches the volume compose.prod.yml mounts.
ENV DATA_DIR=/app/.data

# Declared so a deploy that forgets to mount a volume still starts — it just
# loses the documents with the container.
RUN mkdir -p /app/.data

EXPOSE 8000

CMD ["./entrypoint.sh"]
