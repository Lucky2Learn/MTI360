# infrastructure/

**Status:** Reserved. No infrastructure files exist yet.

## Purpose

Configuration for the services MTI 360 runs on, starting with local development.

Planned local services (T00-03), orchestrated by a root `compose.yaml` so that `docker compose up` works from a fresh clone:

| Service | Role |
|---|---|
| `postgres` | Primary database (pgvector-enabled image once AI work starts) |
| `redis` | Cache, rate limits, sessions, job queue |
| `object-storage` | S3-compatible emulator with a private bucket (product choice made in T00-03) |
| `mailpit` | Local SMTP catcher for password reset / invitation flows |
| `migrate` | One-shot `alembic upgrade head` |
| `api` / `worker` | Backend image, two entrypoints |
| `frontend` | Next.js dev server (optional; native `next dev` is documented for Windows) |

## Ownership

Platform / DevOps engineering.

## What belongs here

- Per-service local configuration (`postgres/`, `redis/`, `object-storage/`)
- Later: deployment, reverse-proxy and monitoring configuration (Phase 17)

## What does NOT belong here

- Real secrets, credentials, certificates or `.env` files
- Local volume data (`.docker-data/`, `.data/` are ignored)
- Application code
- Production infrastructure before it is actually required (ARCHITECTURE.md §55)

## Populated by

| Task | Adds |
|---|---|
| T00-03 | Local Docker Compose services and their configuration |
| T00-05 | CI helpers, if needed |
| Phase 17 | Production environment, monitoring, backup/restore |
