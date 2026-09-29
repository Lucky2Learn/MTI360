# MTI 360

**The Complete Growth & Operations Platform for Maritime Training Institutes**

*Acquire Students. Simplify Operations. Grow Your Institute.*

---

## What MTI 360 is

MTI 360 is a multi-tenant SaaS platform for Maritime Training Institutes. It connects the complete institute lifecycle in one platform:

```text
Acquire → Convert → Admit → Train → Collect → Communicate → Comply → Place → Grow
```

It covers marketing and lead management, counselling, applications and admissions, students, courses, batches, timetable, attendance, faculty, examinations, certificates, finance, compliance, placement, WhatsApp / email / SMS / voice communication, workflow automation, governed AI agents and analytics.

## Product vision

One operating platform for maritime training institutes: secure, multi-tenant, AI-assisted but human-controlled, responsive on every device, and built on a premium maritime design language. See [PRD.md](PRD.md).

MTI 360 is **one product with four experiences**:

| # | Experience | Users |
|---|---|---|
| 1 | Platform Control Plane | MTI 360 platform administrators (tenants, plans, billing, provisioning, AI providers, support, security) |
| 2 | Tenant Application | Maritime Training Institute staff |
| 3 | Student Portal | Students (mobile-first) |
| 4 | Tenant Public Website | Prospective students and the public, per institute (tenant-branded) |

## Current status

> **No product functionality has been implemented yet.** The development toolchain (T00-02), local Docker infrastructure (T00-03), validated per-environment configuration (T00-04), CI (T00-05), the design-token foundation with Light/Dark/System themes (T00-06) the component library (T00-07) and the application shell with the four experience route boundaries (T00-08, placeholder pages only) the responsive layout primitives (T00-09) and the accessibility foundation (T00-10: WCAG 2.2 AA contract, guards and tests) exist; the frontend has a neutral token-styled root page, the shell at `/platform`, `/app`, `/student` and `/site`, and a development-only component and layout showcase, and the backend only a `/health` liveness endpoint. No database schema, authentication or tenancy exists.

| Area | Status |
|---|---|
| Product and engineering specifications | Baseline complete |
| T00-01 Repository Structure | `COMPLETED` |
| T00-02 Development Environment | `COMPLETED` (merged, PR #1) |
| T00-03 Docker Development Environment | `COMPLETED` (merged, PR #3) |
| T00-04 Environment Configuration | `COMPLETED` (merged, PR #4) |
| T00-05 CI Foundation | `COMPLETED` (merged, PR #5) |
| T00-06 Design Token Foundation | `COMPLETED` (merged, PR #6) |
| T00-07 Core Component Library | `COMPLETED` (merged, PR #7, PR #8, PR #9) |
| T00-08 Application Shell | `COMPLETED` (merged, PR #10) |
| T00-09 Responsive Layout Foundation | `COMPLETED` (merged, PR #11) |
| T00-10 Accessibility Foundation | `READY_FOR_REVIEW` |
| Product features (screens, APIs, database, auth, tenancy) | Not started |

The live tracker is [DEVELOPMENT-STATUS.md](DEVELOPMENT-STATUS.md).

## Architecture summary

| Concern | Choice |
|---|---|
| Frontend | Next.js + React + TypeScript — one app, four experiences |
| Backend | Python + FastAPI — modular monolith |
| Database | PostgreSQL + SQLAlchemy + Alembic |
| Cache / queue / sessions | Redis |
| Files | S3-compatible object storage |
| Local development | Hybrid: infrastructure in Docker Compose (project `mti360`), apps run natively |
| Multi-tenancy | Shared schema with `tenant_id`; tenant context derived server-side only; enforced by repositories, an ORM filter, PostgreSQL Row-Level Security and composite foreign keys |
| Identity | Separate platform identity; opaque server-side sessions per realm; explicit, audited support sessions |

Decisions are recorded as ADRs in [docs/adr/](docs/adr/). Details: [ARCHITECTURE.md](ARCHITECTURE.md), [docs/architecture/](docs/architecture/).

## Repository structure

```text
MTI360/
├── *.md                        Product and engineering specifications (source of truth)
├── index.html app.js styles.css MTI 360 marketing website (see note below)
├── package.json, pnpm-workspace.yaml   Root commands and pnpm workspace (no dependencies)
├── compose.yaml                Local Docker infrastructure + app images (project "mti360")
├── frontend/                   Next.js application
├── backend/                    FastAPI modular monolith (uv-managed)
├── database/                   PostgreSQL bootstrap and development seeds
├── infrastructure/             Local service configuration (object-storage bucket init)
├── tests/                      Cross-stack E2E and accessibility suites
├── docs/                       ADRs and architecture notes
└── scripts/                    Developer helper scripts
```

Each directory has a README describing what belongs there. Full target tree: [docs/architecture/repository-structure.md](docs/architecture/repository-structure.md).

## Documents

| Document | Purpose |
|---|---|
| [CLAUDE.md](CLAUDE.md) | Engineering constitution — read first |
| [PRD.md](PRD.md) | Product requirements |
| [APP-FLOW.md](APP-FLOW.md) | Application flows |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System architecture |
| [PLATFORM-ADMIN.md](PLATFORM-ADMIN.md) | SaaS control plane specification |
| [DESIGN-SYSTEM.md](DESIGN-SYSTEM.md) | Design tokens, themes, components |
| [UI-SCREENS.md](UI-SCREENS.md) | Screen inventory |
| [TASKS.md](TASKS.md) | Implementation roadmap |
| [DEVELOPMENT-STATUS.md](DEVELOPMENT-STATUS.md) | Live implementation status |
| [MASTER-CLAUDE-DESIGN-PROMPT.md](MASTER-CLAUDE-DESIGN-PROMPT.md) | Design-tool brief |
| [docs/README.md](docs/README.md) | ADRs, architecture notes, known specification inconsistencies |

## Development sequence

Engineering follows [TASKS.md](TASKS.md):

```text
PHASE 00 Foundation → 01 Authentication & Multi-Tenancy → 02 Platform Control Plane
→ 03 Tenant Foundation → 04 Admissions → 05 Academics → 06 Finance → 07 Compliance
→ 08 Placement → 09 Communication → 10 Automation → 11 AI → 12 Analytics
→ 13 Student Portal → 14 Tenant Public Website → 15 SaaS Billing & Operations
→ 16 Security & Hardening → 17 Production Readiness
```

Phase 00 order: T00-01 Repository Structure → T00-02 Development Environment → T00-03 Docker → T00-04 Environment Configuration → T00-05 CI → T00-06 Design Tokens → T00-07 Components → T00-08 Application Shell → T00-09 Responsive → T00-10 Accessibility.

## Getting started

### Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Node.js | 24 LTS (`.nvmrc`: 24.21.0; `>=24.15.0 <25` accepted) | |
| pnpm | 11.28.0 (from `packageManager`) | `corepack enable` (or, without admin rights on Windows: `corepack enable --install-directory "%APPDATA%\npm" pnpm`) |
| uv | 0.12.x (≥ 0.12.19) | [Official installer](https://docs.astral.sh/uv/getting-started/installation/) |
| Python | 3.14 | Installed and managed by uv — no system Python required |
| Git | any recent | Tags must be present (`git fetch --tags`) for `pnpm check:landing` |
| Docker Desktop | Engine 29.x, Compose v2+ | Local infrastructure (PostgreSQL, Redis, S3, Mailpit) |

### Quick start

```bash
cp .env.example .env   # then replace every change-me with a long random value (never commit .env)
pnpm bootstrap         # install frontend (frozen lockfile) and backend (locked) dependencies
pnpm infra:up          # PostgreSQL 18, Redis 8.8, SeaweedFS S3, Mailpit in Docker (project "mti360")
pnpm dev               # native frontend http://localhost:3000, backend http://127.0.0.1:8000/health
pnpm check             # CI's repo/frontend/backend checks: landing, env, lock, format, lint, typecheck, tests, build
```

Ports can be changed if 3000/8000 are in use (for example by another local project): `FRONTEND_PORT=3100 API_PORT=8100 pnpm dev`, and the same variables in `.env` for containers. Full guide: [docs/runbooks/local-development.md](docs/runbooks/local-development.md).

### Commands

| Command | Purpose |
|---|---|
| `pnpm bootstrap` | Install all dependencies from the lockfiles |
| `pnpm dev` / `pnpm dev:frontend` / `pnpm dev:backend` | Run both apps / one app |
| `pnpm build` | Production build of the frontend |
| `pnpm lint` | ESLint (frontend) and Ruff (backend) |
| `pnpm typecheck` | TypeScript and mypy (strict) |
| `pnpm test` | Vitest (frontend) and pytest (backend) |
| `pnpm format` / `pnpm format:check` | Prettier (frontend) and Ruff format (backend) |
| `pnpm check:landing` | Verify the marketing website files are unchanged |
| `pnpm check:env` | Environment template and secret hygiene |
| `pnpm check:lock` | Verify `backend/uv.lock` is up to date |
| `pnpm check` | All of the above checks in CI order |
| `pnpm infra:up` / `pnpm infra:down` | Start / stop local infrastructure (volumes kept) |
| `pnpm infra:reset` | Delete all local MTI 360 containers, network and `mti360_*` volumes (only MTI 360) |
| `pnpm infra:logs` | Follow container logs |
| `pnpm stack:up` | Build and run infrastructure plus the api and frontend images |

Versions, holds, supply-chain controls and update policy: [docs/architecture/toolchain.md](docs/architecture/toolchain.md).

### Continuous integration

Every pull request to `main` and every push to `main` runs the CI workflow (jobs `repo`, `frontend`, `backend`, `secrets`, `docker`); the single required status is **`ci-ok`**. CodeQL and dependency audits report but are not required. Git workflow: feature branch → pull request → **Create a merge commit** → `main`. Details, local reproduction and the branch-protection configuration: [docs/architecture/ci.md](docs/architecture/ci.md).

## Marketing website note

The root `index.html`, `app.js` and `styles.css` are the **MTI 360 marketing website** — a static page promoting MTI 360 itself.

- It is **not** the MTI 360 application and **not** the Tenant Public Website ([ADR-0003](docs/adr/0003-marketing-vs-tenant-public-website.md)).
- Status: **Prototype — not production ready.** Its demo-request form does not send data.
- Do not modify, move or delete these files without an explicit `MKT-*` task ([TASKS.md](TASKS.md)).

## Security and environment warning

- **Never commit secrets.** Only `*.example` environment files are tracked. Copy `.env.example`, `backend/.env.example` and `frontend/.env.example` to their ignored local counterparts and replace every `change-me` placeholder locally.
- **Never put a secret in a `NEXT_PUBLIC_*` variable** — those values are shipped to every browser.
- API keys, provider tokens, database passwords, session/encryption keys, certificates, database dumps and uploaded files must never enter the repository.
- Tenant isolation is enforced server-side. Never trust a tenant identifier supplied by the browser (CLAUDE.md §5–§6).
