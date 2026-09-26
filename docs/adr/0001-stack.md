# ADR-0001 — Technology Stack

- **Status:** Accepted
- **Date:** 2026-09-26
- **Task:** T00-01
- **Related:** ARCHITECTURE.md §5, §68–§72; ADR-0002

## Context

`ARCHITECTURE.md` specified Next.js + React + TypeScript for the frontend and Python + FastAPI for the backend. The repository audit (T00-01 Step 01) noted that an earlier project brief mentioned Spring Boot, which appears in no specification. The stack had to be confirmed before any repository structure could be created.

The repository currently contains only specifications and a static marketing website; no application code exists, so there is no migration cost in either direction.

## Decision

| Concern | Decision |
|---|---|
| Frontend | **Next.js (App Router) + React + TypeScript** |
| Backend | **Python + FastAPI** |
| Validation / API schemas | Pydantic |
| ORM | **SQLAlchemy 2.0**, async (`asyncpg`), typed `Mapped[]` models, `lazy="raise"` by default |
| Migrations | **Alembic** |
| Database | **PostgreSQL** (single database, shared schema, `tenant_id` — see ADR-0004) |
| Vector search | `pgvector` in the same PostgreSQL instance, introduced when AI/RAG work begins |
| Cache / queue / sessions | **Redis** |
| Object storage | **S3-compatible** storage (local emulator in development) |
| Background jobs | Python worker behind an internal `core/jobs` abstraction. **The queue library is chosen in T00-03**, not in this ADR |
| Local orchestration | **Docker Compose** (T00-03) |
| Architecture style | **Modular monolith** — no microservices at this stage |
| Package managers | `uv` (Python) and `pnpm` (Node). Exact runtime versions (Python 3.12+, Node LTS) are pinned in T00-02 |
| Frontend styling / primitives | Tailwind CSS mapped to semantic design tokens; headless accessible primitives (e.g. Radix). **Approved in principle; confirmed in T00-06/T00-07** |
| AI providers | Provider abstraction with a deterministic `fake` provider for development and tests (CLAUDE.md §46) |

## Consequences

- Python gives direct access to the AI/agent ecosystem the product depends on (agent runtime, RAG, tool calling, evaluation).
- Two languages (TypeScript + Python) must be maintained; API types are generated from FastAPI's OpenAPI schema to keep the contract in sync.
- Async SQLAlchemy requires discipline around session scope and eager loading; `lazy="raise"` prevents implicit lazy loads.
- Choosing the queue library later keeps T00-01/T00-02 small but requires every job to go through `core/jobs`.

## Alternatives considered

- **Spring Boot (Java) backend** — mature enterprise ecosystem and existing Java expertise, but weaker fit for the AI/agent runtime that ARCHITECTURE.md places in Python; would require a separate Python service for AI from day one. Rejected.
- **React + Vite SPA instead of Next.js** — simpler build, but no server components, server-side session handling or SSR for the tenant public website. Rejected.
- **Synchronous SQLAlchemy** — simpler mental model; rejected in favour of async to match FastAPI and the I/O-heavy provider integrations.
- **Separate vector database** — rejected for now; `pgvector` keeps tenant isolation (RLS) and transactions in one place. Can be revisited if scale requires it.
