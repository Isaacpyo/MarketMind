# syntax=docker/dockerfile:1.7
# MarketMind API: FastAPI + implicit ALS. Small enough for Render's 512 MB free tier.

FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project
COPY marketmind ./marketmind
COPY data/seed ./data/seed

FROM python:3.12-slim AS runtime
# implicit's compiled ALS kernels link against OpenMP.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 app
WORKDIR /app
COPY --from=builder --chown=app:app /app /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    OPENBLAS_NUM_THREADS=1 \
    PORT=8000
USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/api/health', timeout=2)"
# Render injects $PORT; locally it defaults to 8000.
CMD ["sh", "-c", "exec uvicorn --factory marketmind.main:app_factory --host 0.0.0.0 --port ${PORT} --no-access-log"]
