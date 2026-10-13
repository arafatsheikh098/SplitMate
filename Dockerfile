# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create a non-root user up front.
RUN groupadd --system --gid 1000 splitmate \
    && useradd --system --uid 1000 --gid splitmate --create-home --shell /bin/bash splitmate

WORKDIR /app

# Install dependencies first so changes to source don't bust the cache.
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# Copy the source.
COPY splitmate ./splitmate
COPY alembic ./alembic
COPY alembic.ini ./

# Health check uses the same /health endpoint the app serves.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, sys; \
sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status == 200 else 1)"

USER splitmate

EXPOSE 8000

# Default: run migrations, then start uvicorn.  Compose / Render can pass a
# different command for one-off tasks.
CMD ["sh", "-c", "alembic upgrade head && uvicorn splitmate.main:app --host 0.0.0.0 --port 8000"]