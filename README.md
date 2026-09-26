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

> **No application code has been implemented yet.**

| Area | Status |
|---|---|
| Product and engineering specifications | Baseline complete |
| T00-01 Repository Structure | `READY_FOR_REVIEW` |
| Phase 00 Foundation (T00-02 … T00-10) | Not started |
| Application (frontend, backend, database) | Not started |

The live tracker is [DEVELOPMENT-STATUS.md](DEVELOPMENT-STATUS.md).

## Architecture summary

| Concern | Choice |
|---|---|
| Frontend | Next.js + React + TypeScript — one app, four experiences |
| Backend | Python + FastAPI — modular monolith |
| Database | PostgreSQL + SQLAlchemy + Alembic |
| Cache / queue / sessions | Redis |
| Files | S3-compatible object storage |
| Local development | Docker Compose (from T00-03) |
| Multi-tenancy | Shared schema with `tenant_id`; tenant context derived server-side only; enforced by repositories, an ORM filter, PostgreSQL Row-Level Security and composite foreign keys |
| Identity | Separate platform identity; opaque server-side sessions per realm; explicit, audited support sessions |

Decisions are recorded as ADRs in [docs/adr/](docs/adr/). Details: [ARCHITECTURE.md](ARCHITECTURE.md), [docs/architecture/](docs/architecture/).

## Repository structure

```text
MTI360/
├── *.md                        Product and engineering specifications (source of truth)
├── index.html app.js styles.css MTI 360 marketing website (see note below)
├── frontend/                   Next.js application (from T00-02)
├── backend/                    FastAPI modular monolith + Alembic migrations (from T00-02)
├── database/                   PostgreSQL bootstrap and development seeds
├── infrastructure/             Local service configuration (from T00-03)
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

Setup instructions will be added in T00-02 / T00-03. There is nothing to build or run yet.

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
