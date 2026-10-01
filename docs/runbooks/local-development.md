# Runbook — Local Development

- **Status:** Current as of T00-03 (2026-09-26)
- **Related:** [toolchain.md](../architecture/toolchain.md), [repository-structure.md](../architecture/repository-structure.md), `compose.yaml`

## 1. Model: hybrid development

| Runs in Docker (`pnpm infra:up`) | Runs natively (`pnpm dev`) |
|---|---|
| PostgreSQL 18, Redis 8.8, SeaweedFS (S3), Mailpit | Next.js dev server, FastAPI dev server |

Application source code is **not** bind-mounted into containers for day-to-day work (Windows bind mounts and file watching are slow). The `app` Compose profile (`pnpm stack:up`) builds and runs the production-shaped images for parity checks only.

## 2. First-time setup

1. Tools from [toolchain.md](../architecture/toolchain.md) (Node 24, pnpm 11 via Corepack, uv) plus **Docker Desktop** (Engine 29.x, Compose v2+ / v5).
2. `cp .env.example .env` and replace **every** `change-me` with a long random value. Compose refuses to start while a required value is missing.
3. Copy `backend/.env.example` → `backend/.env` when backend settings are needed; keep `MTI_APP_PASSWORD` and the `S3_*` values consistent with the root `.env`.
4. `pnpm bootstrap`

## 3. Daily commands

| Command | Effect |
|---|---|
| `pnpm infra:up` | Start PostgreSQL, Redis, SeaweedFS, Mailpit; wait until healthy; create the private bucket (idempotent) |
| `pnpm dev` | Native frontend + backend (ports from the shell: `FRONTEND_PORT`, `API_PORT`) |
| `pnpm infra:logs` | Follow infrastructure / app container logs |
| `pnpm infra:down` | Stop and remove MTI 360 containers and network. **Data volumes are kept.** |
| `pnpm stack:up` | Build images and run infrastructure, the one-shot `migrate` container, **then** the api and frontend containers |
| `pnpm db:migrate` / `pnpm db:check` | Apply migrations to the local database (native) / fail when models and migrations differ |
| `pnpm infra:reset` | **Deletes all local MTI 360 data**: removes MTI 360 containers, network and `mti360_*` volumes. Nothing else. |

Stop the native `pnpm dev` servers before `pnpm stack:up` (and vice versa) — they use the same host ports.

## 4. Services, ports and endpoints

All host ports bind to **127.0.0.1**. Defaults can be overridden in the local `.env`.

| Service | Container | Default host port | Endpoint (from the host) | Notes |
|---|---|---|---|---|
| PostgreSQL 18.6 | `mti360-postgres-1` | 5432 (`POSTGRES_PORT`) | `127.0.0.1:5432/mti360` | Roles `mti_owner`, `mti_app`, `mti_readonly` |
| Redis 8.8 | `mti360-redis-1` | 6379 (`REDIS_PORT`) | `redis://127.0.0.1:6379/0` | No application client yet |
| SeaweedFS 4.47 (S3) | `mti360-object-storage-1` | 8333 (`S3_PORT`) | `http://127.0.0.1:8333` | Private bucket `S3_BUCKET` (default `mti360-local`); signed requests only |
| Mailpit 1.31 | `mti360-mailpit-1` | 1025 SMTP, 8025 UI | `http://127.0.0.1:8025` | Catches all outgoing mail |
| API (app profile) | `mti360-api-1` | 8000 (`API_PORT`) | `http://127.0.0.1:8000/health` | |
| Frontend (app profile) | `mti360-frontend-1` | 3000 (`FRONTEND_PORT`) | `http://127.0.0.1:3000` | |

Inside the Compose network services are reached by name (`postgres:5432`, `redis:6379`, `object-storage:8333`, `mailpit:1025`, `api:8000`).

Volumes: `mti360_postgres_data`, `mti360_redis_data`, `mti360_object_storage_data`. Network: `mti360_default`.

## 5. Running beside other local projects (two-SaaS isolation)

Another SaaS project (ACRS) may run on the same machine with its own Compose project and ports (e.g. 3000, 8000, 5433). MTI 360 stays isolated because:

- the Compose project name is fixed to **`mti360`** in `compose.yaml` — never pass `-p` and never set `COMPOSE_PROJECT_NAME`;
- every volume is explicitly named `mti360_*`; the network is `mti360_default`;
- all published ports bind to `127.0.0.1` and are overridable.

**Port conflicts:** set overrides in the local `.env` for the containers and in the shell for native dev, e.g. `.env`: `FRONTEND_PORT=3100`, `API_PORT=8100`, and `FRONTEND_PORT=3100 API_PORT=8100 pnpm dev`.

**Never** run, from any directory, broad Docker cleanup commands (`docker system prune`, `docker volume prune`, `docker network prune`) or `docker compose down` in another project's directory. Use only the `pnpm infra:*` scripts (or `docker compose` from this repository) for MTI 360.

## 6. PostgreSQL

- Image `pgvector/pgvector:0.8.6-pg18-trixie`. The pgvector extension is available but **not enabled** (AI phase).
- The PostgreSQL 18 image keeps data under `/var/lib/postgresql/18/docker`; the volume is mounted at `/var/lib/postgresql`.
- `database/init/01-roles.sh` runs **only on an empty volume** and creates:

| Role | Purpose | Attributes |
|---|---|---|
| `mti_owner` | Owns the database and `public` schema; future migrations | LOGIN, no SUPERUSER/CREATEDB/CREATEROLE/REPLICATION/BYPASSRLS |
| `mti_app` | Application runtime (DML via default privileges) | same restrictions |
| `mti_readonly` | Reporting / governed SQL agent (SELECT) | same restrictions |

- Password authentication (`scram-sha-256`) is enforced for every connection from outside the container (host port and Compose network). The upstream image trusts local socket/loopback connections *inside* the container (reachable only with `docker exec`).
- Changing role passwords in `.env` does not affect an existing volume; run `pnpm infra:reset` (deletes data) or change them with `ALTER ROLE`.
- Migrations (T01-01): `pnpm db:migrate` applies Alembic migrations as `mti_owner` (`MIGRATIONS_DATABASE_URL`); `pnpm db:check` fails when models and migrations differ. `pnpm stack:up` runs the one-shot `migrate` container before starting the api. Revisions: `0001` baseline, `0002` `audit_events` (T01-02); no business tables yet.
- **Test database** (T01-01): `database/init/02-test-database.sh` creates `${POSTGRES_DB}_test` (default `mti360_test`) with the same roles and grants. It runs automatically on an empty volume. For an **existing** volume, run it once (idempotent, keeps data):

  ```bash
  MSYS_NO_PATHCONV=1 docker compose exec postgres bash /docker-entrypoint-initdb.d/02-test-database.sh
  ```

- **Database tests** run only when the test URLs are set; otherwise they are skipped. Use the passwords from the root `.env` (URL-safe values):

  ```bash
  export TEST_DATABASE_URL=postgresql+asyncpg://mti_app:<MTI_APP_PASSWORD>@127.0.0.1:5432/mti360_test
  export TEST_MIGRATIONS_DATABASE_URL=postgresql+asyncpg://mti_owner:<MTI_OWNER_PASSWORD>@127.0.0.1:5432/mti360_test
  export TEST_READONLY_DATABASE_URL=postgresql+asyncpg://mti_readonly:<MTI_READONLY_PASSWORD>@127.0.0.1:5432/mti360_test
  pnpm test:backend      # REQUIRE_DATABASE_TESTS=1 turns skips into failures (CI)
  ```

  Never point these variables at a database with data you want to keep: the tests migrate it up and down.

## 7. Object storage (SeaweedFS)

- `weed mini` with only the S3 API enabled (WebDAV, admin UI, Iceberg/Lance catalogs and telemetry are disabled).
- The S3 admin identity comes from `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY`; anonymous requests receive `403 AccessDenied`.
- The one-shot `object-storage-init` service creates `S3_BUCKET` (idempotent) and is removed after it runs.
- Use path-style addressing and SigV4 (`region` any, e.g. `us-east-1`); presigned URLs work.

## 8. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `required variable ... is missing a value` | `.env` missing or incomplete — copy `.env.example` and fill every value |
| `address already in use` / `EADDRINUSE` | Port used by another project — override the port (§5) |
| Native frontend: "Another next dev server is already running" | Next.js allows one `next dev` per project directory — stop the other one |
| Roles/passwords unchanged after editing `.env` | Init scripts run only on an empty volume (§6) |
| `pnpm` fails in Git Bash with `Cannot find module ...corepack/dist/pnpm.js` | Git-Bash path conversion; use PowerShell/cmd, or do not set `MSYS_NO_PATHCONV` when running pnpm and add `%APPDATA%\npm` to PATH in POSIX form |
