# === Base: production dependencies ===
FROM python:3.11-slim AS base

# Python optimization flags
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies for rhino3dm (T-024-AGENT)
# CMake required for rhino3dm compilation (C++ bindings)
# nodejs/npm required for gltf-pipeline (Draco compression)
# hadolint ignore=DL3008,DL3016
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    nodejs \
    npm \
    && npm install -g gltf-pipeline@4 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user early (reused in dev/prod)
RUN groupadd -r agentuser && useradd -r -g agentuser -u 1001 agentuser \
    && chown -R agentuser:agentuser /app

# Copy and install dependencies as root
COPY --chown=agentuser:agentuser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# === Dev: hot-reload + test dependencies (NON-ROOT) ===
FROM base AS dev

# Switch to non-root user for runtime
USER agentuser

CMD ["celery", "-A", "celery_app", "worker", "--loglevel=info", "--concurrency=2"]

# === Prod: copy source, production concurrency (NON-ROOT) ===
FROM base AS prod

COPY --chown=agentuser:agentuser . .

# Verify gltf-pipeline is available (critical for Draco compression)
RUN command -v gltf-pipeline || (echo "ERROR: gltf-pipeline not found" && exit 1)

# Switch to non-root user for runtime
USER agentuser

CMD ["celery", "-A", "celery_app", "worker", "--loglevel=warning", "--concurrency=4"]
