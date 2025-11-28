# ===================================================================
# Multi-stage Dockerfile for shining-quasar
# Python 3.10 slim with uv for fast dependency installation
# Final image size optimized for production
# ===================================================================

# ======================
# Stage 1: Builder
# ======================
FROM python:3.10-slim AS builder

# Install uv for fast package installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml uv.lock ./

# Install dependencies (no dev dependencies for production)
RUN uv sync --frozen --no-dev --no-install-project

# Copy source code
COPY src/ ./src/
COPY templates/ ./templates/
COPY scripts/ ./scripts/
COPY stubs/ ./stubs/
COPY data/inputs/ ./data/inputs/

# Install the project itself
RUN uv sync --frozen --no-dev

# ======================
# Stage 2: Runtime
# ======================
FROM python:3.10-slim AS runtime

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create non-root user for security
RUN groupadd --gid 1000 appgroup \
    && useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY --from=builder /app/src /app/src
COPY --from=builder /app/templates /app/templates
COPY --from=builder /app/scripts /app/scripts
COPY --from=builder /app/stubs /app/stubs
COPY --from=builder /app/data /app/data
COPY --from=builder /app/pyproject.toml /app/pyproject.toml

# Create data directories
RUN mkdir -p /app/data/outputs /app/data/inputs \
    && chown -R appuser:appgroup /app

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose FastAPI port
EXPOSE 8000

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from src.infra.health import health_check; print(health_check())" || exit 1

# Create startup script
RUN echo '#!/bin/bash\n\
set -e\n\
# Optional: Run cache warming\n\
if [ -f "/app/scripts/cache_warming.py" ]; then\n\
    python /app/scripts/cache_warming.py 2>/dev/null || echo "Cache warming skipped"\n\
fi\n\
# Start the application\n\
exec "$@"\n\
' > /app/start.sh && chmod +x /app/start.sh

ENTRYPOINT ["/app/start.sh"]
CMD ["python", "-m", "uvicorn", "src.web.api:app", "--host", "0.0.0.0", "--port", "8000"]
