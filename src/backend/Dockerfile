# === Base: production dependencies ===
FROM python:3.11-slim AS base

# Python optimization flags (prevent .pyc files, unbuffered output for logs)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies for rhino3dm + open3d (required for agent test execution)
# CMake required for rhino3dm compilation (C++ bindings)
# libx11-6, libgl1, libgomp1, libglib2.0-0 required for open3d (decimation backend)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libx11-6 \
    libgl1 \
    libgomp1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user early (reused in dev/prod)
RUN groupadd -r appuser && useradd -r -g appuser -u 1000 appuser \
    && chown -R appuser:appuser /app

# Copy and install dependencies as root (building wheels requires privileges)
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

# === Dev: hot-reload + test dependencies (NON-ROOT) ===
FROM base AS dev

COPY --chown=appuser:appuser requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

# Switch to non-root user for runtime
USER appuser

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# === Prod: copy source, multi-worker (NON-ROOT) ===
FROM base AS prod

COPY --chown=appuser:appuser . .

# Switch to non-root user for runtime
USER appuser

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
