# infrastructure/

**Status:** Local Docker infrastructure implemented (T00-03). Runbook: [docs/runbooks/local-development.md](../docs/runbooks/local-development.md).

## Purpose

Configuration for the services MTI 360 runs on, starting with local development. The services are defined in the root `compose.yaml` (Compose project **`mti360`**) and started with `pnpm infra:up` / `pnpm stack:up`.

| Service | Profile | Image | Role |
|---|---|---|---|
| `postgres` | infra | `pgvector/pgvector:0.8.6-pg18-trixie` | PostgreSQL 18; roles from `database/init/`; pgvector not enabled |
| `redis` | infra | `redis:8.8-alpine` | Cache / sessions / future queue (no client yet) |
| `object-storage` | infra | `chrislusf/seaweedfs:4.47` | S3-compatible storage, authenticated S3 API only |
| `object-storage-init` | infra | `chrislusf/seaweedfs:4.47` | One-shot private bucket creation ([object-storage/create-bucket.sh](object-storage/create-bucket.sh)) |
| `mailpit` | infra | `axllent/mailpit:v1.31` | Local SMTP catcher (1025) and web UI (8025) |
| `api` | app | `mti360-api:local` (backend/Dockerfile) | Production-shaped FastAPI image |
| `frontend` | app | `mti360-frontend:local` (frontend/Dockerfile) | Production-shaped Next.js standalone image |

**Deferred (decision D4):** `migrate` (Alembic) and `worker` (background jobs + queue library) are added by the first task that needs them.

All host ports bind to `127.0.0.1`; all volumes are named `mti360_*`. The Compose project name is fixed so MTI 360 never interferes with other local projects (see the runbook, §5).

## Ownership

Platform / DevOps engineering.

## What belongs here

- Per-service local configuration (currently `object-storage/`)
- Later: deployment, reverse-proxy and monitoring configuration (Phase 17)

## What does NOT belong here

- Real secrets, credentials, certificates or `.env` files
- Local volume data (`.docker-data/`, `.data/` are ignored)
- Application code
- Production infrastructure before it is actually required (ARCHITECTURE.md §55)

## Populated by

| Task | Adds |
|---|---|
| T00-03 ✅ | Local Docker Compose services and their configuration |
| T00-05 | CI helpers, if needed |
| Phase 17 | Production environment, monitoring, backup/restore |
