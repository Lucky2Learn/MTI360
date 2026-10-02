# MTI 360 — DEVELOPMENT-STATUS.md

## Live Development Status & Execution Tracker

**Product:** MTI 360  
**Positioning:** The Complete Growth & Operations Platform for Maritime Training Institutes  
**Tagline:** Acquire Students. Simplify Operations. Grow Your Institute.  
**Document:** `DEVELOPMENT-STATUS.md`  
**Version:** 1.0  
**Status:** Development Tracking Baseline

---

# 1. PURPOSE

This document is the **live implementation status** of MTI 360.

It records:

- what has been implemented
- what is currently being developed
- what has been verified
- what is blocked
- what remains
- what should be implemented next

This document must be updated throughout development.

---

# 2. IMPORTANT DISTINCTION

```text
TASKS.md
    ↓
What should be built

DEVELOPMENT-STATUS.md
    ↓
What has actually been built and verified
```

Do not use this document as a second task specification.

Do not copy the complete task descriptions from `TASKS.md`.

---

# 3. SOURCE DOCUMENTS

Development must remain aligned with:

```text
PRD.md
APP-FLOW.md
ARCHITECTURE.md
PLATFORM-ADMIN.md
DESIGN-SYSTEM.md
UI-SCREENS.md
CLAUDE.md
TASKS.md
DEVELOPMENT-STATUS.md
```

---

# 4. STATUS DEFINITIONS

Use only:

| Status | Meaning |
|---|---|
| `NOT_STARTED` | Work has not started |
| `IN_PROGRESS` | Currently being implemented |
| `BLOCKED` | Cannot continue because of a dependency/problem |
| `READY_FOR_REVIEW` | Implementation completed and awaiting review |
| `COMPLETED` | Implemented and verified |
| `DEFERRED` | Intentionally postponed |

---

# 5. CURRENT PROJECT STATUS

## Overall Status

```text
IN_PROGRESS
```

## Current Phase

```text
PHASE 01 — AUTHENTICATION & MULTI-TENANCY
```

## Current Milestone

```text
M1 — Secure SaaS Foundation (Phase 01)
M0 — Foundation Ready: reached 2026-09-30 (Phase 00 complete)
```

## Overall Completion

```text
0%
```

> The percentage must be updated only from actual completed work. Do not estimate completion merely from the number of files or screens generated.

> **2026-09-30:** Phase 00 is `COMPLETED`: T00-01 … T00-10A are merged to `main` (T00-02 via PR #1, T00-03 via PR #3, T00-04 via PR #4, T00-05 via PR #5, T00-06 via PR #6, T00-07 via PR #7, PR #8 and PR #9, T00-08 via PR #10, T00-09 via PR #11, T00-10 via PR #12, T00-10A via PR #13). Phase 01 is `IN_PROGRESS`: the T01-00 architecture review is approved (D1–D22 with the D10 and D14 amendments) T01-01 (Backend, Database & API Foundation) is `COMPLETED` (PR #14), and T01-02 (Audit Foundation) is `COMPLETED` (PR #16). T01-03 (Tenancy Core) is `COMPLETED` (PR #19). T01-04 (Tenant Identity & Authentication) is `READY_FOR_REVIEW` (branch `feat/T01-04-identity-authentication`, not pushed). All are infrastructure only: database access, migrations, request context, error envelope, logging, realm routers, the append-only audit table with its writers, the `tenants` and `campuses` tables with their isolation layers, and the tenant authentication backend (no screens). No business tables and no product functionality exist yet, so product implementation completion remains 0%.

---

# 6. CURRENT OBJECTIVE

The immediate objective is:

> Establish the MTI 360 technical foundation and prepare the project for secure multi-tenant implementation.

The immediate implementation sequence is:

```text
Repository
    ↓
Development Environment
    ↓
Docker
    ↓
Environment Configuration
    ↓
CI Foundation
    ↓
Design Tokens
    ↓
Core Components
    ↓
Application Shell
    ↓
Responsive Foundation
    ↓
Accessibility Foundation
    ↓
Authentication
    ↓
Multi-Tenancy
```

---

# 7. MASTER PHASE STATUS

| Phase | Description | Status |
|---|---|---|
| 00 | Foundation | `COMPLETED` |
| 01 | Authentication & Multi-Tenancy | `IN_PROGRESS` |
| 02 | Platform Control Plane | `NOT_STARTED` |
| 03 | Tenant Foundation | `NOT_STARTED` |
| 04 | Admissions | `NOT_STARTED` |
| 05 | Academics | `NOT_STARTED` |
| 06 | Finance | `NOT_STARTED` |
| 07 | Compliance | `NOT_STARTED` |
| 08 | Placement | `NOT_STARTED` |
| 09 | Communication | `NOT_STARTED` |
| 10 | Automation | `NOT_STARTED` |
| 11 | AI | `NOT_STARTED` |
| 12 | Analytics | `NOT_STARTED` |
| 13 | Student Portal | `NOT_STARTED` |
| 14 | Public Website | `NOT_STARTED` |
| 15 | SaaS Billing & Operations | `NOT_STARTED` |
| 16 | Security & Hardening | `NOT_STARTED` |
| 17 | Production Readiness | `NOT_STARTED` |

---

# 8. PHASE 00 — FOUNDATION

## Phase Status

```text
COMPLETED
```

## Phase Completion

```text
10 / 10 tasks completed (T00-01 … T00-10 COMPLETED); corrective task T00-10A COMPLETED
```

---

### T00-01 — Repository Structure

**Status:** `COMPLETED` (reviewed; merged to `main` at `914729b`)

**Implementation:**

```text
Repository hygiene: .gitignore, .gitattributes (LF), .editorconfig
Baseline tags (local): spec-baseline-v1 -> 8f0473c, marketing-site-v1 -> 411ef3b
Tracked top-level directories with READMEs:
  frontend/ backend/ database/ infrastructure/ tests/ docs/ scripts/
Environment templates (placeholders only):
  .env.example, backend/.env.example, frontend/.env.example
ADRs: docs/adr/0001-0006
Architecture notes: docs/architecture/repository-structure.md,
  tenancy.md, security.md, spec-inconsistencies.md
README.md rewritten; targeted T00-01 notes added to ARCHITECTURE.md,
  TASKS.md, CLAUDE.md
No application framework, package manifest, Dockerfile, migration,
component, endpoint or business module was created.
```

**Verification:**

```text
git add --renormalize . -> no changes
.env / backend/.env / frontend/.env.local -> ignored (git check-ignore)
*.example files and root landing files -> not ignored
Marketing website SHA-256 (working tree) identical before and after:
  index.html  26343c176523f9740b8c92731262602938cdafb3acb6954035d0112a69cee6a3
  app.js      daab7a05898aad0c1eae622e81c59984476e4d832689a2b180e9a669e413138d
  styles.css  46aa3641042f50d3d66bd81d0072766667bf611a2b9ccfc625481b6ba7eb5e2d
git diff spec-baseline-v1 -- index.html app.js styles.css -> empty
No node_modules, .venv, build output, dumps, credentials or API keys
```

**Notes:**

```text
"Repository builds successfully" (T00-01 DoD) is not applicable until
T00-02 creates a buildable project (amended in TASKS.md).
Awaiting review before the main-branch step (create main from the
reviewed commit; set default branch; branch protection).
Tags are local only; nothing has been pushed.
```

---

### T00-02 — Development Environment

**Status:** `COMPLETED` (merged to `main` via PR #1, merge commit `03b3bec`)

**Implementation:**

```text
Pins: .nvmrc 24.21.0; packageManager pnpm@11.28.0; engines >=24.15.0 <25;
  backend/.python-version 3.14; uv required-version >=0.12.19,<0.13
Workspace: pnpm-workspace.yaml (frontend only), root package.json scripts
  (no dependencies, no orchestration tool), shellEmulator for portable scripts
Frontend: Next.js 16.3.5, React 19.2.8, TypeScript 6.0.3, ESLint 9.39.5
  (next core-web-vitals + typescript, type-aware rules, jsx-a11y, import
  order), Prettier 3.9.8, Vitest 4.1.11 + jsdom + Testing Library;
  layout.tsx + neutral page.tsx + one smoke test
Backend: FastAPI 0.141.1, uvicorn 0.53.0, Pydantic 2.13.5,
  pydantic-settings 2.15.0; Ruff 0.16.8, mypy 2.3.1 (strict), pytest 9.1.1
  (AnyIO plugin); create_app(), Settings, GET /health; 7 smoke tests
Supply chain: 7-day cooldown (pnpm minimumReleaseAge, uv exclude-newer),
  dependency build scripts blocked (strictDepBuilds; unrs-resolver reviewed
  and disallowed), frozen/locked installs, uv run --locked
Not added (D5): SQLAlchemy, Alembic, asyncpg, Redis, S3 client
Docs: docs/architecture/toolchain.md; README, frontend/backend READMEs,
  repository-structure.md, security.md, ARCHITECTURE §5 note, TASKS
```

**Verification:**

```text
pnpm bootstrap (frozen/locked) -> OK
pnpm check -> PASS (check:landing, format:check, lint, typecheck,
  test [vitest 1 passed, pytest 7 passed], build)
pnpm dev (FRONTEND_PORT=3100 API_PORT=8100) -> frontend 200, /health 200
  {"status":"ok"}, no Server / X-Powered-By headers; process tree stopped
  cleanly, ports released
Marketing website files identical to marketing-site-v1 (SHA-256 unchanged)
```

**Notes:**

```text
Local Node is 24.15.0 (accepted by engines); .nvmrc pins 24.21.0 for CI and
Docker. Ports 3000/8000 are occupied on this machine by another project's
Docker containers, hence FRONTEND_PORT / API_PORT overrides.
npm marks ESLint 9 as no longer supported; ESLint 10 remains blocked by
Next.js lint plugin peer ranges (see toolchain.md §3).
`next dev` writes frontend/AGENTS.md and frontend/CLAUDE.md when it detects
an AI agent; not committed — decision pending.
```

---

### T00-03 — Docker Development Environment

**Status:** `COMPLETED` (merged to `main` via PR #3, merge commit `c7b769b`)

**Implementation:**

```text
compose.yaml (project "mti360"; all host ports 127.0.0.1; volumes mti360_*)
  infra: postgres (pgvector/pgvector:0.8.6-pg18-trixie, PG 18.6, pgvector
         not enabled), redis (redis:8.8-alpine), object-storage (SeaweedFS
         4.47, authenticated S3 API only) + one-shot object-storage-init
         (private bucket), mailpit (axllent/mailpit:v1.31)
  app:   api (mti360-api:local), frontend (mti360-frontend:local) —
         read-only rootfs, cap_drop ALL, no-new-privileges, non-root
database/init/01-roles.sh: mti_owner / mti_app / mti_readonly
infrastructure/object-storage/create-bucket.sh
backend/Dockerfile + .dockerignore (uv 0.12.19, python:3.14.7-slim, uid 10001)
frontend/Dockerfile + Dockerfile.dockerignore (node:24.21.0-trixie-slim,
  pnpm 11.28.0, Next.js standalone, uid 1000)
Root scripts: infra:up, infra:down, infra:reset, infra:logs, stack:up
Deferred (D4): migrate (Alembic), worker + queue library
```

**Verification:**

```text
docker compose config: valid; missing .env -> clear "required variable" error
pnpm infra:reset: removed only mti360 containers, network, volumes
pnpm infra:up from empty volumes: exit 0 (~8 s), all healthy
Roles: no SUPERUSER/CREATEDB/CREATEROLE/REPLICATION/BYPASSRLS; mti_owner owns
  database + public schema; default privileges as designed; wrong password
  rejected via Compose network and host port; runtime roles cannot CREATE;
  0 tables, extensions = plpgsql only, 0 RLS policies
Redis PONG (8.8.3); S3 bucket exists, anonymous 403, signed + presigned OK,
  wrong secret rejected; Mailpit readyz OK, UI 200
Native backend 127.0.0.1:8100/health 200; native frontend on 3100 served
  (see Notes)
pnpm stack:up: exit 0; api /health 200 (uid 10001), frontend 200 (uid 1000);
  read-only rootfs, caps dropped; no privileged / host network / docker socket
pnpm infra:down kept volumes; restart did not re-run role bootstrap
pnpm check: PASS; marketing website SHA-256 unchanged
ACRS containers/volumes/networks unchanged by MTI 360 commands
```

**Notes:**

```text
`docker compose up --wait` exits 1 when a one-shot container has exited (even
with code 0), so infra:up / stack:up run the bucket init as a separate
`run --rm` step. PostgreSQL's upstream image trusts connections made inside
the container itself; all external connections require passwords.
Native frontend verification on 3100 used a developer-started `next dev`
(Next.js allows one dev server per project directory).
```

---

### T00-04 — Environment Configuration

**Status:** `COMPLETED` (merged to `main` via PR #4, merge commit `09a7413`)

**Implementation:**

```text
backend/app/core/config.py: Settings types every backend/.env.example
  variable (SecretStr for secrets; hide_input_in_errors); source policy
  (backend/.env read only in development; APP_ENV never from .env);
  per-environment rules raising a value-free ConfigurationError;
  load_settings() / get_settings()
backend/app/main.py: fail-fast contract documented (behaviour unchanged)
frontend/src/lib/env.ts: server-only env contract (APP_ENV, API_BASE_URL;
  NEXT_PUBLIC_APP_NAME the only public value); server-only@0.0.1 added
scripts/check-env.mjs + `pnpm check:env` (in `pnpm check`)
Env templates: comments only ([staging/production] markers, source policy)
docs/architecture/environments.md: environment matrix and decisions D1-D5
Not added (out of scope): DB engine/connection/schema/migrations, Redis/S3/
  SMTP clients, sessions/CSRF/auth/tenancy, CORS middleware, Docker changes
```

**Verification:**

```text
Backend: 139 pytest tests pass (rule matrix per environment with passing and
  failing cases; secret masking in errors/repr/JSON/logs; .env ignored in
  test/staging/production; template <-> Settings consistency). Mutation
  check: disabling the .env policy makes the isolation tests fail.
Frontend: 18 vitest tests pass; a temporary Client Component importing
  env.ts fails `next build` ("depends on server-only"); a temporary Server
  Component import builds. Both probes deleted.
pnpm check:env: passes on the repo; fails for all 8 defect fixtures (tracked
  .env and .env.local, secret and URL password in a template, secret-like
  NEXT_PUBLIC_ in a template and in source, drift both ways); no values printed.
Native API, broken production env: exit 1, rules listed, 0 value leaks.
Native API, valid production env (fake values): /health 200, /docs 404,
  /openapi.json 404. Native API with zero configuration: /health 200, /docs 200.
pnpm stack:up: exit 0; api (APP_ENV=development, no .env in image) /health
  200; frontend 200. api image with APP_ENV=production and no config: exit 1.
pnpm check: PASS. Landing page SHA-256 unchanged. ACRS unchanged.
```

---

### T00-05 — CI Foundation

**Status:** `COMPLETED` (merged to `main` via PR #5, merge commit `e335502`)

**Implementation:**

```text
.github/workflows/ci.yml: PR/push to main + dispatch; ubuntu-24.04;
  contents: read; no secrets; persist-credentials: false; superseded PR
  runs cancelled. Parallel jobs calling the existing root scripts:
  repo (check:landing, check:env, actionlint), frontend (frozen install,
  format, lint, typecheck, tests, build), backend (uv sync --locked,
  check:lock, ruff format/lint, mypy, pytest), secrets (gitleaks full
  history + self-test), docker (both images built, not pushed; API smoke
  test; production fail-fast; compose config). ci-ok = single required
  status, passes only when all five jobs succeed.
.github/workflows/codeql.yml, audit.yml: reporting only (not in ci-ok)
.github/dependabot.yml: github-actions, docker, docker-compose only
  (monthly, grouped, 7-day cooldown, no majors, holds); npm/uv not enabled
.gitleaks.toml: default rules + one exact path AND exact value allowlist
scripts/ci/: install-tool.sh (pinned, SHA-256 verified), gitleaks-selftest.sh,
  docker-smoke.sh
package.json: format:check:frontend, format:check:backend, check:lock
docs/architecture/ci.md: architecture, security model, pins, Dependabot
  scope, local reproduction, future branch-protection ruleset (not applied)
Actions pinned by SHA: checkout v7.0.1, setup-node v7.0.0, setup-uv
  v10.1.0, codeql-action v4.38.1 (all released >= 7 days before pinning)
```

**Verification:**

```text
Local only (GitHub verification after push). pnpm check: PASS
  (18 frontend + 139 backend tests, next build). actionlint 1.7.12: clean
  (Linux run with shellcheck 0.9.0); shellcheck 0.10.0 on scripts/ci: clean.
  Dependabot and workflow files valid against their JSON schemas.
gitleaks 8.30.1 full history (--all): baseline 2 findings, both the
  documented fake TEST_CSRF_SECRET; with the allowlist: no leaks.
  Self-test 4/4 (detected, other value in allowlisted file detected,
  documented value elsewhere detected, documented value in its file clean).
install-tool.sh: linux-x64 and windows-x64 checksums verified against the
  downloaded archives; a corrupted expected hash aborts before extraction.
Docker: both :ci images build; smoke test /health 200 {"status":"ok"},
  HEALTHCHECK healthy; APP_ENV=production without config exits 1 with a
  value-free ConfigurationError; compose config valid (and fails without
  the required variables). Clean-clone rehearsal of every job: PASS.
pnpm audit and pip-audit 2.10.1: no known vulnerabilities.
Landing page SHA-256 unchanged. ACRS unchanged (listing comparison).
```

---

### T00-06 — Design Token Foundation

**Status:** `COMPLETED` (merged to `main` via PR #6, merge commit `0f4346b`)

**Implementation:**

```text
frontend/src/design-system/tokens/: primitives.css (DESIGN-SYSTEM.md §6-§8
  palette verbatim + documented derived mixes; only raw colours),
  semantic.css (§10 tokens + *-surface/*-text, link, focus-ring, elevation;
  Light and Dark mappings; no-JS fallback), tailwind.css (Tailwind v4
  @theme: defaults removed; semantic colour/elevation utilities; §18 type
  scale; 4px spacing; §34 radii; tablet/desktop/large breakpoints)
frontend/src/design-system/theme/: preference light|dark|system in
  localStorage "mti360.theme" (default system), pre-paint <head> script,
  ThemeProvider/useTheme (useSyncExternalStore; OS listener; cross-tab sync;
  storage-safe), ThemeSelector (fieldset + native radios)
frontend/src/design-system/typography/fonts.ts: self-hosted Inter variable
  (next/font/local; latin preloaded, latin-ext on demand)
app/layout.tsx + globals.css + neutral page.tsx wired to tokens and theme
Dependencies: tailwindcss 4.3.3, @tailwindcss/postcss 4.3.3,
  @fontsource-variable/inter 5.3.0 (no install scripts); postcss.config.mjs
Docs: design-tokens.md, ADR-0007, INC-12 decided, INC-17 recorded
```

**Verification:**

```text
pnpm check: PASS (frontend 193 tests: palette fidelity, derivations,
  Light/Dark parity, fallback == Dark, primitives-only references, Tailwind
  mapping/reset, WCAG 2.2 AA contrast in both themes, guard, theme runtime,
  pre-paint matrix, selector; backend 139). Guard negative check: planted
  raw colour, dark: utility and raw semantic value all fail the tests.
Built CSS: MTI 360 utilities only (no Tailwind default palette, sizes,
  radii, breakpoints); Inter latin + latin-ext emitted locally.
next start + curl: pre-paint script in <head>, font preload, no external
  or font-CDN URLs; fonts served 200 font/woff2.
Docker: frontend :ci image builds and runs healthy (hardened); API smoke
  test (docker-smoke.sh) passes.
Headless Chromium 1.63 (production image): 68/68 checks - Light and Dark
  at 390/768/1024/1440 (token backgrounds, Inter, no overflow, no console
  or hydration warnings, no external requests); pre-paint with app JS
  blocked; no-JS OS fallback; live System change; keyboard Tab + arrow with
  visible focus; cross-tab sync; reload without flash. Screenshots kept in
  the local scratchpad only.
Clean-clone frontend job rehearsal, gitleaks full history: PASS.
Landing page SHA-256 unchanged. ACRS unchanged (listing comparison).
```

---

### T00-07 — Core Component Library

**Status:** `COMPLETED` — **07A** merged to `main` via PR #7 (merge commit `8a370a4`); **07B** (forms) via PR #8 (`1b8740c`); **07C** (overlays, data, interaction controls) via PR #9 (`e69603e`). ChartCard and PermissionGate/AccessDenied are deferred (INC-19, INC-18).

**Implementation (07C):**

```text
Overlay infrastructure: shared surfaces (overlay.ts) and PanelDialog layout;
  07B Select/Combobox/DatePicker popovers use the shared surface (styling only)
Overlays: Dialog (Modal; sm/md/lg/xl), AlertDialog (Cancel focused, scrim
  does not dismiss), Popover, Tooltip, Drawer (left/right/top/bottom),
  DropdownMenu, ContextMenu (right-click, Shift+F10, ContextMenu key), Toast
  (React Aria UNSTABLE_Toast* behind the MTI 360 API; error/action toasts
  persist)
Data: DataTable (typed, controlled; sorting, single/multiple selection with
  indeterminate select-all, row actions, loading/empty/error, scroll or card
  layout on mobile), Pagination (en-IN numbers, page size, compact mobile)
Interaction controls: FilterBar (mobile bottom Drawer), Search, RadioGroup,
  Switch, TimePicker (ISO "HH:mm", en-IN 12-hour, no time zones)
Showcase: 07C sections (showcase-overlays.tsx) with a showcase-only toast region
No new dependencies, no new tokens, no 07A/07B public API changes
Docs: components.md contracts (3C), INC-18/19/20 updated, INC-24, INC-25
```

**Verification (07C):**

```text
pnpm check: PASS (frontend 482 tests, backend 139). Headless Chromium on
  the production image: 343/343 (07A/07B suites + Dialog, AlertDialog,
  Drawer, menus and Toast in Light/Dark at 390/768/1024/1440 with axe 0,
  viewport containment, focus trap/restore, Escape, no overflow, no console
  or hydration errors; tooltip, context menu keyboard, DataTable sorting/
  selection/actions/states, pagination, mobile FilterBar, 44px controls,
  reduced motion). No axe exclusions added for 07C. Clean clone, gitleaks,
  Docker + API smoke: PASS. Landing page unchanged. ACRS unchanged
  (listing comparison). /design-system returns 404 with APP_ENV=production.
```


**Implementation (07B):**

```text
Field foundation: FieldLabel (* + programmatic required), FieldDescription,
  FieldErrorMessage (icon + text), FieldSuccessMessage (opt-in), shared
  control classes, Form (native validation, validationErrors for server
  errors), shared popover/option list
Components: Input, Textarea (character count), Checkbox (CheckboxField +
  CheckboxButton, indeterminate), Select, Combobox (contains or manual/async,
  loading status inside the popover), DatePicker (ISO API, en-IN DD/MM/YYYY,
  Monday-first product default + firstDayOfWeek override, min/max/
  unavailable), FileUpload (UX-only validation, deny list, no previews/object
  URLs/transport)
Showcase: form sections + Student enquiry form (simulated server errors)
No new dependencies, no new tokens, no jsdom polyfills (probe: not needed)
Docs: components.md contracts (3B), INC-20 updated, INC-22, INC-23
```

**Verification (07B):**

```text
pnpm check: PASS (frontend 396 tests, backend 139). Headless Chromium on
  the production image: 129/129 (07A suite + popovers axe in Light/Dark at
  390/1024, viewport containment, DatePicker typing/calendar/ISO/Monday
  default/Sunday override, FileUpload rejections and no object URLs, form
  first-invalid focus and server error mapping, 44px mobile controls,
  reduced motion). Clean clone, gitleaks, Docker + API smoke: PASS.
Landing page unchanged. ACRS unchanged (listing comparison).
```

**Implementation (07A):**

```text
Dependencies: react-aria-components 1.21.1, @internationalized/date 3.12.4,
  lucide-react 1.47.0; dev @testing-library/user-event 14.6.7, axe-core 4.13.0
Infrastructure: lib/cx.ts (cx, focusRing), icons/ (curated Lucide set),
  testing/axe.ts, tokens/components.css (control heights 32/40/44 with 44 px
  medium below tablet, focus ring, z-index); semantic surface-hover,
  surface-selected, brand-primary-hover, success-strong, error-strong,
  overlay-scrim (+ derived seaglass-950/400); guard extensions
Components: Button, IconButton, Card, Badge, Tabs, KPI, Timeline, Alert,
  Skeleton (+ LoadingRegion), EmptyState, ErrorState
Showcase: /design-system (development/test only, 404 otherwise, noindex)
Docs: components.md (contracts), ADR-0008, INC-18..INC-21
```

**Verification (07A):**

```text
pnpm check: PASS (frontend 305 tests incl. axe on every component, token
  contrast matrix with new tokens, guards with detector fixtures, showcase
  gate matrix; backend 139). Guard negative check: planted arbitrary value,
  lucide/React Aria imports and raw HTML all fail.
Headless Chromium 1.63 on the production image (APP_ENV=test): 70/70 -
  Light and Dark at 390/768/1024/1440 with axe (WCAG 2.2 AA incl. contrast)
  0 violations, no overflow, no console warnings, no external requests;
  keyboard activation, focus ring in the token colour, tabs keyboard model,
  pending/disabled, 44 px controls on mobile, reduced motion, neutral page
  regression; APP_ENV=production: /design-system 404.
Clean clone, gitleaks, Docker build + API smoke: PASS. Landing page
  unchanged. ACRS unchanged (listing comparison).
```

---

### T00-08 — Application Shell

**Status:** `COMPLETED` (reviewed; merged to `main` via PR #10 with a merge commit, `4a47f98`, 2026-09-28)

**Implementation:**

```text
Shell (frontend/src/shells/, contracts: docs/architecture/application-shell.md):
  ApplicationShell, AppHeader, AppSidebar (collapsible rail / fixed),
  AppNavigation (configuration-driven, nested, badges, aria-current),
  MobileNavigation (T00-07C Drawer), Breadcrumbs, PageHeader, PageContainer /
  PageContent, SkipNavigation, UserMenu (DropdownMenu; Preferences opens the
  existing ThemeSelector), NotificationCenter (Popover; static data),
  CommandSearch (Dialog + Search; Ctrl+K; pages of the current experience),
  global ToastRegion mount, ShellLoading / ShellError, PublicSiteShell,
  ExperienceFrame; NavigationProvider (design-system/components/Router)
  connects React Aria links to the Next.js router
Experience framework: EXPERIENCE ids, typed configuration, registry, page
  resolution and static params (structural only: no auth, authorization or
  tenant resolution; no tenant identifier in routes)
Routes: /platform (7), /app (76), /student (10), /site (5) placeholder pages
  with layout (noindex), loading and error boundaries; other paths 404
"/" unchanged (neutral page; marketing site not integrated, INC-26);
  /design-system gate unchanged (404 in production)
No new dependencies, no new tokens, no theme-runtime or 07A/B/C API changes;
  icon module extended with shell/navigation icons
Docs: application-shell.md; INC-26, INC-27, INC-28
```

**Verification:**

```text
pnpm check: PASS (frontend 555 tests, backend 139). Headless Chromium on the
production image (APP_ENV=test and production): 394/394 — every experience in
Light and Dark at 390/768/1024/1440 (HTTP 200, one main/h1, noindex, no
overflow, axe 0 incl. contrast, no console/hydration errors, no external
requests); skip link, rail/collapse, drawer focus and Escape, menus, Preferences
theme switch + persistence, System theme, notifications, Ctrl+K search, toast,
public-site navigation, client-side links, reduced motion; / neutral page; /design-system 200 in
test and 404 in production; unknown paths 404.
```

---

### T00-09 — Responsive Foundation

**Status:** `COMPLETED` (reviewed; merged to `main` via PR #11 with a merge commit, `265a06d`)

**Implementation:**

```text
Layout primitives (frontend/src/design-system/layout/, "@/design-system/layout";
  conventions: docs/architecture/layout.md):
  responsive.ts (breakpoint vocabulary on the approved tiers, Responsive<T>,
  4px spacing scale 2xs..2xl with section gaps growing from tablet, literal
  column/span class maps), Container (narrow 48rem / standard 72rem / wide
  80rem / full; page gutter 16/24/32px), Stack, Inline (wrap or stackBelow),
  Grid / GridItem (1-6, 12 columns; spans), Section, SplitLayout (1:1, 2:1,
  3:1; DOM order = stacked order), ActionBar (primary on top on mobile,
  wrapping row from tablet), Show (CSS-only responsive visibility)
Shell integration (public APIs unchanged): PageContainer uses the shared
  widths/gutter (+ additive "narrow"); PageContent sections 24 -> 32px;
  PageHeader and Section actions via ActionBar - beside the title while it
  keeps >= 24rem, wrapped below otherwise (fixes a squeezed title at 768/1024)
Defects found in Chromium, fixed without API changes: Kpi long values spilled
  out of narrow cards (wrap-anywhere); ErrorState actions did not wrap;
  DataTable scroll-region focus ring clipped by its frame (new insetFocusRing)
Page conventions: page header/actions, dashboard, data list (FilterBar +
  DataTable), detail (SplitLayout), form (1 -> 2 columns + ActionBar),
  content widths, overflow/long content, RTL readiness
Showcase: layout sections on /design-system; /design-system/layout = generic
  page inside the real shell (development/test only, 404 in production)
No new dependencies, breakpoints or tokens; responsive typography unchanged
  (page title 24 -> 32px already per DESIGN-SYSTEM.md §19). INC-29
```

**Verification:**

```text
pnpm check: PASS (frontend 609 tests, backend 139). Headless Chromium on the
production image (APP_ENV=test and production): 675/675 - the full T00-08
shell regression plus /design-system and /design-system/layout in Light and
Dark at 390/640/768/1024/1280/1440 (no page overflow, no element spilling its
box, axe 0 incl. contrast with no exclusions, no console/hydration errors, no
external requests), breakpoint edges 767/768, 1023/1024, 1439/1440, layout
geometry per width, 44px targets, FilterBar drawer, table scroll region,
keyboard order and unclipped focus ring, reduced motion, System theme,
element-level spill on every experience; /design-system/layout 404 in
production. gitleaks (full history): no leaks. API image smoke: PASS.
Compose config: valid.
```

---

### T00-10 — Accessibility Foundation

**Status:** `COMPLETED` (reviewed; merged to `main` via PR #12, `94cb752`). INC-24 was resolved by T00-10A.

**Implementation:**

```text
Contract: docs/architecture/accessibility.md (WCAG 2.2 AA; keyboard, focus,
  names, forms, live regions, overlays, tables, motion, contrast, landmarks,
  headings, links vs buttons, touch targets, testing, screen checklist,
  known exceptions)
Foundation: app/globals.css :focus-visible token fallback + reduced-motion
  safety net; design-system/testing/a11y.ts (expectNamedControls,
  tabSequence, expectFocusContained, expectFocusRing, expectHeadingOutline);
  guards: outline-none only with a replacement or "a11y-focus:"
  justification, every transition/animation paired with a reduced-motion
  variant, no positive tabIndex
Verified defects fixed (public APIs unchanged): Pagination focus lost to
  <body> at first/last page; Tabs focus ring clipped by the scrolling list
  (insetFocusRing); Popover Dismiss buttons outside the dialog (axe region)
  and focus not contained (popover is now the dialog); FileUpload drop zone
  named "DropZone"; DataTable/Search status regions mounted with their text
  (now persistent; DataTable announces error/empty); Toast region not
  reachable with F6 (landmark never registered); Breadcrumb links 24px on
  mobile (now 44px)
Tests: cross-component contract (components/accessibility.test.tsx), shell
  accessibility for all experiences (ShellAccessibility.test.tsx), page-level
  names and heading outline, brand-primary non-text contrast, INC-24 pairs
  pinned
No new dependencies, tokens, breakpoints or ADRs; no backend/infra changes
Remaining exceptions: Combobox axe rules while open (React Aria, documented,
  no repository exclusion); INC-24 Dark state text on elevated surfaces
  (token decision needed); 32px sm/in-field controls (>= 24px, WCAG 2.5.8)
```

**Verification:**

```text
pnpm check: PASS (frontend 684 tests, backend 139). Headless Chromium on the
production image (APP_ENV=test and production): 1386/1386 - the full T00-08
and T00-09 suites plus: keyboard walk of every focus stop on all experiences,
/design-system and /design-system/layout in Light and Dark at
390/768/1024/1440 (visible token ring, ring contrast >= 3:1, never clipped,
never in hidden content, 44px mobile targets, axe 0 incl. contrast, no console
errors); overlay matrix (Dialog, AlertDialog x2, Drawers, Popovers, menus:
focus entry, name, axe while open, containment, Home/End, Escape, focus
return) at 390/1024 in both themes; context menu, Select, calendar, time
segments; Combobox exception limited to its 4 documented rules while open and
axe 0 once closed; Pagination focus; Tabs keyboard and inset ring; form
first-invalid focus + error association; toast region F6 and keyboard
dismissal; reduced motion; System theme; /design-system and
/design-system/layout 404 in production. gitleaks (full history): no leaks.
API image smoke: PASS. Compose config: valid.
```

---

### T00-10A — Accessibility Token Correction (INC-24)

**Status:** `COMPLETED` (reviewed; merged to `main` via PR #13, `9f00b2e`)

**Implementation:**

```text
Measured: Dark *-text (= *-400) on surface-elevated/surface-hover: error
  3.79, info 4.03, success 4.19, warning 4.22; on surface-selected 4.00-4.45
Tokens (approved narrow exception): 4 derived primitives, documented mix
  formula, no palette change: success-300 #6DB096 mix(success-600, ice-100,
  0.62), warning-300 #C59B5B (0.72), error-300 #D59293 (0.56), info-300
  #79AAC8 (0.58); Dark success/warning/error/info-text -> *-300 (Dark block
  + no-JS fallback). Unchanged: every existing primitive, Light mappings,
  Dark indicators and success/error-strong fills (*-400)
Result: Dark *-text on surface-elevated: error 4.72, info 4.74, success
  4.68, warning 4.63; surface-selected 4.89-5.00; other surfaces >= 5.52
Tests: design-system/testing/contrast.ts (shared parsing + expectContrast);
  tokens.test.ts state text x every surface (Light/Dark, no exceptions) +
  mapping pins; components/state-text.test.tsx (rendered pairs: field
  error/success, Switch error, Alert, ErrorState, Toast, destructive menu
  item; Dialog, AlertDialog, Drawer, Popover; Light/Dark; axe)
Showcase (development/test only): "Validation in overlays" fixture
No new dependencies, component APIs, layouts, breakpoints or ADRs; no
  backend/infra changes
```

**Verification:**

```text
pnpm check: PASS (frontend 783 tests, backend 139). Headless Chromium on the
production image (APP_ENV=test and production): 1722/1722 - the full T00-08,
T00-09 and T00-10 suites plus 336 T00-10A checks: state text inside the
validation Dialog, Drawer and Popover in Light, Dark, System (OS dark) and
System (OS light) at 390/768/1024/1440 (computed colour vs effective
background >= 4.5:1; measured Dark minimum error-text 4.72, success-text
4.68 on surface-elevated, info/warning-text 5.57/5.55 on their surfaces;
axe 0 incl. color-contrast, no overflow, Escape + focus return). Combobox
exception unchanged. gitleaks (full history): no leaks. API image smoke:
PASS. Compose config: valid.
```

---

# 9. PHASE 01 — AUTHENTICATION & MULTI-TENANCY

## Phase Status

```text
IN_PROGRESS
```

## Phase Completion

```text
4 / 11 tasks completed (T01-00 … T01-03 COMPLETED; T01-04 READY_FOR_REVIEW)
```

Re-sequenced by T01-00 (decision D1; the mapping from the previous IDs is in TASKS.md, Phase 01).

| Task | Description | Status |
|---|---|---|
| T01-00 | Architecture Review | `COMPLETED` (approved 2026-09-30) |
| T01-01 | Backend, Database & API Foundation | `COMPLETED` (PR #14, `42bc8b1`) |
| T01-02 | Audit Foundation | `COMPLETED` (PR #16, `91d0180`) |
| T01-03 | Tenancy Core | `COMPLETED` (PR #19, `f602631`) |
| T01-04 | Tenant Identity & Authentication | `READY_FOR_REVIEW` (branch `feat/T01-04-identity-authentication`; not pushed) |
| T01-05 | Authorization & RBAC | `NOT_STARTED` |
| T01-06 | Platform Identity & MFA | `NOT_STARTED` |
| T01-07 | Platform Administration Foundation (API) | `NOT_STARTED` |
| T01-08 | Tenant Administration Foundation (API) | `NOT_STARTED` |
| T01-09 | Frontend Authentication & Session Integration | `NOT_STARTED` |
| T01-10 | Security Verification Gate | `NOT_STARTED` |

### T01-01 — Backend, Database & API Foundation

**Status:** `COMPLETED` (merged to `main` by PR #14, merge commit `42bc8b1`; CI verified)

**Implementation:**

```text
Dependencies (D4): sqlalchemy[asyncio] 2.0.54, asyncpg 0.31.0, alembic 1.20.0;
  dev import-linter 2.15 (Python 3.14 wheels, 7-day cooldown)
Database: UUIDv7 ids; Base + naming convention; UUIDPrimaryKey, Timestamp
  (timestamptz), Versioned (optimistic lock -> 409) mixins; app-role engine;
  DbSession = one transaction per request, SET LOCAL app.realm/request_id/
  tenant_id/user_id, committed BEFORE the response (scope=function), rolled
  back on error
Migrations: Alembic (owner role, model discovery, runtime role names for
  grants); baseline 0001 revokes runtime write access to alembic_version;
  pnpm db:migrate / db:check; compose "migrate" one-shot (only service with
  owner credentials); database/init/02-test-database.sh (mti360_test)
API: RequestContext; realm routers /api/v1/platform, /api/v1, /student,
  /public, /webhooks with guards run first; deny by default (401) until
  T01-04/T01-06; envelope {data, meta} / {error: {code, message, details,
  request_id}}; RequestModel extra=forbid; offset pagination + allow-listed
  sort; operationId <realm>_<tag>_<function>
Operations: JSON logs with redaction, request_id, no query strings; uvicorn
  access log off; X-Request-ID; no-store + nosniff on /api
Architecture: import-linter layers main -> api -> modules -> integrations
  -> core; ADR-0010 (sessions, identity/credential split - D14 amended),
  ADR-0011 (RBAC), ADR-0012 (encryption); backend-foundation.md incl.
  post-commit side-effect semantics (D10 amended)
No authentication, tenant, user or business tables; no frontend changes
```

**Verification:**

```text
Backend 219 tests (was 139): unit, API conventions, security (realm guards,
route-coverage meta-test over effective routes) and 11 PostgreSQL
integration tests (migrations up/down/check, role privileges, commit/
rollback, commit-before-response, SET LOCAL isolation, mixins). Without the
TEST_*_DATABASE_URL variables: 208 passed, 11 skipped. ruff, ruff format,
mypy (strict), import-linter: pass. Mutation checks: the default FastAPI
dependency scope fails the commit-ordering test; a core -> api import breaks
the layer contract. actionlint: pass. See the development log for the full
gate list.
```

### T01-02 — Audit Foundation

**Status:** `COMPLETED` (merged to `main` by PR #16, merge commit `91d0180`)

**Implementation:**

```text
Database: migration 0002 audit_events (UUIDv7 id, request_id, realm,
  tenant_id NULL without FK, principal_id, category security|admin|
  data_access|domain, event_type, target_type/target_id, JSONB metadata,
  created_at); check constraints; 3 indexes; mti_app SELECT/INSERT only,
  mti_readonly none; triggers reject UPDATE/DELETE/TRUNCATE for every role;
  first RLS policies (platform reads all, tenant reads own tenant, INSERT
  bound to trusted tenant and realm); mti_app stays NOBYPASSRLS
Code: app/core/audit (events, metadata, models, writer, security);
  write_audit_event in the request transaction; record_security_event
  buffers per request, the realm guard (function-scoped yield dependency)
  flushes after DbSession has released its connection and before the
  response, via context_transaction (core/db/session.py); flush failure
  logged (request ID, realm, count, exception class) and swallowed
Docs: ADR-0013, backend-foundation.md §12, security.md §11, tenancy.md,
  INC-35
No authentication, tenants, users, producers, outbox, queue or retry
```

**Verification:**

```text
Backend 307 tests (was 222): 49 PostgreSQL integration tests (was 11) run
with REQUIRE_DATABASE_TESTS=1 - schema, constraints, privileges,
append-only (app role and owner), RLS read/insert matrix, migration
down/up without orphans, writer commit/rollback/failure, security-event
flush on a one-connection pool, flush failure logging. Without the
database variables: 258 passed, 49 skipped. ruff, ruff format, mypy
(strict), import-linter (2 kept): pass. Negative control: a request-scoped
DbSession makes the flush time out on the one-connection pool and fails the
lifecycle tests.
```

### T01-03 — Tenancy Core

**Status:** `COMPLETED` (merged to `main` by PR #19, merge commit `f602631`)

**Implementation:**

```text
Database: migration 0003 - tenants (UUIDv7 id, name, status CHECK on the 8
  lifecycle states, timestamps, version) and campuses (TenantScopedMixin,
  name, required upper-case code unique per tenant, UNIQUE (tenant_id, id),
  FK to tenants ON DELETE RESTRICT); mti_app SELECT/INSERT/UPDATE (no
  DELETE), mti_readonly SELECT; RLS enabled (not forced): campuses
  realm-agnostic tenant_id = app.tenant_id (ALL, USING + WITH CHECK),
  tenants realm-aware (platform/system read all and write, any other
  context reads its own row only); roles unchanged, NOBYPASSRLS
Code: app/core/tenancy - TenantScopedMixin, tenant_foreign_key(), ORM
  filter (do_orm_execute + with_loader_criteria, include_aliases; SELECT,
  UPDATE, DELETE; fails closed), TenantScopedRepository (select/find/get/
  list/count/add, no delete, cross-tenant = 404), system_context (SYSTEM
  realm, refused inside HTTP); context_transaction records the context in
  session.info; context_scope() binds a context outside HTTP.
  app/modules/tenants - Tenant model, TenantStatus, suspend/reactivate,
  status access policy; app/modules/institute - Campus model
Docs: ADR-0014; backend-foundation §13; tenancy, security §1a,
  repository-structure; INC-36 … INC-41 (INC-32 updated); script.py.mako
No API, authentication, users, memberships, provisioning, audit producers,
  frontend or dependency changes
```

**Verification:**

```text
Backend 410 tests (was 307): 99 PostgreSQL integration tests (was 49) with
REQUIRE_DATABASE_TESTS=1; without the database variables 311 passed, 99
skipped. New: tenancy schema/migration (17), isolation (33), unit (53).
ruff, ruff format, mypy (strict), import-linter (2 kept): pass. pnpm check
(frontend 783 tests and build included): pass. API image build + docker
smoke test: pass. Negative control: with the ORM filter disabled, 9 tests
fail (owner-role ORM isolation, bulk UPDATE/DELETE, fail-closed). CI not
run (not pushed).
```

### T01-04 — Tenant Identity & Authentication

**Status:** `READY_FOR_REVIEW` (branch `feat/T01-04-identity-authentication`, based on the frozen UI contract `30511bc` on `main` at `f602631`; not pushed)

**Implementation:**

```text
Database: migration 0004 - users, user_credentials, tenant_memberships,
  membership_campuses, user_sessions, password_reset_tokens,
  user_invitations; composite FKs (membership campus in the membership's
  tenant; session tenant among the user's memberships; session campus in
  the session tenant); mti_app SELECT/INSERT/UPDATE (no DELETE), no access
  for mti_readonly; RLS on every table (21 policies incl. tenants_member_
  read), pre-authentication lookup keys app.auth_email / app.auth_token_hash
  / app.session_token_hash matched by equality; no SECURITY DEFINER
Code: app/modules/identity (domain, tokens, passwords, lookup, models,
  repository, service, schemas, router, events, templates); core/ratelimit
  (Redis, auth: namespace, fail closed), core/net (TRUSTED_PROXY_HOPS),
  integrations/email (SMTP + fake); realm guard resolves sessions
  (Access.AUTHENTICATED / SESSION / ANONYMOUS), CSRF token and same-origin
  checks; errors SESSION_REFRESH_REQUIRED, SERVICE_UNAVAILABLE, Retry-After;
  settings APP_BASE_URL, TRUSTED_PROXY_HOPS, ARGON2_*, SMTP_TIMEOUT_SECONDS;
  middleware clears the request context after the request
Dependencies: argon2-cffi 25.1.0 (bindings 26.1.0), redis 8.1.0 (7-day
  cooldown respected); blocklist SecLists 10k (MIT, pinned commit)
Infra: compose api REDIS_URL + Mailpit; CI starts Redis (TEST_REDIS_URL)
Docs: ADR-0015, identity-authentication.md, backend-foundation §14,
  security, tenancy, environments, repository-structure, runbook,
  INC-42/INC-43
No frontend, RBAC, platform identity, MFA, provisioning or administration
```

**Verification:**

```text
Backend 538 tests (was 410): 170 PostgreSQL/Redis integration tests (was 99)
with REQUIRE_DATABASE_TESTS=1; without the database and Redis variables
368 passed, 170 skipped. New: identity schema/RLS 13, authentication API
23, session/recovery API 32, rate limiting 4, identity rules 40, email 5,
security boundaries 4, settings 6, API conventions 1. ruff, ruff format,
mypy (strict), import-linter (2 kept): pass. pnpm check (frontend 783 tests
and build included): pass. API image build + docker smoke test: pass.
Compose config: valid. gitleaks (full history + tree): no leaks. Negative
control: with the CSRF/same-origin gate disabled, 5 tests fail. CI not run
(not pushed).
```

---

# 10. PHASE 02 — PLATFORM CONTROL PLANE

## Phase Status

```text
NOT_STARTED
```

## Phase Completion

```text
0 / 23 tasks
```

| Task | Description | Status |
|---|---|---|
| T02-01 | Platform Shell | `NOT_STARTED` |
| T02-02 | Platform Login | `NOT_STARTED` |
| T02-03 | Platform Dashboard | `NOT_STARTED` |
| T02-04 | Tenant Management | `NOT_STARTED` |
| T02-05 | Tenant Lifecycle | `NOT_STARTED` |
| T02-06 | Plans & Pricing | `NOT_STARTED` |
| T02-07 | Subscription Management | `NOT_STARTED` |
| T02-08 | Usage Metering | `NOT_STARTED` |
| T02-09 | Communication Providers | `NOT_STARTED` |
| T02-10 | Platform AI | `NOT_STARTED` |
| T02-11 | Platform Integrations | `NOT_STARTED` |
| T02-12 | Provisioning Engine | `NOT_STARTED` |
| T02-13 | Background Jobs | `NOT_STARTED` |
| T02-14 | Platform Health | `NOT_STARTED` |
| T02-15 | Support | `NOT_STARTED` |
| T02-16 | Platform Notifications | `NOT_STARTED` |
| T02-17 | Feature Flags | `NOT_STARTED` |
| T02-18 | Platform Settings | `NOT_STARTED` |
| T02-19 | Platform Security | `NOT_STARTED` |
| T02-20 | Platform Analytics | `NOT_STARTED` |
| T02-21 | Platform Credentials | `NOT_STARTED` |
| T02-22 | Platform Branding / Domains | `NOT_STARTED` |
| T02-23 | Platform Administrators | `NOT_STARTED` |

---

# 11. PHASE 03 — TENANT FOUNDATION

## Phase Status

```text
NOT_STARTED
```

## Phase Completion

```text
0 / 11 tasks
```

| Task | Description | Status |
|---|---|---|
| T03-01 | Tenant Shell | `NOT_STARTED` |
| T03-02 | Institute Profile | `NOT_STARTED` |
| T03-03 | Campus Management | `NOT_STARTED` |
| T03-04 | Tenant Users | `NOT_STARTED` |
| T03-05 | Tenant Roles | `NOT_STARTED` |
| T03-06 | Tenant Integrations | `NOT_STARTED` |
| T03-07 | Tenant AI Configuration | `NOT_STARTED` |
| T03-08 | Notifications | `NOT_STARTED` |
| T03-09 | Tenant Billing | `NOT_STARTED` |
| T03-10 | Tenant Audit | `NOT_STARTED` |
| T03-11 | Tenant Settings | `NOT_STARTED` |

---

# 12. PHASE 04 — ADMISSIONS

## Phase Status

```text
NOT_STARTED
```

## Phase Completion

```text
0 / 10 tasks
```

| Task | Description | Status |
|---|---|---|
| T04-01 | Lead Foundation | `NOT_STARTED` |
| T04-02 | Lead Pipeline | `NOT_STARTED` |
| T04-03 | Counselling | `NOT_STARTED` |
| T04-04 | Applications | `NOT_STARTED` |
| T04-05 | Application Review | `NOT_STARTED` |
| T04-06 | Document Verification | `NOT_STARTED` |
| T04-07 | Admission Approval | `NOT_STARTED` |
| T04-08 | Student Creation | `NOT_STARTED` |
| T04-09 | Admissions Communication | `NOT_STARTED` |
| T04-10 | Admissions Tests | `NOT_STARTED` |

---

# 13. PHASE 05 — ACADEMICS

## Phase Status

```text
NOT_STARTED
```

## Phase Completion

```text
0 / 12 tasks
```

| Task | Description | Status |
|---|---|---|
| T05-01 | Courses | `NOT_STARTED` |
| T05-02 | Curriculum | `NOT_STARTED` |
| T05-03 | Batches | `NOT_STARTED` |
| T05-04 | Timetable | `NOT_STARTED` |
| T05-05 | Attendance | `NOT_STARTED` |
| T05-06 | Faculty | `NOT_STARTED` |
| T05-07 | Training | `NOT_STARTED` |
| T05-08 | Examinations | `NOT_STARTED` |
| T05-09 | Results | `NOT_STARTED` |
| T05-10 | Certificates | `NOT_STARTED` |
| T05-11 | Academic Reports | `NOT_STARTED` |
| T05-12 | Academic Tests | `NOT_STARTED` |

---

# 14. PHASE 06 — FINANCE

## Phase Status

```text
NOT_STARTED
```

## Phase Completion

```text
0 / 10 tasks
```

| Task | Description | Status |
|---|---|---|
| T06-01 | Finance Foundation | `NOT_STARTED` |
| T06-02 | Fee Structure | `NOT_STARTED` |
| T06-03 | Invoices | `NOT_STARTED` |
| T06-04 | Payments | `NOT_STARTED` |
| T06-05 | Outstanding | `NOT_STARTED` |
| T06-06 | Refunds | `NOT_STARTED` |
| T06-07 | Finance Reports | `NOT_STARTED` |
| T06-08 | Payment Integration | `NOT_STARTED` |
| T06-09 | Financial Security | `NOT_STARTED` |
| T06-10 | Finance Tests | `NOT_STARTED` |

---

# 15. PHASE 07 — COMPLIANCE

## Phase Status

```text
NOT_STARTED
```

## Phase Completion

```text
0 / 7 tasks
```

| Task | Description | Status |
|---|---|---|
| T07-01 | Compliance Dashboard | `NOT_STARTED` |
| T07-02 | Requirements | `NOT_STARTED` |
| T07-03 | Compliance Documents | `NOT_STARTED` |
| T07-04 | Inspections | `NOT_STARTED` |
| T07-05 | Corrective Actions | `NOT_STARTED` |
| T07-06 | Compliance Audit | `NOT_STARTED` |
| T07-07 | Compliance Notifications | `NOT_STARTED` |

---

# 16. PHASE 08 — PLACEMENT

## Phase Status

```text
NOT_STARTED
```

## Phase Completion

```text
0 / 6 tasks
```

| Task | Description | Status |
|---|---|---|
| T08-01 | Placement Dashboard | `NOT_STARTED` |
| T08-02 | Eligible Students | `NOT_STARTED` |
| T08-03 | Companies | `NOT_STARTED` |
| T08-04 | Opportunities | `NOT_STARTED` |
| T08-05 | Placement Tracking | `NOT_STARTED` |
| T08-06 | Alumni | `NOT_STARTED` |

---

# 17. PHASE 09 — COMMUNICATION

## Phase Status

```text
NOT_STARTED
```

## Phase Completion

```text
0 / 11 tasks
```

| Task | Description | Status |
|---|---|---|
| T09-01 | Communication Foundation | `NOT_STARTED` |
| T09-02 | WhatsApp | `NOT_STARTED` |
| T09-03 | Email | `NOT_STARTED` |
| T09-04 | SMS | `NOT_STARTED` |
| T09-05 | Voice | `NOT_STARTED` |
| T09-06 | Conversation Workspace | `NOT_STARTED` |
| T09-07 | Contacts | `NOT_STARTED` |
| T09-08 | Templates | `NOT_STARTED` |
| T09-09 | Broadcasts | `NOT_STARTED` |
| T09-10 | Communication Analytics | `NOT_STARTED` |
| T09-11 | Provider Abstraction | `NOT_STARTED` |

---

# 18. PHASE 10 — AUTOMATION

## Phase Status

```text
NOT_STARTED
```

## Phase Completion

```text
0 / 7 tasks
```

| Task | Description | Status |
|---|---|---|
| T10-01 | Workflow Model | `NOT_STARTED` |
| T10-02 | Workflow List | `NOT_STARTED` |
| T10-03 | Workflow Builder | `NOT_STARTED` |
| T10-04 | AI Agents | `NOT_STARTED` |
| T10-05 | Executions | `NOT_STARTED` |
| T10-06 | Automation Security | `NOT_STARTED` |
| T10-07 | Automation Reliability | `NOT_STARTED` |

---

# 19. PHASE 11 — AI

## Phase Status

```text
NOT_STARTED
```

## Phase Completion

```text
0 / 12 tasks
```

| Task | Description | Status |
|---|---|---|
| T11-01 | AI Foundation | `NOT_STARTED` |
| T11-02 | AI Assistant | `NOT_STARTED` |
| T11-03 | AI Resolution | `NOT_STARTED` |
| T11-04 | Knowledge | `NOT_STARTED` |
| T11-05 | AI Analytics | `NOT_STARTED` |
| T11-06 | SQL/Data Agent | `NOT_STARTED` |
| T11-07 | AI Execution | `NOT_STARTED` |
| T11-08 | AI Configuration | `NOT_STARTED` |
| T11-09 | AI Guardrails | `NOT_STARTED` |
| T11-10 | AI Human Approval | `NOT_STARTED` |
| T11-11 | AI Failure Handling | `NOT_STARTED` |
| T11-12 | AI Security Tests | `NOT_STARTED` |

---

# 20. PHASE 12 — ANALYTICS

## Phase Status

```text
NOT_STARTED
```

## Phase Completion

```text
0 / 7 tasks
```

| Task | Description | Status |
|---|---|---|
| T12-01 | Executive Analytics | `NOT_STARTED` |
| T12-02 | Admissions Analytics | `NOT_STARTED` |
| T12-03 | Finance Analytics | `NOT_STARTED` |
| T12-04 | Academic Analytics | `NOT_STARTED` |
| T12-05 | Marketing Analytics | `NOT_STARTED` |
| T12-06 | AI Analytics | `NOT_STARTED` |
| T12-07 | Analytics Security | `NOT_STARTED` |

---

# 21. PHASE 13 — STUDENT PORTAL

## Phase Status

```text
NOT_STARTED
```

## Phase Completion

```text
0 / 11 tasks
```

| Task | Description | Status |
|---|---|---|
| T13-01 | Student Authentication | `NOT_STARTED` |
| T13-02 | Student Dashboard | `NOT_STARTED` |
| T13-03 | My Course | `NOT_STARTED` |
| T13-04 | Attendance | `NOT_STARTED` |
| T13-05 | Training | `NOT_STARTED` |
| T13-06 | Examinations | `NOT_STARTED` |
| T13-07 | Fees | `NOT_STARTED` |
| T13-08 | Certificates | `NOT_STARTED` |
| T13-09 | Placement | `NOT_STARTED` |
| T13-10 | Profile | `NOT_STARTED` |
| T13-11 | Student Security | `NOT_STARTED` |

---

# 22. PHASE 14 — PUBLIC WEBSITE

## Phase Status

```text
NOT_STARTED
```

## Phase Completion

```text
0 / 7 tasks
```

| Task | Description | Status |
|---|---|---|
| T14-01 | Public Website Foundation | `NOT_STARTED` |
| T14-02 | Home | `NOT_STARTED` |
| T14-03 | Features | `NOT_STARTED` |
| T14-04 | Solutions | `NOT_STARTED` |
| T14-05 | Pricing | `NOT_STARTED` |
| T14-06 | Request Demo | `NOT_STARTED` |
| T14-07 | Contact | `NOT_STARTED` |

---

# 23. PHASE 15 — SAAS BILLING & OPERATIONS

## Phase Status

```text
NOT_STARTED
```

## Phase Completion

```text
0 / 6 tasks
```

| Task | Description | Status |
|---|---|---|
| T15-01 | Subscription Enforcement | `NOT_STARTED` |
| T15-02 | Usage Limits | `NOT_STARTED` |
| T15-03 | Billing Reconciliation | `NOT_STARTED` |
| T15-04 | Failed Payment Handling | `NOT_STARTED` |
| T15-05 | Tenant Provisioning Reliability | `NOT_STARTED` |
| T15-06 | Platform Operational Monitoring | `NOT_STARTED` |

---

# 24. PHASE 16 — SECURITY & HARDENING

## Phase Status

```text
NOT_STARTED
```

## Phase Completion

```text
0 / 12 tasks
```

| Task | Description | Status |
|---|---|---|
| T16-01 | Authentication Security Review | `NOT_STARTED` |
| T16-02 | Authorization Review | `NOT_STARTED` |
| T16-03 | Tenant Isolation Review | `NOT_STARTED` |
| T16-04 | API Security Review | `NOT_STARTED` |
| T16-05 | Database Security Review | `NOT_STARTED` |
| T16-06 | File Security Review | `NOT_STARTED` |
| T16-07 | AI Security Review | `NOT_STARTED` |
| T16-08 | Communication Security | `NOT_STARTED` |
| T16-09 | Audit Review | `NOT_STARTED` |
| T16-10 | Dependency Security | `NOT_STARTED` |
| T16-11 | Performance Review | `NOT_STARTED` |
| T16-12 | Accessibility Review | `NOT_STARTED` |

---

# 25. PHASE 17 — PRODUCTION READINESS

## Phase Status

```text
NOT_STARTED
```

## Phase Completion

```text
0 / 13 tasks
```

| Task | Description | Status |
|---|---|---|
| T17-01 | Production Environment | `NOT_STARTED` |
| T17-02 | Database Migration Process | `NOT_STARTED` |
| T17-03 | Backup & Restore | `NOT_STARTED` |
| T17-04 | Monitoring | `NOT_STARTED` |
| T17-05 | Logging | `NOT_STARTED` |
| T17-06 | Alerting | `NOT_STARTED` |
| T17-07 | Disaster Recovery | `NOT_STARTED` |
| T17-08 | Production Smoke Tests | `NOT_STARTED` |
| T17-09 | Security Smoke Tests | `NOT_STARTED` |
| T17-10 | Production Performance Test | `NOT_STARTED` |
| T17-11 | Production UI Review | `NOT_STARTED` |
| T17-12 | Documentation Review | `NOT_STARTED` |
| T17-13 | Release Checklist | `NOT_STARTED` |

---

# 26. CROSS-CUTTING STATUS

| Area | Status | Notes |
|---|---|---|
| Design System | `NOT_STARTED` | Tokens/components pending implementation |
| Accessibility | `NOT_STARTED` | Foundation pending |
| Authentication | `NOT_STARTED` | Phase 01 |
| Authorization | `NOT_STARTED` | Phase 01 |
| Multi-Tenancy | `NOT_STARTED` | Phase 01 |
| Tenant Isolation | `NOT_STARTED` | Phase 01 |
| Audit | `NOT_STARTED` | Foundation pending |
| Observability | `NOT_STARTED` | Production phase |
| AI Guardrails | `NOT_STARTED` | Phase 11 |
| SQL Agent Security | `NOT_STARTED` | Phase 11 |
| Communication Security | `NOT_STARTED` | Phase 09 |
| Billing Security | `NOT_STARTED` | Phase 15 |
| Backup / Restore | `NOT_STARTED` | Phase 17 |

---

# 27. UI IMPLEMENTATION STATUS

## Platform Control Plane

```text
0 / 53 screens implemented
```

Status:

```text
NOT_STARTED
```

---

## Tenant Application

```text
0 / approximately 153 screens implemented
```

Status:

```text
NOT_STARTED
```

---

## Student Portal

```text
0 / 10 screens implemented
```

Status:

```text
NOT_STARTED
```

---

## Public Website

```text
0 / 6 screens implemented
```

Status:

```text
NOT_STARTED
```

---

## Total

```text
0 / approximately 222 screens implemented
```

### Important

Screen count is a planning metric only.

It must NOT be used as the sole measure of project completion.

A screen is only considered implemented when its required underlying behavior is also implemented.

---

# 28. PAGE TEMPLATE STATUS

| Template | Status |
|---|---|
| T01 Dashboard | `NOT_STARTED` |
| T02 Data List | `NOT_STARTED` |
| T03 Detail | `NOT_STARTED` |
| T04 Form | `NOT_STARTED` |
| T05 Wizard | `NOT_STARTED` |
| T06 Kanban | `NOT_STARTED` |
| T07 Calendar | `NOT_STARTED` |
| T08 Communication Workspace | `NOT_STARTED` |
| T09 AI Workspace | `NOT_STARTED` |
| T10 Analytics | `NOT_STARTED` |
| T11 Workflow Builder | `NOT_STARTED` |
| T12 Tenant 360 | `NOT_STARTED` |
| T13 Platform Operations | `NOT_STARTED` |
| T14 Support Workspace | `NOT_STARTED` |
| T15 Settings | `NOT_STARTED` |
| T16 Authentication | `NOT_STARTED` |
| T17 Student Portal | `NOT_STARTED` |
| T18 Public Website | `NOT_STARTED` |

---

# 29. COMPONENT LIBRARY STATUS

## Core Components

| Component | Status |
|---|---|
| AppShell | `COMPLETED` (T00-08, PR #10, `ApplicationShell`; INC-28) |
| Sidebar | `COMPLETED` (T00-08, PR #10, `AppSidebar` + `AppNavigation`) |
| TopBar | `COMPLETED` (T00-08, PR #10, `AppHeader`) |
| PageHeader | `COMPLETED` (T00-08, PR #10; responsive actions T00-09, PR #11) |
| Breadcrumb | `COMPLETED` (T00-08, PR #10, `Breadcrumbs`) |
| GlobalSearch | `COMPLETED` (T00-08, PR #10, `CommandSearch`; entry point only) |
| TenantContext | `NOT_STARTED` (needs authentication and tenancy) |
| CampusSwitcher | `NOT_STARTED` (needs authentication and tenancy) |
| NotificationCenter | `COMPLETED` (T00-08, PR #10; static data) |
| UserMenu | `COMPLETED` (T00-08, PR #10; no authentication) |
| Button | `COMPLETED` (T00-07A, PR #7) |
| IconButton | `COMPLETED` (T00-07A, PR #7) |
| Input | `COMPLETED` (T00-07B, PR #8) |
| Select | `COMPLETED` (T00-07B, PR #8) |
| Combobox | `COMPLETED` (T00-07B, PR #8) |
| DatePicker | `COMPLETED` (T00-07B, PR #8) |
| FileUpload | `COMPLETED` (T00-07B, PR #8) |
| Tabs | `COMPLETED` (T00-07A, PR #7) |
| Card | `COMPLETED` (T00-07A, PR #7) |
| Badge | `COMPLETED` (T00-07A, PR #7) |
| DataTable | `COMPLETED` (T00-07C, PR #9) |
| FilterBar | `COMPLETED` (T00-07C, PR #9) |
| Pagination | `COMPLETED` (T00-07C, PR #9) |
| Drawer | `COMPLETED` (T00-07C, PR #9) |
| Modal | `COMPLETED` (T00-07C, PR #9, `Dialog`) |
| Dialog | `COMPLETED` (T00-07C, PR #9, `AlertDialog`; INC-18) |
| Toast | `COMPLETED` (T00-07C, PR #9) |
| Alert | `COMPLETED` (T00-07A, PR #7) |
| Timeline | `COMPLETED` (T00-07A, PR #7) |
| KPI | `COMPLETED` (T00-07A, PR #7) |
| ChartCard | `NOT_STARTED` (deferred from 07C, INC-19) |
| EmptyState | `COMPLETED` (T00-07A, PR #7) |
| ErrorState | `COMPLETED` (T00-07A, PR #7) |
| Skeleton | `COMPLETED` (T00-07A, PR #7) |
| PermissionGate | `NOT_STARTED` |

Also implemented outside this list: Textarea and Checkbox (T00-07B, PR #8); Popover, Tooltip, DropdownMenu, ContextMenu, Search, RadioGroup, Switch and TimePicker (T00-07C, PR #9). T00-08 also adds PageContainer/PageContent, SkipNavigation, MobileNavigation, ShellLoading/ShellError and PublicSiteShell (`COMPLETED`, PR #10). T00-09 adds the layout primitives Container, Stack, Inline, Grid/GridItem, Section, SplitLayout, ActionBar and Show (`COMPLETED`, PR #11; docs/architecture/layout.md). T00-10 hardens the library for WCAG 2.2 AA without API changes; the accessibility contract, test helpers and guards are `READY_FOR_REVIEW` (docs/architecture/accessibility.md).

---

# 30. ENTERPRISE COMPONENT STATUS

| Component | Status |
|---|---|
| TenantHealthCard | `NOT_STARTED` |
| SubscriptionCard | `NOT_STARTED` |
| UsageMeter | `NOT_STARTED` |
| RevenueCard | `NOT_STARTED` |
| PlatformHealthCard | `NOT_STARTED` |
| IncidentCard | `NOT_STARTED` |
| SupportSessionBanner | `NOT_STARTED` |
| AuditTimeline | `NOT_STARTED` |
| ProvisioningProgress | `NOT_STARTED` |
| SystemStatus | `NOT_STARTED` |

---

# 31. TENANT COMPONENT STATUS

| Component | Status |
|---|---|
| AdmissionFunnel | `NOT_STARTED` |
| StudentCard | `NOT_STARTED` |
| CourseCard | `NOT_STARTED` |
| BatchCard | `NOT_STARTED` |
| TrainingProgress | `NOT_STARTED` |
| AttendanceSummary | `NOT_STARTED` |
| FeeSummary | `NOT_STARTED` |
| ComplianceSummary | `NOT_STARTED` |
| PlacementPipeline | `NOT_STARTED` |

---

# 32. AI COMPONENT STATUS

| Component | Status |
|---|---|
| AIAssistant | `NOT_STARTED` |
| AISuggestion | `NOT_STARTED` |
| AIAction | `NOT_STARTED` |
| AIExecution | `NOT_STARTED` |
| AISource | `NOT_STARTED` |
| AIConfidence | `NOT_STARTED` |
| AIApproval | `NOT_STARTED` |

---

# 33. ARCHITECTURE READINESS

| Area | Status |
|---|---|
| Product Definition | `READY` |
| Application Flow | `READY` |
| Architecture Specification | `READY` |
| Platform Control Plane Specification | `READY` |
| Design System | `READY` |
| Screen Inventory | `READY` |
| Claude Development Rules | `READY` |
| Task Roadmap | `READY` |
| Development Tracking | `READY` |
| Repository Structure (T00-01) | `COMPLETED` |
| Development Toolchain (T00-02) | `COMPLETED` |
| Local Docker Infrastructure (T00-03) | `COMPLETED` |
| Environment Configuration (T00-04) | `COMPLETED` |
| CI Foundation (T00-05) | `COMPLETED` |
| Design Token Foundation (T00-06) | `COMPLETED` |
| Core Component Library (T00-07) | `COMPLETED` (PR #7, PR #8, PR #9) |
| Application Shell (T00-08) | `COMPLETED` (PR #10) |
| Responsive Layout Foundation (T00-09) | `COMPLETED` (PR #11) |
| Accessibility Foundation (T00-10) | `COMPLETED` (PR #12) |
| Accessibility Token Correction (T00-10A) | `COMPLETED` (PR #13) |
| Architecture Review (T01-00) | `COMPLETED` (approved; D1–D22) |
| Backend, Database & API Foundation (T01-01) | `READY_FOR_REVIEW` |
| Architecture Decision Records | `READY_FOR_REVIEW` (ADR-0001 … ADR-0006) |
| Production Implementation | `NOT_STARTED` |

---

# 34. CURRENT BLOCKERS

## Blocker 1

```text
None
```

---

# 35. CURRENT RISKS

The following should be monitored during implementation.

### RISK-01 — Scope Size

MTI 360 contains a large number of functional areas and screens.

**Mitigation:**

Use vertical slices and reusable components.

---

### RISK-02 — Multi-Tenant Security

Cross-tenant leakage would be a critical platform failure.

**Mitigation:**

Treat tenant isolation as a foundational architecture and continuously test it.

---

### RISK-03 — UI Duplication

Large screen count may lead to duplicated components.

**Mitigation:**

Use page templates and shared component library.

---

### RISK-04 — AI Overreach

AI functionality can introduce security and data-boundary risks.

**Mitigation:**

Use explicit tools, permissions, tenant context, approvals and execution auditing.

---

### RISK-05 — Architecture Drift

Implementation may diverge from specification as development progresses.

**Mitigation:**

Keep specification documents version controlled and update them when architectural decisions change.

---

### RISK-06 — Premature Feature Development

Building advanced AI/analytics before core workflows are stable can increase complexity.

**Mitigation:**

Follow the phase dependencies.

---

### RISK-07 — Production Readiness Gap

A working development environment does not automatically mean production readiness.

**Mitigation:**

Maintain a dedicated Phase 16 and Phase 17 hardening/release cycle.

---

# 36. CURRENT DECISIONS

The following decisions are currently established.

### DEC-001 — True Multi-Tenant SaaS

MTI 360 is a multi-tenant SaaS platform.

---

### DEC-002 — Separate Platform Control Plane

Platform administration is separate from tenant administration.

---

### DEC-003 — Four Experiences

```text
Platform
Tenant
Student
Public
```

---

### DEC-004 — Tenant Isolation

Tenant isolation is enforced server-side and is not a frontend-only feature.

---

### DEC-005 — Premium Maritime Design

MTI 360 uses a distinct premium maritime visual identity defined in `DESIGN-SYSTEM.md`.

---

### DEC-006 — Reusable UI Architecture

The product uses page templates and reusable components instead of implementing every screen independently.

---

### DEC-007 — Controlled AI

AI actions are permission-aware, tenant-scoped and auditable.

---

### DEC-008 — SQL/Data Agent

The SQL/Data Agent is read-only by default.

---

### DEC-009 — Vertical Slice Development

Major features should be implemented end-to-end rather than as disconnected UI-only modules.

---

### DEC-010 — Technology Stack Confirmed

Next.js + React + TypeScript; Python + FastAPI; PostgreSQL + SQLAlchemy + Alembic; Redis; S3-compatible storage; Docker Compose (T00-03); modular monolith. See `docs/adr/0001-stack.md`.

---

### DEC-011 — Monorepo Layout

Single monorepo; specifications stay at the root; migrations in `backend/migrations/`; one Next.js app for four experiences. See `docs/adr/0002-monorepo-layout.md`.

---

### DEC-012 — Marketing Website ≠ Tenant Public Website

The root landing page is the MTI 360 marketing website, not the Tenant Public Website and not part of the application. See `docs/adr/0003-marketing-vs-tenant-public-website.md`.

---

### DEC-013 — Tenant Isolation Layers

Server-side context, tenant-scoped repositories, automatic ORM filter, PostgreSQL RLS and composite foreign keys, with a mandatory cross-tenant test gate. See `docs/adr/0004-tenant-isolation.md`.

---

### DEC-014 — Identity and Session Realms

Separate platform identity; opaque server-side sessions; realm-specific cookies; explicit, audited support sessions. See `docs/adr/0005-identity-and-session-realms.md`.

---

### DEC-015 — API Prefixes

`/api/v1/platform/*`, `/api/v1/*` (tenant), `/api/v1/student/*`, `/api/v1/public/*`, `/api/v1/webhooks/*`. See `docs/adr/0006-api-prefixes.md`.

---

### DEC-016 — Local Infrastructure (T00-03)

Hybrid development (infrastructure in Docker, apps native). PostgreSQL 18 via `pgvector/pgvector:0.8.6-pg18-trixie` (pgvector not enabled), Redis 8.8, SeaweedFS 4.47 as the S3-compatible emulator (MinIO community edition archived), Mailpit 1.31. Compose project `mti360`, volumes `mti360_*`, ports on `127.0.0.1`. See `docs/runbooks/local-development.md`.

---

### DEC-017 — Migrate and Worker Deferred (T00-03 D4)

The Alembic `migrate` service and the background `worker` (with the queue-library choice ADR-0001 placed in T00-03) are added by the first tasks that need them.

---

### DEC-018 — Environment Configuration (T00-04 D1–D5)

Four environments validated at startup. D1: database TLS (`ssl=require` or stricter) in staging/production. D2: frontend `server-only` marker package. D3: staging as strict as production except `LOG_LEVEL=DEBUG`. D4: staging/production never read `.env` files (process environment / secret manager only). D5: dependency-free `pnpm check:env` in `pnpm check`; gitleaks in T00-05. See `docs/architecture/environments.md`.

---

### DEC-021 — Core Component Library (T00-07 D1–D14, ADR-0008)

Delivered in three slices (07A infrastructure/display/states, 07B forms, 07C overlays/data), each with its own PR and merge commit. React Aria Components as the headless primitive layer and Lucide as the single icon family, both behind design-system boundaries enforced by tests. Component-token layer and new interaction tokens; no arbitrary Tailwind values. `/design-system` showcase only in development/test. Spec inconsistencies INC-18 … INC-21 recorded. See `docs/architecture/components.md`.

---

### DEC-020 — Design Token Foundation (T00-06 D1–D10, ADR-0007)

Tailwind CSS 4.3 (CSS-first `@theme`) over three token layers: primitives (DESIGN-SYSTEM.md palette verbatim + documented derived mixes; the only raw colours) → semantic tokens with separate Light and Dark mappings switched by `data-theme` → Tailwind utilities; Tailwind defaults removed; no `dark:` in components. Self-hosted Inter; system monospace. Theme preference `light | dark | system` in `localStorage` (`mti360.theme`, default `system`) applied by a pre-paint script; per-user persistence in Phase 01. Contrast conflicts of specification colours recorded as INC-17 (DESIGN-SYSTEM.md unchanged). See `docs/architecture/design-tokens.md`.

---

### DEC-019 — CI Foundation (T00-05 D1–D10)

Single required status `ci-ok` over parallel jobs repo, frontend, backend, secrets, docker; CodeQL and audits reporting only. Actions pinned by commit SHA (release >= 7 days old); gitleaks/actionlint checksum-verified; no secrets in CI. Dependabot only for github-actions, docker and docker-compose (pnpm 11 and uv compatibility not established). Git workflow: feature branch → PR → Create a merge commit → `main`; the future `main` ruleset (PR, 0 approvals, conversations resolved, merge commit only, `ci-ok` up to date, no force push, no deletion) is documented in `docs/architecture/ci.md` and not yet applied.

---

# 37. RECENT CHANGES

| Date | Change | Impact |
|---|---|---|
| 2026-09-25 | `CLAUDE.md` created | Development rules established |
| 2026-09-25 | `TASKS.md` created | Implementation roadmap established |
| 2026-09-25 | `DEVELOPMENT-STATUS.md` created | Live tracking established |
| 2026-09-26 | Repository audit completed | Actual repository state established (specs + static marketing website only) |
| 2026-09-26 | T00-01 Repository Structure implemented | `READY_FOR_REVIEW`; ADRs 0001–0006 recorded |
| 2026-09-26 | T00-01 reviewed and merged to `main` | `COMPLETED` |
| 2026-09-26 | T00-02 Development Environment implemented | `READY_FOR_REVIEW` on `feat/T00-02-development-environment`; toolchain pinned |
| 2026-09-26 | T00-02 merged to `main` (PR #1, `03b3bec`) | `COMPLETED` |
| 2026-09-26 | T00-03 Docker Development Environment implemented | `READY_FOR_REVIEW` on `feat/T00-03-docker`; local infrastructure + app images |
| 2026-09-26 | T00-03 merged to `main` (PR #3, `c7b769b`) | `COMPLETED` |
| 2026-09-26 | T00-04 Environment Configuration implemented | `READY_FOR_REVIEW` on `feat/T00-04-environment-configuration`; validated per-environment settings |
| 2026-09-27 | T00-04 merged to `main` (PR #4, `09a7413`) | `COMPLETED` |
| 2026-09-27 | T00-05 CI Foundation implemented | `READY_FOR_REVIEW` on `feat/T00-05-ci-foundation`; CI with required `ci-ok`, secret scanning, Docker smoke test |
| 2026-09-27 | T00-05 merged to `main` (PR #5, `e335502`) | `COMPLETED` |
| 2026-09-27 | T00-06 Design Token Foundation implemented | `READY_FOR_REVIEW` on `feat/T00-06-design-tokens`; tokens, Tailwind v4, Light/Dark/System theme |
| 2026-09-27 | T00-06 merged to `main` (PR #6, `0f4346b`) | `COMPLETED` |
| 2026-09-27 | T00-07A components foundation implemented | `READY_FOR_REVIEW` on `feat/T00-07a-components-foundation`; 11 components, React Aria, Lucide, showcase |
| 2026-09-27 | T00-07A merged to `main` (PR #7, `8a370a4`) | `COMPLETED` |
| 2026-09-27 | T00-07B form components implemented | `READY_FOR_REVIEW` on `feat/T00-07b-form-components`; Field/Form + 7 form components |
| 2026-09-27 | T00-07B merged to `main` (PR #8, `1b8740c`) | `COMPLETED` |
| 2026-09-27 | T00-07C overlays, data and interaction controls implemented | `READY_FOR_REVIEW` on `feat/T00-07c-overlays-data`; 15 components + overlay infrastructure |
| 2026-09-28 | T00-07C merged to `main` (PR #9, `e69603e`) | T00-07 `COMPLETED` |
| 2026-09-28 | T00-08 Application Shell implemented | `READY_FOR_REVIEW` on `feat/T00-08-application-shell`; shell + four experience route boundaries |
| 2026-09-28 | T00-08 merged to `main` (PR #10, `4a47f98`) | `COMPLETED` |
| 2026-09-29 | T00-09 Responsive Layout Foundation implemented | `READY_FOR_REVIEW` on `feat/T00-09-responsive-layout`; layout primitives, shell integration, layout showcase |
| 2026-09-29 | T00-09 merged to `main` (PR #11, `265a06d`) | `COMPLETED` |
| 2026-09-29 | T00-10 Accessibility Foundation implemented | `READY_FOR_REVIEW` on `feat/T00-10-accessibility-foundation`; WCAG 2.2 AA contract, guards, helpers, 8 verified fixes, contract tests |
| 2026-09-30 | T00-10 merged to `main` (PR #12, `94cb752`) | `COMPLETED` |
| 2026-09-30 | T00-10A Accessibility Token Correction implemented | `READY_FOR_REVIEW` on `feat/T00-10a-accessibility-token-correction`; INC-24 resolved (Dark `*-text` → derived `*-300`), contrast helper, component regression |
| 2026-09-30 | T00-10A merged to `main` (PR #13, `9f00b2e`) | `COMPLETED`; Phase 00 complete |
| 2026-09-30 | T01-00 Architecture Review approved | `COMPLETED`; D1–D22 with the D10 and D14 amendments; Phase 01 re-sequenced |
| 2026-09-30 | T01-01 Backend, Database & API Foundation implemented | `READY_FOR_REVIEW` on `feat/T01-01-backend-foundation`; database/migrations, context, errors, logging, realm routers, CI PostgreSQL |
| 2026-10-01 | T01-01 merged to `main` (PR #14, `42bc8b1`) | `COMPLETED` |
| 2026-10-01 | T01-02 Audit Foundation implemented | `READY_FOR_REVIEW` on `feat/T01-02-audit-foundation`; audit_events, append-only, first RLS policies, audit and security-event writers |
| 2026-10-02 | T01-02 merged to `main` (PR #16, `91d0180`) | `COMPLETED` |
| 2026-10-02 | T01-03 Tenancy Core implemented | `READY_FOR_REVIEW` on `feat/T01-03-tenancy-core`; tenants, campuses, RLS, ORM filter, tenant-scoped repository, system_context, ADR-0014 |
| 2026-10-02 | T01-03 merged to `main` (PR #19, `f602631`) | `COMPLETED` |
| 2026-10-02 | T01-04 UI contract frozen (`30511bc`) | AUTH-01 … AUTH-08 specification; decisions D04, D19 |
| 2026-10-02 | T01-04 Tenant Identity & Authentication implemented | `READY_FOR_REVIEW` on `feat/T01-04-identity-authentication`; identity tables, RLS with pre-authentication lookup keys, sessions, CSRF, rate limits, lockout, reset, invitations, email, ADR-0015 |

---

# 38. DEVELOPMENT LOG

Use this section as a chronological implementation record.

## Entry Template

```text
### YYYY-MM-DD — TASK-ID

Status:
COMPLETED

Summary:
...

Files:
...

Database:
...

API:
...

UI:
...

Tests:
...

Verification:
...

Known Issues:
...

Next:
...
```

---

# 39. FIRST DEVELOPMENT ENTRY

## 2026-09-25 — Specification Baseline

**Status:**

```text
COMPLETED
```

### Completed

The following product specification documents have been established:

```text
PRD.md
APP-FLOW.md
ARCHITECTURE.md
PLATFORM-ADMIN.md
DESIGN-SYSTEM.md
UI-SCREENS.md
CLAUDE.md
TASKS.md
DEVELOPMENT-STATUS.md
```

### Product Architecture

Four product experiences are defined:

```text
Platform Control Plane
Tenant Application
Student Portal
Public Website
```

### UI Architecture

Approximately 222 screens are defined across the four experiences.

Reusable page templates and component architecture are defined.

### Security Architecture

Core principles are defined for:

- authentication
- authorization
- tenant isolation
- audit
- controlled support access
- AI security

### Implementation

No production application code has been implemented yet.

---

## 2026-09-26 — T00-01 Repository Structure

**Status:**

```text
READY_FOR_REVIEW
```

**Summary:**

Established the approved repository foundation without scaffolding any application code. Recorded the approved architecture decisions as ADRs and documented known specification inconsistencies without resolving them.

**Files:**

```text
Created:
  .gitignore  .gitattributes  .editorconfig
  .env.example  backend/.env.example  frontend/.env.example
  frontend/README.md  backend/README.md  database/README.md
  infrastructure/README.md  tests/README.md  scripts/README.md
  docs/README.md
  docs/adr/0001-stack.md … 0006-api-prefixes.md
  docs/architecture/repository-structure.md  tenancy.md  security.md
  docs/architecture/spec-inconsistencies.md
Changed:
  README.md (rewritten; previously empty)
  ARCHITECTURE.md, TASKS.md, CLAUDE.md, DEVELOPMENT-STATUS.md
  (targeted T00-01 notes only; no requirements removed)
Unchanged (verified by SHA-256):
  index.html  app.js  styles.css
```

**Database / API / UI:**

```text
None (out of scope for T00-01)
```

**Tests:**

```text
No automated tests existed yet at T00-01 (added from T00-02; CI from T00-05).
Checks performed: git renormalize dry run, git check-ignore for .env and
*.example, git diff --check, secret-pattern scan, SHA-256 comparison of
the marketing website files, scan for accidental scaffolding.
```

**Known Issues:**

```text
Specification inconsistencies recorded in
docs/architecture/spec-inconsistencies.md (open, not resolved).
Baseline tags are local only (not pushed).
```

**Next:**

```text
Review T00-01 -> main-branch step -> T00-02 Development Environment
```

---

## 2026-09-26 — T00-02 Development Environment

**Status:**

```text
READY_FOR_REVIEW
```

**Summary:**

Established the development toolchain on `feat/T00-02-development-environment`: pinned runtimes and package managers, Next.js + TypeScript and FastAPI + uv foundations, lint/format/typecheck/test tooling, supply-chain controls and a root command matrix. Details: `docs/architecture/toolchain.md`.

**Files:**

```text
Created: .nvmrc, package.json, pnpm-workspace.yaml, pnpm-lock.yaml,
  .vscode/extensions.json, docs/architecture/toolchain.md,
  frontend/{package.json, tsconfig.json, next.config.ts, eslint.config.mjs,
  .prettierrc.json, .prettierignore, vitest.config.mts, vitest.setup.ts,
  src/app/layout.tsx, src/app/page.tsx, src/app/page.test.tsx},
  backend/{pyproject.toml, uv.lock, .python-version, app/__init__.py,
  app/main.py, app/core/__init__.py, app/core/config.py, tests/conftest.py,
  tests/unit/test_health.py, tests/unit/test_config.py}
Changed: README.md, frontend/README.md, backend/README.md,
  backend/.env.example (comments only), ARCHITECTURE.md (§5 note),
  TASKS.md, DEVELOPMENT-STATUS.md, docs/README.md,
  docs/architecture/repository-structure.md, docs/architecture/security.md
Unchanged (verified): index.html, app.js, styles.css
```

**Database / API / UI:**

```text
Database: none. API: GET /health (liveness only). UI: neutral root page only.
```

**Tests:**

```text
Frontend: 1 smoke test (Vitest). Backend: 7 smoke tests (pytest).
No business, tenancy, auth or database tests (later phases).
```

**Known Issues:**

```text
ESLint 9 is out of upstream support (ESLint 10 blocked by plugin peers).
GitHub default branch is still claude/compassionate-johnson-gxdgr9.
Agent-generated frontend/AGENTS.md + CLAUDE.md policy undecided.
```

**Next:**

```text
Review and merge T00-02 PR -> T00-03 Docker Development Environment
```

---

## 2026-09-26 — T00-03 Docker Development Environment

**Status:**

```text
READY_FOR_REVIEW
```

**Summary:**

Local Docker infrastructure (PostgreSQL 18, Redis 8.8, SeaweedFS 4.47 S3, Mailpit 1.31) in Compose project `mti360`, PostgreSQL role bootstrap for future RLS, production-shaped non-root api and frontend images, and root `infra:*` / `stack:up` commands. Hybrid development: infrastructure in Docker, apps native. Coexists with the separately running ACRS project without affecting it.

**Files:**

```text
Created: compose.yaml, database/init/01-roles.sh,
  infrastructure/object-storage/create-bucket.sh, backend/Dockerfile,
  backend/.dockerignore, frontend/Dockerfile, frontend/Dockerfile.dockerignore,
  docs/runbooks/local-development.md
Changed: .env.example, backend/.env.example (S3 endpoint), frontend/next.config.ts,
  package.json, README.md, infrastructure/README.md, database/README.md,
  docs/architecture/toolchain.md, docs/architecture/repository-structure.md,
  ARCHITECTURE.md (§55 note), TASKS.md, DEVELOPMENT-STATUS.md
Unchanged (verified): index.html, app.js, styles.css; ACRS
```

**Database / API / UI:**

```text
Database: roles and privileges only — no tables, schemas, RLS policies,
extensions or migrations. API / UI: unchanged (GET /health, neutral page).
```

**Tests:**

```text
No new automated tests (infrastructure task). Verification recorded under
T00-03 above; pnpm check passes.
```

**Known Issues:**

```text
Upstream Postgres image trusts in-container loopback connections.
`compose up --wait` treats exited one-shot containers as failures (handled
by a separate `run --rm` init step).
Native `pnpm dev` reads ports from the shell, not from .env.
```

**Next:**

```text
Review and merge T00-03 PR -> T00-04 Environment Configuration
```

---

## 2026-09-26 — T00-04 Environment Configuration

**Status:**

```text
READY_FOR_REVIEW
```

**Summary:**

Typed, validated configuration for development, test, staging and production. Backend `Settings` covers every template variable with per-environment rules and a value-free `ConfigurationError`; `backend/.env` is read only in development; staging/production use the process environment only. Frontend `env.ts` is server-only. `pnpm check:env` guards templates and tracked files. Development still needs zero configuration.

**Files:**

```text
Created: docs/architecture/environments.md, scripts/check-env.mjs,
  backend/tests/unit/test_settings_environments.py,
  backend/tests/unit/test_env_template.py, frontend/src/lib/env.ts,
  frontend/src/lib/env.test.ts
Changed: backend/app/core/config.py, backend/app/main.py (docstring),
  backend/tests/conftest.py, backend/tests/unit/test_config.py,
  backend/pyproject.toml (ruff S105-S107 ignored in tests only),
  .env.example, backend/.env.example, frontend/.env.example (comments only),
  package.json, frontend/package.json, pnpm-lock.yaml, scripts/README.md,
  README.md, backend/README.md, frontend/README.md, docs/README.md,
  docs/architecture/{security,toolchain,repository-structure}.md,
  ARCHITECTURE.md (§56 note), TASKS.md, DEVELOPMENT-STATUS.md
Unchanged (verified): compose.yaml, Dockerfiles, infrastructure and database
  scripts, ADRs, index.html, app.js, styles.css; ACRS
```

**Database / API / UI:**

```text
Database: none (connection settings validated only). API: unchanged
(GET /health; /docs only in development). UI: unchanged.
```

**Tests:**

```text
Backend 139 passed (was 7). Frontend 18 passed (was 1). pnpm check passes.
```

**Known Issues:**

```text
Staging/production require S3 access keys and SMTP credentials (strict D-matrix
reading); revisit if IAM roles or unauthenticated relays are chosen (Phase 17).
Bootstrap-superuser detection uses a fixed name list (postgres,
mti360_superuser). Unset deployed fields also report the rules their local
defaults would break (accurate, somewhat verbose). env.ts is not yet imported
by any page (first consumer: T00-08 shell / API proxy).
```

**Next:**

```text
Review and merge T00-04 PR -> T00-05 CI Foundation
```

---

## 2026-09-27 — T00-05 CI Foundation

**Status:**

```text
READY_FOR_REVIEW
```

**Summary:**

GitHub Actions CI for every PR and push to `main`: parallel repo, frontend, backend, secrets and docker jobs that reuse the existing root scripts, aggregated into the single required status `ci-ok`. Least privilege, no secrets, SHA-pinned actions, checksum-verified tools, full-history gitleaks with a narrow allowlist and a detection self-test, Docker build and API smoke test. CodeQL and dependency audits report only. Dependabot for actions and images only. Future branch protection documented, not applied.

**Files:**

```text
Created: .github/workflows/{ci,codeql,audit}.yml, .github/dependabot.yml,
  .gitleaks.toml, scripts/ci/{install-tool,gitleaks-selftest,docker-smoke}.sh,
  docs/architecture/ci.md
Changed: package.json (scripts only), README.md, docs/README.md,
  docs/architecture/{toolchain,security,repository-structure}.md (§7: merge
  commit, not squash), scripts/README.md, TASKS.md, DEVELOPMENT-STATUS.md
Unchanged (verified): application code, Dockerfiles, compose.yaml,
  environment templates, lockfiles, ADRs, index.html, app.js, styles.css; ACRS
```

**Database / API / UI:**

```text
None.
```

**Tests:**

```text
No new application tests. pnpm check passes (18 frontend, 139 backend).
CI scripts verified locally, including negative cases (corrupted checksum,
self-test allowlist cases, compose without required variables).
```

**Known Issues:**

```text
GitHub-side behaviour (runner, CodeQL upload, Dependabot parsing of the
ARG-based Dockerfile FROM lines) is verified only after the first push.
uv 0.12.19 (T00-02 pin) is itself newer than 7 days; it is an explicit
toolchain pin, like pnpm, not a cooldown-governed dependency.
Dependabot for npm (pnpm 11) and uv is not enabled (compatibility).
```

**Next:**

```text
Review T00-05 -> push, PR, GitHub verification, merge commit -> apply the
documented branch protection -> T00-06 Design Token Foundation
```

---

## 2026-09-27 — T00-06 Design Token Foundation

**Status:**

```text
READY_FOR_REVIEW
```

**Summary:**

Design-token foundation for all experiences: DESIGN-SYSTEM.md palette as primitives, semantic Light and Dark mappings, Tailwind CSS v4 theme with all defaults removed, self-hosted Inter, and the Light/Dark/System theme runtime (pre-paint, OS sync, cross-tab sync, local persistence) with an accessible theme selector on the neutral page. Contrast is tested in both themes.

**Files:**

```text
Created: frontend/postcss.config.mjs, frontend/src/app/globals.css,
  frontend/src/design-system/{README.md, tokens/*, theme/*, typography/fonts.ts},
  docs/architecture/design-tokens.md, docs/adr/0007-styling-tailwind-semantic-tokens.md
Changed: frontend/package.json, pnpm-lock.yaml (additions only),
  frontend/src/app/{layout.tsx, page.tsx, page.test.tsx}, frontend/README.md,
  README.md, ARCHITECTURE.md (§5 note), docs/README.md,
  docs/architecture/{repository-structure,toolchain,spec-inconsistencies}.md,
  TASKS.md, DEVELOPMENT-STATUS.md
Unchanged (verified): backend, database, Dockerfiles, compose.yaml,
  environment templates, CI workflows, ADR-0001..0006, DESIGN-SYSTEM.md,
  index.html, app.js, styles.css; ACRS
```

**Database / API / UI:**

```text
Database / API: none. UI: design tokens, theme runtime, ThemeSelector; the
neutral page is token-styled (still not a product screen).
```

**Tests:**

```text
Frontend 193 passed (was 18). Backend 139 passed. pnpm check passes.
Headless Chromium verification 68/68.
```

**Known Issues:**

```text
Several DESIGN-SYSTEM.md colours fail AA as text (INC-17): used for non-text
only; derived text tokens used instead. Tailwind still allows arbitrary
values and off-grid spacing (review rule; raw colours are test-blocked).
The pre-paint script needs the CSP nonce when CSP is introduced. Theme
preference is local only until Phase 01 identity. Responsive typography and
layout tokens are T00-09.
```

**Next:**

```text
Review T00-06 -> push, PR, CI, merge commit -> T00-07 Core Component Library
```

---

## 2026-09-27 — T00-07A Core Component Library: foundation slice

**Status:**

```text
READY_FOR_REVIEW
```

**Summary:**

First of three T00-07 slices: React Aria Components and Lucide behind design-system boundaries, component infrastructure (cx/focusRing, icon set, axe helper, component tokens, interaction tokens, stronger guards) and eleven components — Button, IconButton, Card, Badge, Tabs, KPI, Timeline, Alert, Skeleton, EmptyState, ErrorState — with a development/test-only showcase.

**Files:**

```text
Created: frontend/src/design-system/{components/*, icons/, lib/, testing/,
  tokens/components.css}, frontend/src/app/design-system/{page,showcase,gate,
  showcase.test}, docs/architecture/components.md,
  docs/adr/0008-headless-primitives-and-icons.md
Changed: frontend/package.json, pnpm-lock.yaml (additions only),
  tokens/{primitives,semantic,tailwind}.css, tokens/{tokens,guard}.test.ts,
  app/globals.css, design-system/README.md, frontend/README.md, README.md,
  ARCHITECTURE.md (§5 note), docs/README.md,
  docs/architecture/{design-tokens,repository-structure,toolchain,
  spec-inconsistencies}.md, TASKS.md, DEVELOPMENT-STATUS.md
Unchanged (verified): backend, database, Docker/compose, CI workflows,
  environment templates, ADR-0001..0007, DESIGN-SYSTEM.md, theme runtime,
  root layout, neutral page, index.html, app.js, styles.css; ACRS
```

**Database / API / UI:**

```text
Database / API: none. UI: 11 library components and the /design-system
showcase (development/test only); no product screens.
```

**Tests:**

```text
Frontend 305 passed (was 193). Backend 139 passed. pnpm check passes.
Headless Chromium verification 70/70.
```

**Known Issues:**

```text
Specification gaps recorded, not resolved: INC-18 (component list, Modal vs
Dialog), INC-19 (chart palette), INC-20 (locale formats), INC-21 (tertiary
vs ghost). Filled destructive/success hover is an elevation change (no
dedicated hover colour token). React Aria Link navigates without client-side
routing until T00-08 adds a RouterProvider. The showcase is exposed if a
deployment omits APP_ENV (defaults to development, T00-04); deployments must
set APP_ENV.
```

**Next:**

```text
Review T00-07A -> push, PR, CI, merge commit -> T00-07B Form components
```

---

## 2026-09-27 — T00-07B Core Component Library: form components

**Status:**

```text
READY_FOR_REVIEW
```

**Summary:**

Second T00-07 slice: a shared Field foundation and Form (native validation, server-error mapping), Input, Textarea, Checkbox, Select, Combobox, DatePicker (ISO API, en-IN, Monday-first product default with override) and FileUpload (client-side UX validation only), with showcase sections and a Student enquiry sample form.

**Files:**

```text
Created: frontend/src/design-system/components/{Field (Field.tsx, Listbox.tsx),
  Input, Textarea, Checkbox, Select, Combobox, DatePicker (+ date.ts),
  FileUpload (+ validate-files.ts)} with tests, frontend/src/app/design-system/
  showcase-forms.tsx
Changed: components/index.ts, icons/index.ts (form icons),
  app/design-system/showcase.tsx and showcase.test.tsx,
  docs/architecture/{components,spec-inconsistencies,repository-structure}.md,
  frontend and design-system READMEs, README.md, TASKS.md,
  DEVELOPMENT-STATUS.md
Unchanged (verified): package.json and lockfiles, tokens, vitest.setup.ts,
  07A components, theme runtime, root layout, neutral page, backend,
  database, Docker/compose, CI, environment templates, ADRs, DESIGN-SYSTEM.md,
  index.html, app.js, styles.css; ACRS
```

**Database / API / UI:**

```text
Database / API: none (FileUpload has no transport). UI: form components and
showcase sections; no product screens.
```

**Tests:**

```text
Frontend 396 passed (was 305). Backend 139 passed. pnpm check passes.
Headless Chromium verification 129/129.
```

**Known Issues:**

```text
While a Combobox popover is open, React Aria hides the rest of the page with
aria-hidden (not inert); axe reports aria-hidden-focus. Tab closes the popover
before focus moves (verified), so hidden content never receives focus.
React Aria clears server errors when the edit is committed (blur), not per
keystroke. Upload types/limits, required/success conventions and the first
day of the week are not specified (INC-22, INC-23, INC-20).
Full-screen mobile sheets for Select/DatePicker are deferred to 07C (Modal).
```

**Next:**

```text
Review T00-07B -> push, PR, CI, merge commit -> T00-07C Overlays and data components
```

---

## 2026-09-27 — T00-07C Core Component Library: overlays, data and interaction controls

**Status:**

```text
READY_FOR_REVIEW
```

**Summary:**

Third T00-07 slice: shared overlay infrastructure, Dialog (Modal), AlertDialog, Popover, Tooltip, Drawer, DropdownMenu, ContextMenu and Toast; DataTable and Pagination; FilterBar, Search, RadioGroup, Switch and TimePicker — with showcase sections. ChartCard was not in the 07C scope and is deferred (INC-19).

**Files:**

```text
Created: frontend/src/design-system/components/{Overlay (overlay.ts,
  PanelDialog.tsx), Dialog (Dialog, AlertDialog), Popover, Tooltip, Drawer,
  Menu (MenuContent, DropdownMenu, ContextMenu), Toast, DataTable,
  Pagination, FilterBar, Search, Radio, Switch, TimePicker (+ time.ts)} with
  tests, frontend/src/app/design-system/showcase-overlays.tsx
Changed: components/index.ts, icons/index.ts (overlay, sort, paging, search
  and filter icons), Field/Listbox.tsx and DatePicker.tsx (shared popover
  surface only), Dialog/AlertDialog test hardening,
  app/design-system/showcase.tsx and showcase.test.tsx,
  docs/architecture/{components,spec-inconsistencies,repository-structure}.md,
  frontend and design-system READMEs, README.md, TASKS.md,
  DEVELOPMENT-STATUS.md
Unchanged (verified): package.json and lockfiles, tokens, theme runtime,
  07A/07B public APIs, root layout, neutral page, backend, database,
  Docker/compose, CI, environment templates, ADRs, DESIGN-SYSTEM.md,
  index.html, app.js, styles.css; ACRS
```

**Database / API / UI:**

```text
Database / API: none (DataTable and Search never fetch). UI: overlay, data and
interaction components and showcase sections; no product screens.
```

**Tests:**

```text
Frontend 482 passed (was 396). Backend 139 passed. pnpm check passes.
Headless Chromium verification 343/343.
```

**Known Issues:**

```text
Dark error-text on surface-elevated is 3.79:1 (INC-24): destructive menu items
keep a text-primary label at rest (error icon; error-text on error-surface
when focused); no token was changed. Toast uses React Aria UNSTABLE_Toast*
exports (pinned 1.21.1) behind the MTI 360 API (INC-25). After a pointer
press on an AlertDialog scrim, React Aria returns focus to the dialog within
a frame. TimePicker is keyboard-first (React Aria has no time list) and
normalises Unicode spaces in literal segments to keep server and client
text identical. ChartCard and PermissionGate/AccessDenied remain deferred.
```

**Next:**

```text
Review T00-07C -> push, PR, CI, merge commit -> T00-07 COMPLETED -> T00-08 Application Shell
```

---

## 2026-09-28 — T00-08 Application Shell & Experience Routing Foundation

**Status:**

```text
READY_FOR_REVIEW
```

**Summary:**

Reusable application shell and the four experience route boundaries: `/platform` (Platform Administration), `/app` (Tenant Application), `/student` (Student Portal) and `/site` (Tenant Public Website preview), each with configuration-driven navigation placeholders, loading and error boundaries. Structural only — no authentication, authorization, tenant resolution or business modules. `/` stays the neutral root page: the marketing landing page is not integrated into Next.js (user decision, INC-26).

**Files:**

```text
Created: frontend/src/shells/ (ApplicationShell, AppHeader, AppSidebar,
  AppNavigation, navigation.ts, MobileNavigation, Breadcrumbs, PageHeader,
  PageContainer, SkipNavigation, UserMenu, NotificationCenter, CommandSearch,
  ShellBoundaries, PublicSiteShell, ExperienceFrame, ExperiencePlaceholder,
  ToastExample, experiences/{types,platform,tenant,student,public-site,index})
  with tests; frontend/src/app/{platform,app,student,site}/ (layout, loading,
  error, [[...slug]]/page); frontend/src/app/experience-routes.test.tsx;
  docs/architecture/application-shell.md
Created (design system): components/Router (NavigationProvider) with test
Changed: design-system/icons/index.ts (shell and navigation icons),
  design-system/components/index.ts (Router export),
  app/design-system/showcase.test.tsx (explicit 20 s budget for the
  whole-page axe test; no assertion changed),
  docs/architecture/{spec-inconsistencies,repository-structure}.md,
  docs/architecture/components.md, docs/README.md, frontend and
  design-system READMEs, README.md, TASKS.md, DEVELOPMENT-STATUS.md
Unchanged (verified): package.json and lockfiles, next.config.ts, tokens,
  theme runtime and storage key, 07A/07B/07C components and public APIs, root layout, neutral
  page, /design-system gate, backend, database, Dockerfiles and ignore files,
  compose, CI, environment templates, ADRs, DESIGN-SYSTEM.md, index.html,
  app.js, styles.css; ACRS
```

**Database / API / UI:**

```text
Database / API: none. UI: shell and placeholder pages that state the module is
not built; demo account/notification data is generic and static.
```

**Tests:**

```text
Frontend 555 passed (was 482). Backend 139 passed. pnpm check passes.
Headless Chromium verification 394/394.
```

**Known Issues:**

```text
Marketing site hosting is undecided (INC-26). /site/* differs from the
architecture's /sites/[site]/* rewrite target (INC-27). Shell names differ
between specifications (INC-28). TenantContext, CampusSwitcher and the
support-session banner slot need authentication/tenancy and are not built.
Collapsed rail items have no visible tooltip (names remain available to
assistive technology). Sidebar collapse state is not persisted.
```

**Next:**

```text
Review T00-08 -> push, PR, CI, merge commit -> T00-09 Responsive Foundation
```

---

## 2026-09-29 — T00-09 Responsive Layout Foundation

**Status:**

```text
READY_FOR_REVIEW
```

**Summary:**

Reusable responsive layout primitives and conventions so future screens adapt consistently from 390px to 1440px+ without inventing layout rules. The T00-08 shell is integrated without API changes, and the layout is demonstrated with generic examples (development/test only). No business screens.

**Files:**

```text
Created: frontend/src/design-system/layout/ (responsive.ts, Container, Stack,
  Inline, Grid, Section, SplitLayout, ActionBar, Show, index.ts) with tests;
  frontend/src/app/design-system/showcase-layout.tsx;
  frontend/src/app/design-system/layout/ (page.tsx, layout-example.tsx, test);
  docs/architecture/layout.md
Changed: shells/PageContainer.tsx, shells/PageHeader.tsx (+ tests);
  design-system/components/Kpi, ErrorState, DataTable (+ tests; layout
  defects, no API change); design-system/lib/cx.ts (insetFocusRing);
  app/design-system/showcase.tsx (+ test); docs/architecture/{components,
  application-shell,spec-inconsistencies}.md, docs/README.md, README.md,
  frontend and design-system READMEs, TASKS.md, DEVELOPMENT-STATUS.md
Unchanged (verified): package.json and lockfiles, tokens and breakpoints,
  theme runtime, 07A/07B/07C and T00-08 public APIs, backend, database,
  Dockerfiles and ignore files, compose, CI, environment templates, ADRs,
  DESIGN-SYSTEM.md, index.html, app.js, styles.css; ACRS
```

**Database / API / UI:**

```text
Database / API: none. UI: layout primitives; generic layout examples with
sample maritime labels on development/test-only pages.
```

**Tests:**

```text
Frontend 609 passed (was 555). Backend 139 passed. pnpm check passes.
Headless Chromium verification 675/675 (includes the T00-08 regression).
```

**Known Issues:**

```text
Content-width caps (72/80rem) are below DESIGN-SYSTEM.md §82's typical
1200-1440px, and the layout primitive names are not in the specifications
(INC-29). Breakpoints are viewport-based: column counts must account for the
256px sidebar (documented). The KPI of a very large unabbreviated figure wraps
in narrow cells; compact formats are recommended. Full RTL is not implemented
(layout is direction-neutral).
```

**Next:**

```text
Review T00-09 -> push, PR, CI, merge commit -> T00-10 Accessibility Foundation
```

---

## 2026-09-29 — T00-10 Accessibility Foundation

**Status:**

```text
READY_FOR_REVIEW
```

**Summary:**

Hardens the existing tokens, components, shell and layouts against WCAG 2.2 AA without redesign, new dependencies, token changes or public API changes. The work covers:

* a documented accessibility contract and screen checklist;
* a focus and reduced-motion base layer;
* shared test helpers and static guards;
* eight verified defects fixed;
* cross-component and shell regression suites.

No business screens.

**Files:**

```text
Created: docs/architecture/accessibility.md; frontend/src/design-system/
  testing/a11y.ts (+ test); frontend/src/app/globals.test.ts;
  design-system/components/accessibility.test.tsx;
  shells/ShellAccessibility.test.tsx
Changed: app/globals.css (focus fallback, reduced-motion net);
  tokens/guard.test.ts (3 guards), tokens/tokens.test.ts (non-text and
  INC-24 pairs); components Pagination, Tabs, Popover, FileUpload,
  DataTable, Search, Toast (+ tests), Combobox test; a11y-focus
  annotations in overlay.ts, PanelDialog, Listbox, MenuContent, DatePicker,
  Toast, ApplicationShell, PublicSiteShell; shells/Breadcrumbs.tsx;
  ShellUtilities/showcase/layout-example tests; docs/architecture/
  {components,application-shell,spec-inconsistencies}.md, docs/README.md,
  README.md, frontend and design-system READMEs, TASKS.md,
  DEVELOPMENT-STATUS.md
Unchanged (verified): package.json and lockfiles, tokens (primitive and
  semantic values), breakpoints, theme runtime, public component/shell/layout
  APIs, backend, database, Dockerfiles and ignore files, compose, CI,
  environment templates, ADRs, DESIGN-SYSTEM.md, index.html, app.js,
  styles.css; ACRS
```

**Database / API / UI:**

```text
Database / API: none. UI: no visual redesign; breadcrumb links are taller on
mobile (44px), tabs show an inset ring, focus fallback on native elements.
```

**Tests:**

```text
Frontend 684 passed (was 609). Backend 139 passed. pnpm check passes.
Headless Chromium verification 1386/1386 (includes the T00-08 and T00-09
suites).
```

**Known Issues:**

```text
Combobox: React Aria hides the page with aria-hidden while the list is open
(axe aria-hidden-focus, page-has-heading-one, region, scrollable-region-
focusable); documented, no repository exclusion, verified harmless. INC-24:
in Dark mode all four *-text state tokens on surface-elevated are below
4.5:1 (3.79-4.22) - field messages inside dialogs/drawers/popovers are
affected; needs a token decision. 32px sm and in-field controls meet 24px
(WCAG 2.5.8) but not the 44px convention. Collapsed rail has no visible
tooltip. Assistive-technology (NVDA/VoiceOver) spot checks remain for
Phase 16/17.
```

**Next:**

```text
Review T00-10 -> push, PR, CI, merge commit -> Phase 00 complete ->
PHASE 01 (T01-01 User Identity Model); decide INC-24 (token task)
```

---

## 2026-09-30 — T00-10A Accessibility Token Correction

**Status:**

```text
READY_FOR_REVIEW
```

**Summary:**

Resolves INC-24. In Dark mode the four `*-text` state tokens failed WCAG 2.2 AA on elevated surfaces: 3.79–4.22:1 on `surface-elevated` / `surface-hover` and 4.00–4.45:1 on `surface-selected`. No existing primitive is a lighter step of these hues. So, as a user-approved narrow exception, four derived `*-300` steps were added using the documented formula, and only Dark `*-text` (plus its no-JavaScript fallback) was remapped to them. Contrast coverage now spans every surface, both at token level and as components render it. No business screens.

**Files:**

```text
Created: frontend/src/design-system/testing/contrast.ts;
  design-system/components/state-text.test.tsx
Changed: tokens/primitives.css (4 derived steps), tokens/semantic.css (Dark
  *-text, 8 lines), tokens/tokens.test.ts; app/design-system/
  showcase-overlays.tsx (+ showcase.test.tsx); Menu/MenuContent.tsx
  (comment only); docs/architecture/{design-tokens,accessibility,
  components,spec-inconsistencies}.md, TASKS.md, DEVELOPMENT-STATUS.md
Unchanged (verified): palette and every existing primitive value, Light
  mappings, Dark indicators and -strong fills, package.json and lockfiles,
  component/shell/layout APIs, breakpoints, typography, spacing, backend,
  database, Dockerfiles and ignore files, compose, CI, environment
  templates, ADRs, DESIGN-SYSTEM.md, index.html, app.js, styles.css; ACRS
```

**Database / API / UI:**

```text
Database / API: none. UI: Dark-mode error/info/success/warning text is
slightly lighter (same hues); icons, indicators, fills and Light mode are
unchanged.
```

**Tests:**

```text
Frontend 783 passed (was 684). Backend 139 passed. pnpm check passes.
Headless Chromium verification 1722/1722 (includes the T00-08, T00-09 and
T00-10 suites).
```

**Known Issues:**

```text
Combobox exception unchanged (React Aria aria-hidden while open). DESIGN-
SYSTEM.md does not list derived steps (as for all derived tokens since
T00-06; documented in design-tokens.md). Assistive-technology spot checks
remain for Phase 16/17.
```

**Next:**

```text
Review T00-10A -> push, PR, CI, merge commit -> Phase 00 complete ->
PHASE 01 (T01-01 User Identity Model)
```

---

## 2026-09-30 — T01-00 Architecture Review

**Status:**

```text
COMPLETED
```

**Summary:**

A read-only review of the repository against the specifications and ADRs. It produced the T01 architecture, data model, authentication, RBAC and isolation design, test strategy, a re-sequenced Phase 01 (T01-00 … T01-10) and decisions D1–D22.

The user approved it on 2026-09-30 with two amendments:
- D14: user identity is separated from authentication credentials;
- D10: post-commit email semantics are documented explicitly.

Both are recorded in ADR-0010 and `docs/architecture/backend-foundation.md` §5 and §10.

---

## 2026-09-30 — T01-01 Backend, Database & API Foundation

**Status:**

```text
READY_FOR_REVIEW
```

**Summary:**

The infrastructure every backend module depends on:
- async SQLAlchemy with asyncpg, and Alembic migrations run as the owner role;
- UUIDv7 identifiers and the column mixins;
- one transaction per request with `SET LOCAL` context, committed before the response;
- the trusted request context;
- the API error envelope;
- redacted JSON logging with request IDs;
- the five realm routers with deny-by-default guards;
- pagination, sorting and schema conventions;
- import-linter layer contracts;
- a PostgreSQL test database in local development and CI.

There are no business tables and no authentication.

**Files:**

```text
Created: backend/alembic.ini, backend/migrations/ (env.py, helpers.py,
  script.py.mako, versions/0001_baseline.py); backend/app/core/{ids,
  context, errors, logging, middleware, schemas, pagination}.py,
  core/db/{base, engine, settings, session}.py; backend/app/api/
  (realms.py, platform, tenant, student, public, webhooks);
  backend/app/modules/__init__.py; backend/tests/{api,security,
  integration}/ and unit tests; database/init/02-test-database.sh;
  scripts/ci/start-test-database.sh; docs/adr/0010-0012;
  docs/architecture/backend-foundation.md
Changed: backend/app/main.py, pyproject.toml, uv.lock, Dockerfile
  (migrations in the image, --no-access-log), tests/conftest.py;
  compose.yaml (migrate service; api gets app/readonly URLs only);
  package.json (db:migrate, db:check, stack:up runs migrate, lint:backend
  runs import-linter, dev:backend --no-access-log); .github/workflows/ci.yml
  (backend job starts PostgreSQL and requires database tests); docs
  (TASKS.md re-baseline, DEVELOPMENT-STATUS.md, spec-inconsistencies,
  repository-structure, ci, runbook, READMEs)
Unchanged (verified): frontend, design tokens, environment templates and
  Settings fields, ADR-0001 … ADR-0008, specification documents,
  index.html, app.js, styles.css; ACRS
```

**Database / API / UI:**

```text
Database: Alembic baseline 0001 (no tables; alembic_version protected).
API: realm routers mounted with no business routes; every authenticated
realm returns 401. UI: none.
```

**Tests:**

```text
Backend 219 passed with the PostgreSQL test database (208 passed + 11
skipped without it). Frontend unchanged (783). Import contracts: 2 kept.
```

**Known Issues:**

```text
The deployed API settings still require MIGRATIONS_DATABASE_URL (T00-04);
the API process should not need owner credentials - follow-up with the
deployment work (compose already withholds them). No readiness endpoint
yet. The CI PostgreSQL step cannot be exercised locally without touching
the developer's mti360 volume (compose pins the project and volume names);
it is verified by actionlint and on the first GitHub run.
```

**Next:**

```text
Review T01-01 -> push, PR, CI (first run of the PostgreSQL step), merge
commit -> T01-02 Audit Foundation
```

---

## 2026-10-01 — T01-02 Audit Foundation

**Status:**

```text
READY_FOR_REVIEW
```

**Summary:**

The audit foundation (ADR-0013, T01-00 decision D22, locked decisions 1.1–1.9):
- one append-only, mixed-scope `audit_events` table with nullable `tenant_id` and no foreign key;
- database-level append-only enforcement through privileges and triggers;
- the repository's first Row-Level Security policies;
- `write_audit_event` in the request transaction;
- `record_security_event`, buffered per request and flushed in a fresh transaction after the request connection is released;
- metadata validation and redaction.

T01-01 was merged to `main` by PR #14 (`42bc8b1`); its status is corrected to `COMPLETED`.

**Files:**

```text
Created: backend/app/core/audit/{__init__, events, metadata, models,
  writer, security}.py; backend/migrations/versions/0002_audit_events.py;
  backend/tests/integration/test_audit_foundation.py;
  backend/tests/unit/test_audit_contract.py; docs/adr/0013-audit-events.md
Changed: backend/app/api/realms.py (guard = function-scoped yield
  dependency with the security-event scope); backend/app/core/db/session.py
  (context_transaction); backend/migrations/env.py (CORE_MODEL_MODULES);
  backend/tests/integration/test_database_foundation.py (head derived, no
  fixed "0001"); docs (backend-foundation §3/§4/§10/§12, security §11,
  tenancy, repository-structure, runbook, spec-inconsistencies INC-35,
  docs/README ADR index); TASKS.md; DEVELOPMENT-STATUS.md
Unchanged (verified): frontend, dependencies (pyproject.toml, uv.lock),
  compose, CI workflow, database/init, environment templates, ADR-0001 …
  ADR-0012, specification documents, index.html, app.js, styles.css; ACRS
```

**Database / API / UI:**

```text
Database: migration 0002 (audit_events, constraints, 3 indexes, grants,
2 triggers + 1 function, RLS with 3 policies). API: no new routes; the
realm guard now also flushes security events. UI: none.
```

**Tests:**

```text
Backend 307 passed with the PostgreSQL test database and
REQUIRE_DATABASE_TESTS=1 (258 passed + 49 skipped without it). Frontend
unchanged. Import contracts: 2 kept.
```

**Known Issues:**

```text
No producers yet (authentication and administration arrive in T01-04 …
T01-08). A failed security-event flush loses those events (logged; no
outbox until the first background-job task). Support session, campus, IP
and result fields are deferred (INC-35). Audit retention needs a reviewed
owner-level migration path (the triggers block deletion for every role).
```

**Next:**

```text
Review T01-02 -> push, PR, CI, merge commit -> T01-03 Tenancy Core
```

---

## 2026-10-02 — T01-03 Tenancy Core

**Status:**

```text
READY_FOR_REVIEW
```

**Summary:**

The tenancy core (ADR-0014; T01-03 locked decisions, D15):
- `tenants` (global registry) and `campuses` (the first tenant-owned table) in migration `0003`, without hard delete;
- Row-Level Security: realm-agnostic `tenant_id = app.tenant_id` on tenant-owned tables, realm-aware on `tenants`;
- `TenantScopedMixin` and the composite foreign-key helper;
- the automatic ORM tenant filter and the tenant-scoped repository, both failing closed without a trusted tenant;
- `system_context` for trusted work outside HTTP;
- the tenant lifecycle rules for T01 and the status access policy.

**Files:**

```text
Created: backend/app/core/tenancy/{__init__, context, filter, mixins,
  repository, system}.py; backend/app/modules/tenants/{__init__, domain,
  models}.py; backend/app/modules/institute/{__init__, models}.py;
  backend/migrations/versions/0003_tenancy_core.py;
  backend/tests/integration/test_tenancy_{schema, isolation}.py;
  backend/tests/unit/test_tenancy_{models, core, domain}.py;
  docs/adr/0014-tenancy-core.md
Changed: backend/app/core/context.py (context_scope);
  backend/app/core/db/session.py (session.info context, session_context);
  backend/migrations/script.py.mako (checklist); docs (backend-foundation,
  tenancy, security, repository-structure, spec-inconsistencies, README);
  TASKS.md; DEVELOPMENT-STATUS.md
Unchanged (verified): frontend, dependencies (pyproject.toml, uv.lock),
  compose, Dockerfiles, CI workflow, database/init, migrations 0001/0002,
  app/core/audit, app/api, ADR-0001 … ADR-0013, specification documents,
  index.html, app.js, styles.css; ACRS
```

**Database / API / UI:**

```text
Database: migration 0003 (2 tables, 7 constraints, 4 indexes, grants,
RLS with 6 policies). API: none. UI: none.
```

**Tests:**

```text
Backend 410 passed with the PostgreSQL test database and
REQUIRE_DATABASE_TESTS=1 (311 passed + 99 skipped without it). pnpm check
passed (frontend 783 tests, build). Import contracts: 2 kept. CI not run.
```

**Known Issues:**

```text
No platform write path into tenant-owned rows (INC-39, T01-07) and no
unscoped() block (INC-38). Campus status, address, contact and timezone are
deferred (INC-40, T01-08). T01-04 must let a signed-in user list the
tenants of their memberships before a tenant is active (tenants RLS reads
only the trusted tenant). Test tenants accumulate in the shared test
database (no DELETE), as audit rows do.
```

**Next:**

```text
Review T01-03 -> push, PR, CI, merge commit -> T01-04 Tenant Identity &
Authentication
```

---

## 2026-10-02 — T01-04 Tenant Identity & Authentication

**Status:**

```text
READY_FOR_REVIEW
```

**Summary:**

The tenant authentication backend (ADR-0015; decisions D01–D19; UI contract frozen in `30511bc`):
- seven identity tables with Row-Level Security, reached before sign-in only through equality-matched `SET LOCAL` lookup keys;
- sign-in with generic failures, dummy-hash timing, Redis rate limits and a database lockout;
- sessions stored as HMACs and re-validated on every request, with institute and campus selection per D04;
- password reset and invitations per D19, with email after commit and response;
- CSRF tokens on session routes and a same-origin check on anonymous routes.

T01-03 was merged to `main` by PR #19 (`f602631`); its status is corrected to `COMPLETED` (D18).

**Files:**

```text
Created: backend/app/modules/identity/{__init__, domain, tokens,
  passwords, lookup, models, repository, service, schemas, router, events,
  templates}.py and data/common-passwords.{txt,LICENSE};
  backend/app/core/{net, ratelimit}.py; backend/app/integrations/
  {__init__, email/{__init__, sender, smtp, fake}}.py;
  backend/migrations/versions/0004_identity_authentication.py;
  backend/tests/identity_support.py; tests/integration/test_{identity_
  schema, authentication_api, session_recovery_api, rate_limiting}.py;
  tests/unit/test_{identity_rules, email_integration}.py;
  tests/security/test_identity_boundaries.py; docs/adr/0015-identity-
  authentication.md
Changed: backend/app/api/{realms, tenant}.py; backend/app/main.py;
  backend/app/core/{config, context, errors, middleware}.py;
  backend/app/core/tenancy/mixins.py (optional FK name);
  backend/.env.example; backend/pyproject.toml, uv.lock; compose.yaml;
  scripts/ci/start-test-database.sh; .github/workflows/ci.yml (step names);
  tests (conftest Redis fixture, settings, CI script, API conventions,
  T01-03 schema/model tests scoped to T01-03 objects); docs
  (identity-authentication, backend-foundation, security, tenancy,
  environments, repository-structure, runbook, spec-inconsistencies,
  README); TASKS.md; DEVELOPMENT-STATUS.md
Unchanged (verified): frontend, frozen UI contract, migrations 0001-0003,
  database/init, ADR-0001 … ADR-0014, specification documents, marketing
  site; ACRS
```

**Database / API / UI:**

```text
Database: migration 0004 (7 tables, RLS with 21 policies, grants). API:
9 routes (6 under /api/v1/auth, 3 under /api/v1/session). UI: none
(T01-09).
```

**Tests:**

```text
Backend 538 passed with the PostgreSQL test database, Redis and
REQUIRE_DATABASE_TESTS=1 (368 passed + 170 skipped without them). pnpm
check passed (frontend 783 tests, build). Import contracts: 2 kept.
gitleaks: no leaks. CI not run.
```

**Known Issues:**

```text
The approved 10k blocklist adds little beyond the 12-character minimum
(INC-42). Sign-in security events carry no principal or tenant (anonymous
request; the user is the target, D13). Each authenticated request runs two
short extra transactions for session re-validation (measure before caching).
Invitation creation belongs to T01-07/T01-08 (only system fixtures create
invitations now). Sessions and tokens are never deleted (retention later).
```

**Next:**

```text
Review T01-04 -> push, PR, CI (PostgreSQL + Redis), merge commit -> T01-05
Authorization & RBAC
```

---

# 40. NEXT TASK

The next step is:

```text
Review T01-04 (READY_FOR_REVIEW, branch feat/T01-04-identity-authentication):
push, open the pull request, verify CI on GitHub (PostgreSQL and Redis
integration tests required) and merge with a merge commit. Then continue
with T01-05 — Authorization & RBAC.
```

The completed-task description below is retained for reference.

```text
T00-01 — Repository Structure
```

### Objective

Establish the actual MTI 360 repository structure and verify the existing project environment before implementation begins.

### Required Actions

1. Inspect the repository.
2. Inspect existing files.
3. Inspect Git status.
4. Identify existing application code, if any.
5. Determine current frontend/backend structure.
6. Compare actual repository against `ARCHITECTURE.md`.
7. Do not delete or overwrite existing work.
8. Propose required structural changes.
9. Implement only after understanding the existing state.
10. Update this document after verification.

---

# 41. NEXT DEVELOPMENT SEQUENCE

After `T00-01`:

```text
T00-02 Development Environment
        ↓
T00-03 Docker
        ↓
T00-04 Environment Configuration
        ↓
T00-05 CI
        ↓
T00-06 Design Tokens
        ↓
T00-07 Components
        ↓
T00-08 Application Shell
        ↓
T00-09 Responsive Foundation
        ↓
T00-10 Accessibility
        ↓
PHASE 01
```

---

# 42. HOW CLAUDE CODE MUST UPDATE THIS FILE

After completing a task:

### 1. Update task status

Example:

```text
T00-01
Status: COMPLETED
```

### 2. Update phase count

Example:

```text
1 / 10 tasks
```

### 3. Update overall completion

Only use a meaningful calculation based on actual completed work.

### 4. Add development log entry

Record:

- date
- task
- summary
- files
- tests
- verification
- known issues

### 5. Update blockers

Remove resolved blockers.

### 6. Update next task

Identify the next executable task from `TASKS.md`.

---

# 43. STATUS INTEGRITY RULE

Claude Code must never mark a task:

```text
COMPLETED
```

unless the task's required acceptance criteria and verification have been satisfied.

For example:

```text
Code exists
≠
Feature complete
```

and:

```text
UI exists
≠
Feature complete
```

and:

```text
Tests exist
≠
Tests pass
```

---

# 44. VERIFICATION RULE

When recording verification, use factual statements.

Good:

```text
Backend unit tests: 42 passed
API integration tests: 18 passed
Build: passed
```

Bad:

```text
Looks good.
Should work.
Probably production-ready.
```

---

# 45. BLOCKER RULE

When a task is blocked, record:

```text
Task:
Txx-xx

Status:
BLOCKED

Blocker:
...

Impact:
...

Required Resolution:
...

Can Parallel Work Continue?
YES / NO
```

---

# 46. NO FALSE PROGRESS

Do not count:

- generated placeholder files
- mock screens
- unconnected UI
- fake API responses
- incomplete components

as completed production functionality.

Prototype work may be recorded separately.

---

# 47. PROTOTYPE STATUS

If prototype work is created, track it separately:

```text
Prototype:
YES

Production Ready:
NO
```

This prevents prototype progress from being confused with production progress.

## Current Prototypes

### PROTO-01 — MTI 360 Marketing Website

```text
Files:            index.html, app.js, styles.css (repository root)
Baseline tag:     marketing-site-v1
Prototype:        YES
Production Ready: NO
```

**Reason:**

- The demo-request form is non-functional: it shows a success message without sending data anywhere.
- It is a marketing prototype for MTI 360 itself — **not** the MTI 360 application and **not** the Tenant Public Website (ADR-0003).

It does not count toward any product phase, screen or task completion. Changes are made only through the Marketing Website Track (`MKT-*`) in `TASKS.md`.

---

# 48. SCREEN COMPLETION RULE

A screen can be marked implemented only when:

```text
[ ] Correct screen ID
[ ] Correct route
[ ] Correct persona
[ ] Correct permissions
[ ] Correct data source
[ ] Correct API integration
[ ] Correct page template
[ ] Correct design-system usage
[ ] Loading state
[ ] Empty state
[ ] Error state
[ ] Responsive behavior
[ ] Accessibility
```

where applicable.

---

# 49. FEATURE COMPLETION RULE

A feature can be considered complete only when its major layers are complete:

```text
Database
+
Backend
+
API
+
Authorization
+
Frontend
+
Testing
+
Observability
```

---

# 50. RELEASE READINESS STATUS

At any point, maintain this summary:

| Area | Status |
|---|---|
| Core Functionality | NOT_STARTED |
| Security | NOT_STARTED |
| Multi-Tenancy | NOT_STARTED |
| Performance | NOT_STARTED |
| Accessibility | NOT_STARTED |
| Observability | NOT_STARTED |
| AI Safety | NOT_STARTED |
| Backup / Recovery | NOT_STARTED |
| Production Infrastructure | NOT_STARTED |
| Release Validation | NOT_STARTED |

---

# 51. FINAL RELEASE GATE

MTI 360 must not be considered production-ready until:

```text
[ ] Core workflows work
[ ] Tenant isolation verified
[ ] Authorization verified
[ ] Critical security tests pass
[ ] Database migrations verified
[ ] Backup verified
[ ] Restore verified
[ ] Monitoring operational
[ ] Error handling verified
[ ] Critical E2E tests pass
[ ] Performance reviewed
[ ] Accessibility reviewed
[ ] AI guardrails reviewed
[ ] Communication integrations verified
[ ] Billing verified
[ ] Documentation complete
```

---

# 52. MASTER STATUS SUMMARY

```text
MTI 360

Specification
████████████████████ 100%

Architecture
████████████████████ 100%

Design Definition
████████████████████ 100%

Implementation
░░░░░░░░░░░░░░░░░░░░ 0%

Testing
░░░░░░░░░░░░░░░░░░░░ 0%

Security Verification
░░░░░░░░░░░░░░░░░░░░ 0%

Production Readiness
░░░░░░░░░░░░░░░░░░░░ 0%
```

> The specification percentages represent the current documentation baseline, not software implementation progress.

---

# 53. FINAL PRINCIPLE

`DEVELOPMENT-STATUS.md` must always answer five questions:

```text
1. Where are we?
2. What has actually been completed?
3. What is being worked on?
4. What is blocking progress?
5. What should Claude Code do next?
```

If those five questions cannot be answered from this document, update it.

---

# 54. END STATE

When MTI 360 reaches production:

```text
DEVELOPMENT-STATUS.md
        ↓
Accurately reflects
        ↓
Actual implementation
        ↓
Actual verification
        ↓
Actual production readiness
```

It must never become a stale checklist.

---

**MTI 360**

**Acquire Students. Simplify Operations. Grow Your Institute.**