# database/

**Status:** Reserved. No database files exist yet.

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
| T00-03 | `init/` role and extension bootstrap for the local Postgres container |
| Phase 01+ | `seeds/` development fixtures as each vertical slice is built |
