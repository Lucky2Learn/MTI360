# ADR-0002 — Monorepo Layout

- **Status:** Accepted
- **Date:** 2026-09-26
- **Task:** T00-01
- **Related:** ARCHITECTURE.md §12, §41; [repository-structure.md](../architecture/repository-structure.md)

## Context

MTI 360 has one product, four experiences, one backend and one design language. The repository already contained empty local directories named `frontend/`, `backend/`, `database/`, `docs/`, `infrastructure/` and `tests/`, and ARCHITECTURE.md §12/§41 used `backend/` and `frontend/` in its examples. The specification documents are referenced by root path from `CLAUDE.md` and from each other.

## Decision

1. **Single monorepo** containing frontend, backend, database bootstrap, infrastructure, cross-stack tests, documentation and scripts.
2. **Top-level directories** reuse the existing names:

   ```text
   frontend/        Next.js app (four experiences)
   backend/         FastAPI modular monolith + Alembic migrations + backend tests
   database/        Postgres bootstrap (init/) and development seeds (seeds/)
   infrastructure/  Local service configuration; later deployment configuration
   tests/           Cross-stack E2E and accessibility suites
   docs/            ADRs, architecture notes, runbooks
   scripts/         Thin developer helpers (.sh / .ps1)
   ```

3. **Specifications stay at the repository root** (`CLAUDE.md`, `PRD.md`, `ARCHITECTURE.md`, …). They are not moved into `docs/`.
4. **Alembic migrations live in `backend/migrations/`**, because they are coupled to the SQLAlchemy models. `database/` holds only bootstrap and seed material.
5. **One Next.js application** serves the Platform Control Plane, Tenant Application, Student Portal and Tenant Public Website through separate route trees and shells. `design-system/`, `features/` and `lib/` are independent of routes so the app can be split later without moving code.
6. **The MTI 360 marketing website** remains at the root, unchanged, until a separate relocation task moves it to `marketing-site/` (see ADR-0003).
7. Directories are created only when a task needs them. T00-01 creates top-level directories with README files only — no scaffolding or placeholder code.

## Consequences

- One pull request can change API and UI together (vertical slices, CLAUDE.md §80).
- A single CI pipeline must understand both Python and Node toolchains (T00-05).
- Root paths used throughout the specifications remain valid.
- The root temporarily holds both specifications and the marketing website files; this is accepted until the relocation task.

## Alternatives considered

- **`apps/*` + `packages/*` workspace layout** — common for JavaScript monorepos, but would rename the directories ARCHITECTURE.md already uses and adds workspace tooling not yet needed. Rejected for now.
- **Separate repositories for frontend and backend** — weakens vertical-slice development and cross-cutting tenancy/security review. Rejected.
- **Migrations in `database/migrations/`** — separates migrations from the models they are generated from. Rejected.
- **Separate Next.js apps per experience from day one** — stronger isolation but duplicates the design system and configuration before there is any code. Deferred; the chosen structure keeps this option open.
