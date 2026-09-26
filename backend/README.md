# backend/

**Status:** Toolchain foundation (T00-02). Contains only the application factory (`create_app()`), minimal `Settings` and a `GET /health` liveness endpoint, plus smoke tests. No database, cache, storage, authentication, tenancy or business modules yet.

## Commands

Run from the repository root (`pnpm dev:backend`, `pnpm lint:backend`, …) or inside `backend/`:

| Command | Purpose |
|---|---|
| `uv sync --locked` | Create `.venv` with Python 3.14 (uv-managed) from `uv.lock` |
| `uv run --locked uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port 8000 --no-server-header` | Dev server; `GET /health` → `{"status": "ok"}`; `/docs` only when `APP_ENV=development` |
| `uv run --locked ruff check .` | Lint (includes import sorting and bandit security rules) |
| `uv run --locked ruff format .` | Format (`--check` in CI) |
| `uv run --locked mypy` | Strict type checking (pydantic plugin) |
| `uv run --locked pytest` | Tests (AnyIO plugin, asyncio backend) |

Settings are read from environment variables and `backend/.env` (copy `backend/.env.example`). Toolchain versions and rationale: [docs/architecture/toolchain.md](../docs/architecture/toolchain.md).

## Purpose

The MTI 360 API and background workers: a **Python + FastAPI modular monolith** using **SQLAlchemy** and **Alembic** against **PostgreSQL**, with **Redis** and **S3-compatible object storage**.

It is the single authority for authentication, authorization, tenant isolation, business rules and audit. See [ADR-0001](../docs/adr/0001-stack.md), [ADR-0004](../docs/adr/0004-tenant-isolation.md), [ADR-0005](../docs/adr/0005-identity-and-session-realms.md) and [ADR-0006](../docs/adr/0006-api-prefixes.md).

## Ownership

Backend engineering. Changes to tenancy, authorization or audit require security review.

## What belongs here (planned layout)

```text
backend/
├── migrations/          Alembic (single linear history)
├── app/
│   ├── main.py          app factory, router mounting
│   ├── core/            cross-cutting infrastructure — no business rules
│   ├── api/             realm routers: platform, tenant, student, public, webhooks
│   ├── modules/         business domains (router, schemas, service, domain,
│   │                    models, repository, permissions, events, jobs)
│   ├── integrations/    provider adapters (each with a fake adapter for tests)
│   └── workers/         background worker entrypoint and job registry
└── tests/               unit, integration, api, security (tenant isolation)
```

Layering rule inside a module: `router → service → (domain, repository) → models`. Modules call each other only through their `service`, never through another module's repository or models.

## What does NOT belong here

- UI code
- Database bootstrap / seed scripts (those live in `/database`)
- Docker Compose and infrastructure configuration (those live in `/infrastructure` and root `compose.yaml`)
- Real `.env` files or secrets — only `.env.example` is committed
- Microservices — this is a modular monolith until a documented extraction decision exists

## Populated by

| Task | Adds |
|---|---|
| T00-02 ✅ | `pyproject.toml`, `uv.lock`, FastAPI app factory, settings, `/health`, Ruff / mypy / pytest configuration (Alembic deferred to the first database task — decision D5) |
| T00-03 | `Dockerfile` (api / worker / migrate from one image) |
| T00-04 | Settings loading and per-environment validation |
| Phase 01 | Identity, tenancy, authorization, audit modules and tenant-isolation tests |
