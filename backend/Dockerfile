# syntax=docker/dockerfile:1
# =============================================================================
# MTI 360 backend image (T00-03) — production-shaped, multi-stage.
#
# Build context: backend/        docker build -t mti360-api backend
# Runs:          uvicorn app.main:create_app (FastAPI) — default command
#                alembic upgrade head               — "migrate" (T01-01, compose)
#
# - Locked, production-only dependencies (uv sync --locked --no-dev).
# - Runtime runs as a dedicated non-root user; application files are root-owned
#   and read-only for that user.
# - No secrets are baked in: configuration comes from the runtime environment
#   and .env files are excluded by backend/.dockerignore.
# =============================================================================

ARG PYTHON_IMAGE=python:3.14.7-slim-trixie

FROM ghcr.io/astral-sh/uv:0.12.19 AS uv

# --- builder: resolve and install locked dependencies into /app/.venv --------
FROM ${PYTHON_IMAGE} AS builder

COPY --from=uv /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Dependencies first (cached layer), then the application code.
COPY pyproject.toml uv.lock .python-version ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations

# --- runtime ------------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}"

RUN groupadd --system --gid 10001 mti360 \
 && useradd --system --uid 10001 --gid mti360 --no-create-home \
      --home-dir /nonexistent --shell /usr/sbin/nologin mti360

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/app /app/app
COPY --from=builder /app/alembic.ini /app/alembic.ini
COPY --from=builder /app/migrations /app/migrations

USER 10001:10001

EXPOSE 8000

# Liveness probe using the Python standard library only (no curl in the image).
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"]

# --no-access-log: the application logs every request as JSON without the query
# string (app/core/middleware.py); uvicorn's access log would include it.
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-server-header", "--no-access-log"]
