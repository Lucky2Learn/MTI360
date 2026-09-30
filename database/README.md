# database/

**Status:** Role bootstrap (T00-03): [init/01-roles.sh](init/01-roles.sh). Test database (T01-01): [init/02-test-database.sh](init/02-test-database.sh). The schema is owned by Alembic (`backend/migrations`). No RLS policies, extensions or seeds yet.

`init/01-roles.sh` runs automatically **only when the local Postgres volume is empty** and creates `mti_owner` (owns the database and `public` schema; future migrations), `mti_app` (DML via default privileges) and `mti_readonly` (SELECT). None has SUPERUSER, CREATEDB, CREATEROLE, REPLICATION or BYPASSRLS. Passwords come from the root `.env` only. See [docs/runbooks/local-development.md](../docs/runbooks/local-development.md) §6.

## Purpose

PostgreSQL bootstrap and development data that is **not** owned by Alembic migrations.

```text
database/
├── init/     Local bootstrap run once by the Postgres container:
│             roles (owner / app / readonly), extensions
└── seeds/    Realistic maritime development fixtures
```

## Ownership

Backend engineering, with security review for anything touching database roles or grants.

## What belongs here

- Local-development bootstrap SQL (database roles, extensions)
- Development seed data using realistic maritime examples (courses such as Pre-Sea Training, DNS, B.Sc. Nautical Science; batches; demo institutes) — clearly marked as development fixtures

## What does NOT belong here

- **Schema migrations** — these live in `backend/migrations/` (Alembic), see [ADR-0002](../docs/adr/0002-monorepo-layout.md)
- Real customer data, production dumps or backups (ignored by `.gitignore` and must never be committed)
- Passwords or credentials — bootstrap scripts read them from environment variables
- Hard-coded tenant identity used by the application (CLAUDE.md §60)

## Populated by

| Task | Adds |
|---|---|
| T00-03 ✅ | `init/01-roles.sh` role bootstrap for the local Postgres container (extensions are enabled later, e.g. pgvector in the AI phase) |
| T01-01 ✅ | `init/02-test-database.sh`: idempotent `${POSTGRES_DB}_test` database with the same roles, ownership and default privileges, for the backend integration tests |
| T01-08 | `seeds/dev.json` development fixtures (decision D16) |
