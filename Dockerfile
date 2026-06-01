FROM python:3.13-slim

ARG PORT=8000
ENV PORT=${PORT}
ENV ENVIRONMENT=production
ENV LOG_LEVEL=INFO
ENV WORKERS=4

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Install system dependencies (including curl for healthchecks)
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first for better caching
COPY pyproject.toml .

# Install runtime dependencies (no dev group)
RUN uv sync --no-dev --no-install-project

# Copy application code
COPY . .

# Sync with project source
RUN uv sync --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose documented port (mapping is handled by docker run / compose)
EXPOSE ${PORT}

# Health check (uses PORT env at runtime)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://127.0.0.1:${PORT:-8000}/health || exit 1

# Run granian via CLI so host/port/env/args reliably apply; expand env vars via sh -c
CMD ["sh", "-c", "granian --interface asgi --host 0.0.0.0 --port ${PORT} --workers ${WORKERS} app.main:app"]
