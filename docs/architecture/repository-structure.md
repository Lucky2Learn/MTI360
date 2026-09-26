# Repository Structure

- **Status:** Approved (T00-01)
- **Decisions:** [ADR-0001](../adr/0001-stack.md), [ADR-0002](../adr/0002-monorepo-layout.md), [ADR-0003](../adr/0003-marketing-vs-tenant-public-website.md), [ADR-0006](../adr/0006-api-prefixes.md)

This document describes the **target** repository shape. Items marked ✅ exist after T00-01. Everything else is reserved and is created only by the task noted — never as empty placeholders.

## 1. Repository tree

```text
MTI360/
├── README.md                          ✅
├── CLAUDE.md  PRD.md  APP-FLOW.md  ARCHITECTURE.md  PLATFORM-ADMIN.md
├── DESIGN-SYSTEM.md  UI-SCREENS.md  TASKS.md  DEVELOPMENT-STATUS.md
├── MASTER-CLAUDE-DESIGN-PROMPT.md     ✅ specifications stay at the root
│
├── index.html  app.js  styles.css     ✅ MTI 360 marketing website — PRESERVED, UNCHANGED
│                                         (later relocated to marketing-site/, ADR-0003)
│
├── .gitignore  .gitattributes  .editorconfig          ✅
├── .env.example                       ✅ Compose-level placeholders
├── compose.yaml                       T00-03
│
├── docs/                              ✅
│   ├── README.md                      ✅ documentation index
│   ├── adr/                           ✅ Architecture Decision Records
│   ├── architecture/                  ✅ structure, tenancy, security, inconsistencies
│   └── runbooks/                      later
│
├── marketing-site/                    later relocation task (MKT-01)
│
├── frontend/                          ✅ README + .env.example only
│   ├── package.json  tsconfig.json  next.config.ts  eslint config     T00-02
│   ├── Dockerfile                                                     T00-03
│   ├── public/
│   └── src/
│       ├── middleware.ts              host → experience rewrite, security headers, CSP nonce
│       ├── app/
│       │   ├── platform/              Platform Control Plane
│       │   ├── (tenant-auth)/         AUTH-01 … AUTH-05
│       │   ├── app/                   Tenant Application
│       │   ├── student/               Student Portal
│       │   └── sites/[site]/          Tenant Public Website (rewrite target only)
│       ├── design-system/
│       │   ├── tokens/                semantic CSS variables, Light + Dark
│       │   ├── theme/                 Light / Dark / System + pre-paint script
│       │   ├── components/            core components
│       │   └── templates/             T01 … T18
│       ├── shells/                    PlatformShell, TenantShell, StudentShell, PublicSiteShell
│       ├── features/                  UI feature modules mirroring backend modules
│       ├── lib/                       api client, session helpers, PermissionGate (UX only)
│       └── test/                      test utilities, MSW handlers
│
├── backend/                           ✅ README + .env.example only
│   ├── pyproject.toml  <lockfile>  alembic.ini                        T00-02
│   ├── Dockerfile                     one image → api | worker | migrate   T00-03
│   ├── migrations/                    Alembic, single linear history
│   ├── app/
│   │   ├── main.py
│   │   ├── core/                      config, logging, errors, ids, context, db/, security/,
│   │   │                              authz/, tenancy/, audit/, events/, jobs/, storage/, cache/
│   │   ├── api/                       platform.py, tenant.py, student.py, public.py, webhooks.py
│   │   ├── modules/                   business domains (§3)
│   │   ├── integrations/              whatsapp, email, sms, voice, payments, llm, storage adapters
│   │   └── workers/                   worker entrypoint, job registry
│   └── tests/                         unit/, integration/, api/, security/
│
├── database/                          ✅ README only
│   ├── init/                          roles (owner / app / readonly), extensions   T00-03
│   └── seeds/                         realistic maritime development fixtures
│
├── infrastructure/                    ✅ README only
├── tests/                             ✅ README only — e2e/, accessibility/
├── scripts/                           ✅ README only
└── .github/workflows/                 T00-05
```

## 2. Frontend architecture

One Next.js App Router application; four experiences with separate route trees, shells and session realms.

| Experience | Local path | Production host (planned) | Shell |
|---|---|---|---|
| Platform Control Plane | `/platform/*` (`/platform/login`) | `admin.<domain>` | PlatformShell |
| Tenant Application | `/login` … (AUTH-01–05), `/app/*` | `app.<domain>` | TenantShell + support-session banner slot |
| Student Portal | `/student/*` | `app.<domain>/student` (or `student.<domain>`) | StudentShell (mobile-first) |
| Tenant Public Website | `/sites/[site]/*` (internal) | `<slug>.<sites-domain>` or verified custom domain | PublicSiteShell (tenant-branded) |

- **Route groups** separate unauthenticated pages from shell layouts inside each experience (for example `platform/(auth)/login` vs `platform/(console)/dashboard`).
- **Layouts** are server components that read the session from the backend and redirect on the wrong realm — this is UX routing, not security.
- **Middleware** performs host → experience rewrite, blocks direct external access to `/sites/*`, sets security headers and the CSP nonce, and redirects when no session cookie exists. It makes **no** authorization decisions and never derives a trusted tenant.
- **No tenant identifier in tenant-application URLs** (ADR-0005).
- **Data access:** the browser calls FastAPI through a same-origin proxy (`/api/*`); server components call the backend server-side. Next.js has **no database access and no business logic**. TanStack Query for server state; Zod for form UX validation (the backend validates authoritatively). TypeScript API types are generated from FastAPI's OpenAPI schema.
- **Import boundaries:** `app/` composes `features/` and `shells/`; `features/` may import `design-system/` and `lib/`, and other features only via their public `index.ts`; `design-system/` imports nothing from `features/`.
- **Theme:** Light / Dark / System, pre-paint script (no flash), live OS-preference listener, preference persisted per user when authenticated and locally otherwise (DESIGN-SYSTEM.md §13–§15).

## 3. Backend architecture

FastAPI modular monolith.

### Layering inside a module

```text
modules/<domain>/
├── router.py        API layer — HTTP ↔ schemas, auth/authz dependencies, no business logic
├── schemas.py       Pydantic request/response contracts
├── service.py       Application layer — use cases, transactions, authz, state transitions, events
├── domain.py        Pure rules — state machines, calculations, invariants (no I/O)
├── models.py        SQLAlchemy models owned by this module only
├── repository.py    Data access — extends TenantScopedRepository
├── permissions.py   Permission constants registered centrally
├── events.py        Events published by this module
└── jobs.py          Background job handlers owned by this module
```

Files are created only when needed. Dependency direction: `router → service → (domain, repository) → models`. A module calls another module **only through its service**. `core/` depends on no module. These rules are enforced with import linting from T00-05.

### Modules

| Module | Covers | Realms exposed |
|---|---|---|
| `identity` | authentication, users, credentials, sessions, MFA, password reset (tenant + student) | tenant, student |
| `platform_identity` | platform users, platform roles, platform MFA | platform |
| `access` | tenant roles, permissions, role assignments, campus scope | tenant |
| `tenants` | tenant registry, lifecycle state machine, domains, provisioning | platform; public (domain resolution, internal) |
| `subscriptions` | plans, entitlements, overrides, usage metering | platform (manage); tenant (read own) |
| `billing` | MTI 360 → tenant invoices and payments (SaaS billing) | platform; tenant (read own) |
| `support` | support tickets, support sessions | platform; tenant (raise tickets) |
| `platform_ops` | feature flags, system health, job monitoring, platform settings | platform |
| `institute` | institute profile, branding, campuses, tenant settings | tenant; public (published branding) |
| `crm` | leads, lead activities, counselling | tenant; public (enquiry capture) |
| `admissions` | applications, eligibility, admission approval | tenant; student (own application) |
| `students` | Student 360 | tenant; student (self) |
| `academics` | courses, batches, timetable, attendance, faculty, examinations, certificates | tenant; student; public (published courses) |
| `finance` | student fee structures, invoices, payments, refunds (not SaaS billing) | tenant; student |
| `compliance` | requirements, inspections, corrective actions | tenant |
| `placement` | companies, opportunities, placement tracking, alumni | tenant; student |
| `documents` | document metadata, verification, secure download | tenant; student |
| `communication` | channels, conversations, messages, templates | tenant; webhooks |
| `notifications` | in-app and outbound notifications | all |
| `automation` | workflows, executions | tenant |
| `ai` | agent runtime, tool registry, knowledge/RAG, executions, provider routing | platform (providers, guardrails); tenant (configuration, use) |
| `analytics` | tenant analytics; platform aggregates | tenant; platform (aggregates only) |
| `audit` | audit queries (writer in `core/audit`) | platform; tenant (own) |

### API realms (ADR-0006)

`/api/v1/platform/*`, `/api/v1/*` (tenant), `/api/v1/student/*`, `/api/v1/public/*`, `/api/v1/webhooks/*` — each mounted with a realm dependency.

### Integrations and workers

- Each provider type has an interface, one or more adapters and a **fake adapter** for deterministic tests. Credentials are server-side only.
- One backend image runs as `api`, `worker` or `migrate`. Every job carries `{tenant_id, actor, correlation_id, idempotency_key}`; the worker re-establishes context through the same code path as the API.
- Domain events are written to a **transactional outbox** and enqueued only after commit (ARCHITECTURE.md §66).
- The queue library is selected in T00-03 behind `core/jobs`.

## 4. Testing layout

| Suite | Tooling (planned) | Location |
|---|---|---|
| Backend unit | pytest | `backend/tests/unit/` |
| Backend integration (real PostgreSQL, RLS, migrations, jobs, storage) | pytest + disposable Postgres | `backend/tests/integration/` |
| Backend API | pytest + ASGI client | `backend/tests/api/` |
| Tenant isolation / security | pytest | `backend/tests/security/` |
| Frontend unit / component | Vitest + React Testing Library | colocated in `frontend/src/` |
| Frontend integration | RTL + MSW | `frontend/src/test/` |
| End-to-end | Playwright against the full stack | `tests/e2e/` |
| Accessibility | axe via Playwright, 390/768/1024/1440 × Light/Dark | `tests/accessibility/` |

SQLite is not used for backend tests: RLS and PostgreSQL features must be exercised. The tenant-isolation suite is described in [tenancy.md](tenancy.md#8-tenant-isolation-test-gate).

## 5. Environment files

| File | Committed | Purpose |
|---|---|---|
| `.env.example`, `backend/.env.example`, `frontend/.env.example` | **Yes** | Placeholder templates with a comment per variable |
| `.env`, `backend/.env`, `backend/.env.local`, `frontend/.env.local`, any other `.env.*` | **Never** | Real local values |
| Staging / production configuration | **Never as files** | Injected by the secret manager / CI |

`APP_ENV` is one of `development | test | staging | production`. From T00-04, production settings validation must refuse placeholder secrets, debug mode, permissive CORS and the fake AI provider. See [security.md](security.md#9-secrets-and-configuration).

## 6. Local infrastructure (T00-03)

Root `compose.yaml` with profiles `infra` (postgres, redis, object-storage emulator, mailpit) and `app` (migrate, api, worker, frontend). Ports bound to `127.0.0.1`, health-check-gated startup, named volumes. The object-storage emulator product is chosen in T00-03. No production compose, reverse proxy or monitoring stack until required.

## 7. Git workflow

- T00-01 work is committed on `claude/compassionate-johnson-gxdgr9`, one commit per sub-step.
- Baseline tags: `spec-baseline-v1` (specification baseline) and `marketing-site-v1` (marketing website baseline).
- After T00-01 review, `main` is created from the reviewed commit and made the default branch with protection (pull request required, no force-push; required CI checks after T00-05). The existing branch is preserved.
- Afterwards: short-lived branches (`feat/T00-02-…`, `fix/…`, `docs/…`), one task per pull request, squash merge, conventional commits including the task ID. Architecture changes require an ADR.
