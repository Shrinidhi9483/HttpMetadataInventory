# syntax=docker/dockerfile:1

# HTTP Metadata Inventory Dockerfile
# Multi-stage build for optimized production image

# Build stage
FROM python:3.11-slim as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster package installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock* ./

# Install dependencies
RUN uv pip install --system --no-cache -r pyproject.toml

# Production stage
FROM python:3.11-slim as production

# Create non-root user for security
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    APP_HOME=/app

# Set working directory
WORKDIR $APP_HOME

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=appuser:appgroup ./src ./src

# Copy SSL certificates
COPY --chown=appuser:appgroup ./certs ./certs

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check (using --insecure for self-signed certs)
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('https://localhost:8000/health', timeout=5, verify=False)" || exit 1

# Run application with SSL
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--ssl-keyfile", "certs/key.pem", "--ssl-certfile", "certs/cert.pem"]
