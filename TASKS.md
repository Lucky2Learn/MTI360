# MTI 360 — TASKS.md

## Master Implementation Roadmap

**Product:** MTI 360
**Positioning:** The Complete Growth & Operations Platform for Maritime Training Institutes
**Tagline:** Acquire Students. Simplify Operations. Grow Your Institute.
**Status:** Master Implementation Roadmap
**Version:** 1.0

---

# 1. PURPOSE

This document defines the implementation roadmap for MTI 360.

It converts the product specifications into executable development phases and tasks for Claude Code and development teams.

This document must be used together with:

```text
PRD.md
APP-FLOW.md
ARCHITECTURE.md
PLATFORM-ADMIN.md
DESIGN-SYSTEM.md
UI-SCREENS.md
CLAUDE.md
DEVELOPMENT-STATUS.md
```

`TASKS.md` defines:

* what to build
* in what order
* dependencies
* implementation scope
* tests
* acceptance criteria
* definition of done

---

# 2. IMPORTANT IMPLEMENTATION PRINCIPLE

MTI 360 contains approximately 222 defined screens across:

```text
Platform Control Plane
Tenant Application
Student Portal
Public Website
```

These must NOT be implemented as 222 independent UI projects.

Use:

```text
222+ Screen Specifications
        ↓
18 Page Templates
        ↓
30–50 Core Components
        ↓
Reusable Domain Components
        ↓
Vertical Feature Slices
```

The implementation must maximize reuse.

---

# 3. DEVELOPMENT STRATEGY

Build MTI 360 using **vertical slices**, not only horizontal technical layers.

A vertical slice should ideally contain:

```text
Database
   ↓
Domain / Business Logic
   ↓
API
   ↓
Authorization
   ↓
UI
   ↓
Validation
   ↓
Tests
   ↓
Audit / Observability
```

A feature is not considered complete merely because its UI exists.

---

# 4. MASTER PHASE MAP

```text
PHASE 00 — Foundation
        ↓
PHASE 01 — Authentication & Multi-Tenancy
        ↓
PHASE 02 — Platform Control Plane
        ↓
PHASE 03 — Tenant Foundation
        ↓
PHASE 04 — Admissions
        ↓
PHASE 05 — Academics
        ↓
PHASE 06 — Finance
        ↓
PHASE 07 — Compliance
        ↓
PHASE 08 — Placement
        ↓
PHASE 09 — Communication
        ↓
PHASE 10 — Automation
        ↓
PHASE 11 — AI
        ↓
PHASE 12 — Analytics
        ↓
PHASE 13 — Student Portal
        ↓
PHASE 14 — Public Website
        ↓
PHASE 15 — SaaS Billing & Operations
        ↓
PHASE 16 — Security & Hardening
        ↓
PHASE 17 — Production Readiness
```

---

# 5. TASK STATUS

Use only these statuses:

```text
NOT_STARTED
IN_PROGRESS
BLOCKED
READY_FOR_REVIEW
COMPLETED
DEFERRED
```

---

# 6. PRIORITY

Use:

```text
P0 = Critical / foundational
P1 = Required for initial production release
P2 = Important enhancement
P3 = Future enhancement
```

---

# 7. TASK FORMAT

Every implementation task should follow:

```text
Task ID
Title
Priority
Status
Objective
Dependencies
Scope
Database
Backend
API
Frontend
UI Screens
Permissions
Security
Tests
Acceptance Criteria
Definition of Done
```

---

# PHASE 00 — FOUNDATION

## Objective

Establish the technical foundation required for all subsequent MTI 360 development.

---

## T00-01 — Repository Structure

**Priority:** P0
**Status:** COMPLETED (reviewed and merged to `main` at `914729b`)

### Objective

Establish the agreed repository structure.

### Scope

Define clear boundaries for:

```text
Frontend
Backend
Shared
Database
Infrastructure
Documentation
Tests
Scripts
```

### Acceptance Criteria

* Repository structure documented.
* Frontend/backend boundaries clear.
* Shared code location defined.
* Environment configuration separated.

### Definition of Done

Repository builds successfully using the documented process.

### T00-01 Update (2026-09-26)

Approved via the T00-01 proposal. Decisions: `docs/adr/0001`–`0006`. Structure: `docs/architecture/repository-structure.md`.

**Shared code location:** frontend shared code lives in `frontend/src/design-system/`, `frontend/src/shells/` and `frontend/src/lib/`; backend shared infrastructure lives in `backend/app/core/`. There is no cross-language shared package; TypeScript API types are generated from the FastAPI OpenAPI schema.

**Concrete acceptance criteria:**

* `.gitignore`, `.gitattributes`, `.editorconfig` exist; `.env` files are ignored; `*.example` files are not ignored; `git add --renormalize .` produces no changes.
* Top-level `frontend/`, `backend/`, `database/`, `infrastructure/`, `tests/`, `docs/`, `scripts/` are tracked, each with a README stating purpose, ownership, what belongs, what does not belong and which task populates it.
* `.env.example`, `backend/.env.example`, `frontend/.env.example` contain placeholders only.
* ADRs 0001–0006 and `docs/architecture/` notes exist; known inconsistencies are recorded in `docs/architecture/spec-inconsistencies.md`.
* No application framework, package manifest, Dockerfile, migration, component or endpoint is created.
* The root marketing website files (`index.html`, `app.js`, `styles.css`) are byte-identical before and after (SHA-256 verified).

**Definition of Done amendment:** "Repository builds successfully" is **not applicable** to T00-01 because no buildable project exists until T00-02. The build criterion transfers to T00-02.

---

## T00-02 — Development Environment

**Priority:** P0

Configure:

* local development
* environment variables
* database
* cache/queue where required
* file storage
* local services
* development scripts

### Acceptance Criteria

A new developer can start the project using documented setup instructions.

### T00-02 Update (2026-09-26)

**Status:** COMPLETED (merged to `main` via PR #1, merge commit `03b3bec`)

**Approved scope (T00-02 proposal, decisions D1–D8):** development toolchain only — runtime/package-manager pins, Next.js + TypeScript foundation, FastAPI + uv foundation, lint/format/typecheck/test tooling, root command matrix. Toolchain details: `docs/architecture/toolchain.md`.

**Scope moved to later tasks (not dropped):** database, cache/queue, file storage and local services → T00-03 (Docker) and the first task that uses each client library (decision D5). Environment validation → T00-04.

**Concrete acceptance criteria:**

* Node.js, pnpm, Python and uv versions pinned (`.nvmrc`, `packageManager`, `engines`, `.python-version`, `required-version`).
* `pnpm-lock.yaml` and `uv.lock` committed; `pnpm bootstrap` (frozen / locked installs) succeeds.
* `pnpm dev`, `build`, `lint`, `typecheck`, `test`, `format`, `format:check`, `check:landing` and `check` exist and pass.
* `pnpm dev` serves the neutral frontend page and `GET /health` → `{"status": "ok"}`.
* Minimal runtime code only (D4): root layout + neutral page; `create_app()`, `Settings`, `/health`.
* No SQLAlchemy, Alembic, asyncpg, Redis or S3 client (D5); no Dockerfile, compose file, migration, CI workflow, authentication or tenancy code.
* 7-day supply-chain cooldown active for pnpm and uv (D7).
* `index.html`, `app.js`, `styles.css` identical to `marketing-site-v1`.

**Definition of Done:** the "repository builds successfully" criterion transferred from T00-01 is satisfied by `pnpm build` / `pnpm check`.

---

## T00-03 — Docker Development Environment

**Priority:** P0

Provide reproducible local infrastructure where defined by architecture.

Include:

* application
* database
* Redis/queue if required
* supporting services

### Acceptance Criteria

Clean environment can be started successfully.

### T00-03 Update (2026-09-26)

**Status:** COMPLETED (merged to `main` via PR #3, merge commit `c7b769b`)

**Approved decisions:** D1 branch from `main` after T00-02; D2 SeaweedFS 4.47; D3 Redis 8.8; D4 defer `migrate` and `worker`; D5 documented default ports with local `.env` overrides; D6 PostgreSQL 18 via `pgvector/pgvector:0.8.6-pg18-trixie` (pgvector not enabled); D7 Mailpit now.

**Scope moved to later tasks (not dropped):** `migrate` (Alembic) → first database task; `worker` + queue library → first background-job task (this moves the queue-library choice ADR-0001 placed in T00-03).

**Concrete acceptance criteria:**

* `docker compose config` passes; Compose project name fixed to `mti360`; volumes `mti360_*`; host ports on `127.0.0.1`.
* `pnpm infra:up` starts PostgreSQL, Redis, SeaweedFS and Mailpit from empty volumes, health-gated.
* Roles `mti_owner` / `mti_app` / `mti_readonly` exist with no SUPERUSER, CREATEDB, CREATEROLE, REPLICATION or BYPASSRLS; passwords only from `.env`.
* Redis answers PONG; the private bucket exists; anonymous S3 access is denied; Mailpit is ready.
* Native `pnpm dev` works against the infrastructure; `pnpm stack:up` runs healthy non-root api and frontend containers.
* A missing `.env` makes Compose fail with a clear message.
* `pnpm infra:reset` removes only MTI 360 containers, network and volumes; other local projects (ACRS) are unaffected.
* No Alembic, migration, worker, queue library, tables, RLS policies, authentication or tenancy code; `pnpm check` passes; landing page unchanged.

---

## T00-04 — Environment Configuration

**Priority:** P0

Define:

```text
Development
Test
Staging
Production
```

Ensure secrets are never committed.

### T00-04 Update (2026-09-26)

**Status:** COMPLETED (merged to `main` via PR #4, merge commit `09a7413`)

**Approved decisions:** D1 database TLS (`ssl=require` or stricter) in staging/production; D2 `server-only` package in the frontend; D3 staging as strict as production except `LOG_LEVEL=DEBUG`; D4 staging/production never read `.env` files; D5 dependency-free `pnpm check:env` in `pnpm check` (gitleaks in T00-05). Environment matrix: `docs/architecture/environments.md`.

**Concrete acceptance criteria:**

* `Settings` types every variable in `backend/.env.example`; a test and `pnpm check:env` prove nothing is missing or extra.
* Development starts with no `backend/.env` (T00-03 defaults); `backend/.env` overrides when present; test uses explicit values and never reads `.env`; staging/production use the process environment only.
* Staging and production refuse to start for each rule violation (debug, fake AI provider, placeholder/short/equal secrets, implicit infrastructure settings, database users/superusers/TLS, non-https CORS origins and S3 endpoint; production also `LOG_LEVEL=DEBUG`), each with a failing and a passing test.
* No secret value appears in any `ConfigurationError`, `ValidationError`, `repr` or log output (tested).
* `frontend/src/lib/env.ts` validates server env, exposes only `NEXT_PUBLIC_APP_NAME`, and is `server-only` (a Client Component import fails the build).
* `pnpm check:env` passes on the repository and fails for each defect class.
* The `api` container still starts under `pnpm stack:up` with `APP_ENV=development`.
* No database engine/connection/schema/migration, no Redis/S3/SMTP clients, no auth/session/tenancy/CORS middleware, no Docker/compose changes; landing page unchanged; no secrets committed.

---

## T00-05 — CI Foundation

**Priority:** P1

Implement automated:

```text
Lint
Type Check
Unit Tests
Build
```

### T00-05 Update (2026-09-27)

**Status:** COMPLETED (merged to `main` via PR #5, merge commit `e335502`)

**Approved decisions:** D1 three workflows — `ci.yml` (required via `ci-ok`), `codeql.yml` and `audit.yml` (reporting only); D2 minimal SHA-pinned action set, gitleaks/actionlint as checksum-verified binaries; D3 root scripts `format:check:frontend`, `format:check:backend`, `check:lock` (in `pnpm check`); D4 uv cache only; D5 gitleaks over all refs with `--redact`, allowlist only exact path AND exact value; D6 Docker smoke test starts the API only; D7 Dependabot for `github-actions`, `docker`, `docker-compose` only (npm/pnpm 11 and uv compatibility could not be established); D8 CodeQL and audits visible but not required; D9 ACRS confirmed by listing comparison only; D10 future branch protection — PR required, 0 approvals, conversations resolved, merge commit only, `ci-ok` required and up to date, no force push, no deletion, no linear-history rule (documented, not applied). Details: `docs/architecture/ci.md`.

**Concrete acceptance criteria:**

* `ci.yml` runs on PRs to `main`, pushes to `main` and manual dispatch on `ubuntu-24.04`, with no secrets, no `pull_request_target` and `persist-credentials: false`.
* Jobs `repo`, `frontend`, `backend`, `secrets`, `docker` run in parallel and call the existing root scripts; `ci-ok` passes only when all five succeed.
* Every action is pinned to a full commit SHA of a release at least 7 days old; gitleaks and actionlint are SHA-256 verified.
* gitleaks scans the full history; the allowlist is exact path AND exact value; a self-test proves detection and narrowness.
* Both images build (never pushed); `/health` returns 200; production without configuration fails fast; compose configuration is valid.
* CodeQL and audits run but are not required; Dependabot covers only the approved ecosystems.
* No application code, Dockerfile, compose, environment template, lockfile, landing-page or ADR changes.

---

## T00-06 — Design Token Foundation

**Priority:** P0

Implement the tokens from `DESIGN-SYSTEM.md`.

Include:

* colors
* typography
* spacing
* radius
* shadows
* breakpoints
* semantic states

No arbitrary UI colors.

### T00-06 Update (2026-09-27)

**Status:** COMPLETED (merged to `main` via PR #6, merge commit `0f4346b`)

**Approved decisions:** D1 Tailwind CSS 4.3.3 (CSS-first `@theme`) mapped to semantic tokens, Tailwind default colours/type sizes/radii/breakpoints removed; D2 ADR-0007; D3 self-hosted Inter variable font (`@fontsource-variable/inter` 5.3.0 via `next/font/local`); D4 DESIGN-SYSTEM.md colours kept verbatim, documented derived mixes for accessible text/neutrals/dark surfaces (INC-17); D5 restrained Light shadows, near-zero Dark shadows; D6 system monospace stack (INC-12); D7 minimal accessible `ThemeSelector`; D8 headless Chromium visual verification; D9 `localStorage` `mti360.theme`, default `system`; D10 breakpoints tablet 768 / desktop 1024 / large 1440. Details: `docs/architecture/design-tokens.md`, `docs/adr/0007-styling-tailwind-semantic-tokens.md`.

**Concrete acceptance criteria:**

* All DESIGN-SYSTEM.md §6–§8 colours exist verbatim as primitives; every derived colour is a documented, test-recomputed mix of two palette colours.
* Every §10 semantic token (plus `*-surface`, `*-text`, `link`, `focus-ring`, elevation) has a Light and a Dark mapping referencing primitives only; the no-JS fallback equals Dark.
* Typography, spacing, radius, shadows and breakpoints exist as tokens/utilities; Tailwind defaults for colour, font, type size, weight, radius, shadow and breakpoint are removed.
* WCAG 2.2 AA contrast passes in both themes (4.5:1 text, 3:1 non-text); raw colours only in `primitives.css`; no `dark:` outside the token layer.
* Light / Dark / System selectable, persisted locally, live OS changes, cross-tab sync, safe without storage, applied before first paint, no hydration warnings.
* `ThemeSelector` is a labelled native radio group, keyboard operable, not colour-only.
* No backend, database, Docker, compose, environment template, CI workflow, existing ADR or landing-page changes.

---

## T00-07 — Core Component Library

**Priority:** P0

Implement reusable:

```text
Button
Input
Select
Combobox
DatePicker
FileUpload
Tabs
Card
Badge
DataTable
FilterBar
Pagination
Modal
Drawer
Dialog
Toast
Alert
Timeline
KPI
ChartCard
EmptyState
ErrorState
Skeleton
```

### T00-07 Update (2026-09-27)

**Status:** COMPLETED — delivered in three slices (decision D1): **07A** merged to `main` via PR #7 (merge commit `8a370a4`); **07B** forms via PR #8 (`1b8740c`); **07C** overlays, data and interaction controls via PR #9 (`e69603e`).

**Approved decisions (D1–D14):** D1 three slices, each with its own PR and merge commit; D2 React Aria Components 1.21.1 (ADR-0008); D3 Lucide 1.47.0 via `design-system/icons`; D4 local `cx()` and typed variant maps; D5 semantic `surface-hover`, `surface-selected`, `brand-primary-hover`, `success-strong`, `error-strong`, `overlay-scrim` plus a component-token layer (control heights 32/40/44, focus ring, z-index); D6 guards (no arbitrary values, React Aria/Lucide boundaries, no raw HTML); D7 user-event and axe-core; D8 `/design-system` showcase for development/test only; D9 Modal = container, Dialog = confirmation on Modal; D10 default locale `en-IN`; D11 ChartCard is a frame, no chart library; D12 add IconButton/Textarea/Checkbox, defer Radio/Switch/TimePicker/Search/PermissionGate; D13 tertiary = text-style, ghost = hover surface, success uses `success-strong`; D14 Toast region mounted by T00-08. Details: `docs/architecture/components.md`, `docs/adr/0008-headless-primitives-and-icons.md`; INC-18 … INC-21.

**07A acceptance criteria:**

* Button, IconButton, Card, Badge, Tabs, KPI, Timeline, Alert, Skeleton, EmptyState and ErrorState exist with §73/§74 contracts, token-only styling and tests including axe.
* Guards pass: no raw colours, no `dark:`, no arbitrary values, React Aria and Lucide only inside their boundaries, raw HTML only for the pre-paint script.
* New semantic tokens pass Light/Dark parity, primitives-only and contrast tests.
* Light and Dark at 390/768/1024/1440: axe (including contrast) 0 violations, no overflow, no console warnings, no external requests; keyboard and focus verified in Chromium.
* `/design-system` renders only in development/test; 404 otherwise; `noindex`.
* No backend, database, Docker, compose, CI, environment template, existing ADR, DESIGN-SYSTEM.md or landing-page changes.

**07B approved decisions (D1–D12):** D1 `value`/`defaultValue`/`onChange` + React Aria-style booleans; D2 DatePicker ISO `YYYY-MM-DD` strings (`@internationalized/date` internal); D3 **Monday-first is the MTI 360 product default**, independent of the `en-IN` locale (whose CLDR default is Sunday), with a `firstDayOfWeek` override; D4 visible `*` + programmatic required; D5 native validation, `validate`, `Form validationErrors` for server errors; D6 opt-in success; D7 FileUpload client validation is UX only, server authoritative, no previews/object URLs/file reading; D8 jsdom polyfills only if proven necessary (none were); D9 popovers on all sizes (mobile sheet → 07C); D10 no new tokens or dependencies; D11 showcase sections + Student enquiry form; D12 INC-20 updated, INC-22 and INC-23 recorded.

**07B acceptance criteria:**

* Field foundation/Form, Input, Textarea, Checkbox, Select, Combobox, DatePicker and FileUpload exist with contracts in `components.md`; 07A public APIs unchanged.
* Controlled and uncontrolled APIs; `name` values in `FormData`; native validation blocks submit and focuses the first invalid field; server errors map to fields.
* Keyboard models, visible focus, 44px targets on mobile; axe 0 violations (unit tests with popovers open; browser incl. contrast) in Light and Dark.
* DatePicker: DD/MM/YYYY for `en-IN`, ISO API, Monday-first default, `firstDayOfWeek` override, min/max/unavailable validation, no hydration warnings.
* FileUpload: D7 rules enforced and tested; no transport, previews or object URLs.
* No new dependencies or tokens; guards pass; no backend, database, Docker, compose, CI, environment template, ADR, DESIGN-SYSTEM.md or landing-page changes.

**07C scope (T00-07C implementation prompt):** Dialog/Modal (sm–xl), AlertDialog, Popover, Tooltip and shared overlay infrastructure; Drawer (left/right/top/bottom), DropdownMenu, ContextMenu, Toast; DataTable (typed, sorting, single/multiple selection with indeterminate select-all, row actions, loading/empty/error, responsive) and Pagination; FilterBar (mobile Drawer), Search, Radio, Switch, TimePicker (`en-IN`, `@internationalized/date`, no time zones). This brings Radio, Switch, TimePicker and Search forward from the D12 deferral. ChartCard (D11) is not in the 07C scope and is deferred (INC-19); PermissionGate/AccessDenied remain deferred. Naming: `Dialog` = TASKS.md "Modal", `AlertDialog` = TASKS.md "Dialog" (INC-18).

**07C acceptance criteria:**

* All 07C components exist with contracts in `components.md` (§3C); 07A/07B public APIs unchanged.
* Overlays: focus moves in, is trapped (modals) and returns; Escape closes; AlertDialog focuses the safest action and ignores scrim clicks; overlays stay inside the viewport at 390/768/1024/1440; reduced motion removes transitions.
* Toast: announced region, error and action toasts persist (WCAG 2.2.1), dismiss button, not colour alone.
* DataTable: sorting with `aria-sort`, selection with indeterminate select-all through the shared Checkbox, row actions, loading/empty/error states, no page overflow on mobile.
* Keyboard models, visible focus, 44px targets on mobile; axe 0 violations in Light and Dark (unit tests while open; browser incl. contrast) without new exclusions; no hydration warnings or console errors.
* No new dependencies or tokens; guards pass; no backend, database, Docker, compose, CI, environment template, ADR, DESIGN-SYSTEM.md or landing-page changes; INC-18/19/20 updated, INC-24 and INC-25 recorded.

---

## T00-08 — Application Shell

**Priority:** P0

Implement:

```text
AppShell
Sidebar
TopBar
PageHeader
Breadcrumb
GlobalSearch
NotificationCenter
UserMenu
```

### T00-08 Update (2026-09-28)

**Status:** COMPLETED (merged to `main` via PR #10, `4a47f98`). Contracts: `docs/architecture/application-shell.md`.

**Scope (T00-08 implementation prompt and decision):** reusable shell (`frontend/src/shells/`) — ApplicationShell, AppHeader, AppSidebar/AppNavigation, MobileNavigation (Drawer), Breadcrumbs, PageHeader, PageContainer/PageContent, SkipNavigation, UserMenu (DropdownMenu + existing ThemeSelector), NotificationCenter (Popover, static data), CommandSearch (Dialog + Search, Ctrl+K), global ToastRegion mount, ShellLoading/ShellError — and the experience framework with route boundaries `/platform/*`, `/app/*`, `/student/*` and `/site/*` (navigation placeholders only). Names map to the list above as recorded in INC-28.

**Decision (marketing site):** Option A — the frozen marketing landing page is **not** integrated into Next.js; `/` stays the neutral root page; no ADR-0009 in T00-08; `index.html`, `app.js`, `styles.css`, the Dockerfile, its ignore file and ADR-0003 are unchanged (INC-26). `/site/*` follows the task prompt and differs from the architecture's `/sites/[site]/*` (INC-27).

**Acceptance criteria:**

* Shell components exist with tests (including axe) and documented contracts; 07A/07B/07C public APIs, tokens and the theme runtime unchanged; no new dependencies.
* Each experience has its own navigation configuration, layout (`noindex`), loading and error boundary; only configured pages exist, other paths 404; no tenant identifier in routes; no authentication, authorization or tenant resolution.
* Mobile drawer (focus in, Escape, focus restored), tablet rail, desktop sidebar with collapse; skip link; 44px targets on mobile; no horizontal overflow at 390/768/1024/1440.
* Light, Dark and System in every experience; axe 0 violations in Chromium (including contrast) with overlays open; no console/hydration errors; no external requests; reduced motion respected.
* `/` is the neutral root page; `/design-system` is 200 in development/test and 404 in production; landing-page hashes unchanged.
* No backend, database, Docker, compose, CI or environment changes.

---

## T00-09 — Responsive Foundation

**Priority:** P0

Support the design-system breakpoints.

Verify:

```text
390
640
768
1024
1280
1440+
```

### T00-09 Update (2026-09-29)

**Status:** COMPLETED (merged to `main` via PR #11, `265a06d`). Conventions and contracts: `docs/architecture/layout.md`.

**Scope (T00-09 implementation prompt):** reusable layout primitives in `frontend/src/design-system/layout/`: Container (content widths narrow / standard / wide / full), Stack, Inline, Grid/GridItem, Section, SplitLayout, ActionBar and Show (CSS-only responsive visibility). The breakpoint and spacing vocabulary reuses the approved tiers. The T00-08 shell is integrated without breaking its API: PageContainer uses the shared widths (plus `narrow`), and PageHeader actions wrap below a long title. Page conventions for dashboards, lists with filters and tables, detail pages and forms are documented. `/design-system` gains layout sections, and `/design-system/layout` shows a generic page in the real shell (development/test only). No business screens, and no new dependencies, breakpoints or tokens. Layout defects found in 07A/07C during verification were fixed without API changes (Kpi long values, ErrorState action wrapping, DataTable scroll-region focus ring). Naming and width notes: INC-29.

**Acceptance criteria:**

* Every primitive has behaviour tests (responsive configuration, wrapping, alignment, spacing, composition, semantics, long content) and passes axe; 07A/07B/07C and T00-08 public APIs are unchanged.
* No page-level horizontal overflow and no element spilling its box at 390/640/768/1024/1280/1440 in Light and Dark, including long names, e-mails, titles, breadcrumbs and large numbers.
* 44px mobile touch targets; the DOM order is the focus order; focus rings are visible and unclipped; reduced motion; System theme.
* Axe 0 violations in Chromium with no new exclusions; no console or hydration errors; no external requests.
* `/design-system` and `/design-system/layout` return 200 in development/test and 404 in production; the four experiences work; landing-page hashes are unchanged.
* No backend, database, Docker, compose, CI or environment changes.

---

## T00-10 — Accessibility Foundation

**Priority:** P0

Implement:

* keyboard navigation
* focus states
* semantic markup
* accessible form labels
* screen-reader support
* reduced motion
* contrast

### T00-10 Update (2026-09-29)

**Status:** COMPLETED (merged to `main` via PR #12, `94cb752`). Contract, conventions, checklist and known exceptions: `docs/architecture/accessibility.md`.

**Scope (T00-10 implementation prompt):** harden the existing tokens, components, shell and layouts against WCAG 2.2 AA without redesign, new dependencies, token changes or public API changes. This covers:

* Foundation: a global `:focus-visible` fallback and a reduced-motion safety net; test helpers (`expectNamedControls`, `tabSequence`, `expectFocusContained`, `expectFocusRing`, `expectHeadingOutline`); guards for focus replacement, reduced-motion pairing and positive `tabIndex`.
* Verified defect fixes: Pagination focus loss; Tabs ring clipping; Popover structure and focus containment; the FileUpload drop-zone name; persistent DataTable and Search status regions; Toast region F6; Breadcrumb touch targets.
* A cross-component accessibility contract suite, and a shell accessibility suite for all four experiences.

Remaining exceptions are documented: the React Aria Combobox axe rules while open, and INC-24.

**Acceptance criteria:**

* Keyboard operation, visible and unclipped focus, focus containment and return for every overlay, accessible names for every control, forms with required/invalid/error association and first-invalid focus, and live regions per convention — tested in jsdom and verified in Chromium.
* Light, Dark and System at 390/768/1024/1440 with axe 0 violations (no new exclusions), focus-ring contrast ≥ 3:1, 44px mobile targets (documented exceptions only) and reduced motion.
* Landmarks, a single `h1` and a valid heading outline on every experience; the skip link works.
* T00-06 … T00-09 regression suites pass; `/design-system` and `/design-system/layout` return 404 in production.
* No backend, database, Docker, compose, CI, environment, token or dependency changes; the marketing files are unchanged.

---

## T00-10A — Accessibility Token Correction (INC-24)

**Priority:** P0

**Status:** COMPLETED (merged to `main` via PR #13, `9f00b2e`).

**Objective:** Fix the Dark-mode `*-text` state colours that were below the WCAG 2.2 AA 4.5:1 text target on elevated surfaces (INC-24), without redesigning the colour system.

**Scope:**

* Measured first. Dark `*-400` text on `surface-elevated` / `surface-hover` was error 3.79, info 4.03, success 4.19 and warning 4.22; on `surface-selected` it was 4.00–4.45.
* No existing primitive is a lighter step of these hues. The user therefore approved a narrowly scoped exception: four derived `*-300` primitives, `mix(state-600, ice-100, t)`, used only by Dark `*-text` and the no-JavaScript fallback. Existing primitives, Light mappings, the Dark indicators and the `-strong` fills are unchanged.
* A shared contrast test helper (`design-system/testing/contrast.ts`, `expectContrast`) and a state text × every-surface matrix in `tokens.test.ts`, with the mappings pinned.
* A component regression suite, `components/state-text.test.tsx`: the pairs as components render them, in Light and Dark.
* A development-only showcase fixture, "Validation in overlays", so that Chromium measures state text inside a Dialog, Drawer and Popover.

**Acceptance criteria:**

* Every `*-text` token is ≥ 4.5:1 on every background and surface in Light and Dark. On `surface-elevated` in Dark: error 4.72, info 4.74, success 4.68, warning 4.63.
* Reverting a Dark `*-text` token to `*-400` fails the token and component tests.
* Chromium on the production image: state text in overlays is ≥ 4.5:1 in Light, Dark and System at 390/768/1024/1440, with axe 0 violations including contrast. The T00-08, T00-09 and T00-10 suites pass, and the Combobox exception is unchanged.
* No new dependencies, and no component API, layout, breakpoint, typography, spacing, backend, database, Docker, compose, CI, environment, ADR or marketing-file changes. INC-24 is `RESOLVED`.

---

# PHASE 01 — AUTHENTICATION & MULTI-TENANCY

## Objective

Establish the security and tenancy foundation before building business modules.

## Re-baseline (T01-00, approved 2026-09-30)

The T01-00 architecture review re-sequenced Phase 01 by dependency order (decision D1; INC-31).
- The API and database foundation come first.
- Audit comes before authentication.
- Tenancy comes before identity.
- MFA comes with platform identity.
- Support sessions move to Phase 02.

Decisions D1–D22 and their two approved amendments (D10, D14) are recorded in `docs/architecture/backend-foundation.md` §10, ADR-0010, ADR-0011 and ADR-0012.

Every slice is delivered as five commits:
1. foundation / schema;
2. domain / service;
3. API or UI;
4. security tests;
5. documentation.

| ID | Slice | Status |
|---|---|---|
| T01-00 | Architecture Review | COMPLETED (approved 2026-09-30) |
| T01-01 | Backend, Database & API Foundation | COMPLETED |
| T01-02 | Audit Foundation | COMPLETED |
| T01-03 | Tenancy Core (Tenant, Campus, isolation layers) | COMPLETED |
| T01-04 | Tenant Identity & Authentication | COMPLETED |
| T01-05 | Authorization & RBAC | COMPLETED |
| T01-06 | Platform Identity & MFA | COMPLETED (PR #25, merge `9fdb40a`) |
| T01-07 | Platform Administration Foundation (API) | COMPLETED (PR #27, merge `fe0b019`) |
| T01-08 | Tenant Administration Foundation (API) and development seed | COMPLETED (PR #29, merge `fd70d7d`) |
| T01-09 | Frontend Authentication & Session Integration | IN_PROGRESS (T01-09A tenant: COMPLETED, PR #30, merge `2af531b`; T01-09B platform/MFA UX: READY_FOR_REVIEW, B1 resolved; T01-09C tenant MFA UX: READY_FOR_REVIEW) |
| T01-10 | Security Verification Gate & Phase Close-out | READY_WITH_D18_DEFERRED (gate run locally 2026-10-07; D18 Chromium journeys not run) |

Dependencies:

```text
T01-01 → T01-02 → T01-03 → T01-04 → T01-05 ─┬→ T01-08 ─┐
                     └──────────→ T01-06 ───┼→ T01-07 ─┤
                                            └──────────┴→ T01-09 → T01-10
```

Mapping from the previous Phase 01 IDs (ADR-0004 and ADR-0005 cite the previous IDs):

| Previous ID | Now |
|---|---|
| T01-01 User Identity Model | T01-04 |
| T01-02 Authentication | T01-04 (API) and T01-09 (UI) |
| T01-03 MFA | T01-06 |
| T01-04 Platform Identity | T01-06 |
| T01-05 Tenant Model | T01-03 |
| T01-06 Campus Model | T01-03 |
| T01-07 Tenant Context | T01-01 (context plumbing), T01-03 (resolution), T01-04 (active tenant in the session) |
| T01-08 Role Model | T01-05 |
| T01-09 Authorization Engine | T01-05 |
| T01-10 Tenant Isolation | T01-03 (layers) and T01-10 (gate) |
| T01-11 Audit Foundation | T01-02 |
| T01-12 Security Tests | every slice, plus T01-10 |

Isolation layers for subsystems that do not exist yet (jobs, storage, search, analytics, AI) are tested by the task that introduces each of them; the route-coverage test enforces this.

---

## T01-00 — Architecture Review

**Status:** COMPLETED (read-only review; approved 2026-09-30 with amendments to D10 and D14).

Output: the T01 architecture, the data model, the authentication, RBAC and isolation design, the test strategy, the task breakdown and decisions D1–D22 (`docs/architecture/backend-foundation.md` §10).

---

## T01-01 — Backend, Database & API Foundation

**Priority:** P0

**Status:** COMPLETED (merged to `main` by PR #14, merge commit `42bc8b1`).

**Objective:** Provide the infrastructure every backend module depends on, with no business tables and no authentication.

**Implemented:**

* SQLAlchemy 2.0 async, asyncpg, Alembic (baseline `0001`), UUIDv7 identifiers, and the Base / timestamp / version mixins.
* The application-role engine, and one transaction per request committed before the response, with `SET LOCAL` context for RLS.
* `RequestContext`, the error envelope and handlers, JSON logging with redaction, and request IDs.
* The five realm routers with deny-by-default guards, response and pagination conventions, and OpenAPI operation IDs.
* The `migrate` service, the test database and CI PostgreSQL.
* import-linter contracts.
* ADR-0010 … ADR-0012.

**Acceptance criteria:**

* Migrations upgrade, downgrade and upgrade cleanly; `alembic check` shows no drift; runtime roles cannot change `alembic_version` or create objects.
* A request commits on success, rolls back on error, and never reports success when the commit fails; context never leaks between transactions.
* Every `/api` route is guarded by the realm that owns its prefix (meta-test); authenticated realms and webhooks return 401 before validation.
* Errors use the envelope without input values, SQL or stack traces; every response carries a request ID; logs are JSON, redacted and free of query strings.
* No authentication, tenant, user or business tables; no frontend, token or marketing changes.

---

## T01-02 — Audit Foundation

**Priority:** P0

**Status:** COMPLETED (merged to `main` by PR #16, merge commit `91d0180`).

**Objective:** `audit_events` (append-only grants, RLS, redacted metadata), the audit writer and the security-event writer (D22), with the locked decisions 1.1–1.9 of the T01-02 specification recorded in ADR-0013.

**Implemented:**

* `app/core/audit/`: the `AuditEvent` model and migration `0002`:
  * one mixed-scope table;
  * nullable `tenant_id` without a foreign key;
  * categories `security`, `admin`, `data_access` and `domain`;
  * code-declared event types, a generic target and bounded JSONB metadata;
  * indexes for tenant reads, platform reads and request correlation.
* Privileges and append-only enforcement:
  * `mti_app` has SELECT and INSERT only, and `mti_readonly` has no access;
  * triggers reject UPDATE, DELETE and TRUNCATE for every role.
* The first RLS policies:
  * the platform realm reads all rows, and the tenant realm reads its own tenant only;
  * inserts are bound to the trusted tenant (NULL-safe) and realm.
* `write_audit_event`: in the request transaction, on the request connection.
* `record_security_event`: an in-memory buffer per request. The realm guard (now a function-scoped yield dependency) flushes it through `context_transaction` after the request connection is released and before the response; a failed flush is logged safely and swallowed.
* Metadata validation, limits and deterministic redaction of sensitive keys.
* ADR-0013 and INC-35.

**Acceptance criteria:**

* Upgrade and downgrade are clean, with no orphaned objects; `alembic check` shows no drift; migration tests derive the head.
* UPDATE, DELETE and TRUNCATE are denied to `mti_app`, the triggers also reject them for the owner, and `mti_readonly` cannot read.
* RLS matrix: the tenant reads its own rows; reads of other tenants, platform rows and other realms return nothing; inserts A→A and NULL→NULL are allowed; A→B, A→NULL and NULL→A are denied.
* An audit event commits and rolls back with its mutation on one connection.
* A security event survives a rollback and is flushed after the connection is released, on a one-connection pool.
* A failed flush leaves the response unchanged and logs no metadata.
* No authentication, tenants, users, outbox, queue or retry; import contracts kept.

---

## T01-03 — Tenancy Core

`tenants`, `campuses`, `TenantScopedMixin`, the tenant-scoped repository, the ORM auto-filter, RLS policies, composite foreign keys, `system_context`, and the tenant status access policy (D15). Isolation tests at the database and repository layers.

**Priority:** P0

**Status:** COMPLETED (merged to `main` by PR #19, merge commit `f602631`).

**Implemented** (locked decisions recorded in ADR-0014):

* Migration `0003`:
  * `tenants`: UUIDv7 `id`, `name`, `status` (CHECK on the eight lifecycle states; new tenants start in `TRIAL`), timestamps, `version`.
  * `campuses`: `TenantScopedMixin`, a required upper-case `code` unique per tenant, `UNIQUE (tenant_id, id)`, and an FK to `tenants` with `ON DELETE RESTRICT`.
  * Privileges: `mti_app` SELECT/INSERT/UPDATE (no DELETE), `mti_readonly` SELECT under RLS.
  * RLS, enabled but not forced:
    * `campuses`: realm-agnostic `tenant_id = app.tenant_id`;
    * `tenants`: platform and system read all and write, any other context reads only its own row.
* `app/core/tenancy`:
  * `TenantScopedMixin` and `tenant_foreign_key()`;
  * the ORM filter (`with_loader_criteria`, aliases, joins, bulk UPDATE/DELETE; fails closed);
  * `TenantScopedRepository` (no delete; another tenant's row is a 404);
  * `system_context` (system realm, refused inside HTTP).
  * The context published by `context_transaction` is also recorded in `session.info`; `context_scope()` binds a context outside HTTP.
* `app/modules/tenants`:
  * the `Tenant` model;
  * lifecycle rules: suspend TRIAL/ACTIVE/PAST_DUE → SUSPENDED, reactivate SUSPENDED → ACTIVE;
  * status access policy: tenant/student TRIAL, ACTIVE, PAST_DUE; public TRIAL, ACTIVE.
* `app/modules/institute`: the `Campus` model.
* ADR-0014; INC-36 … INC-41.

**Acceptance criteria:**

* Migration:
  * `0003` upgrades, downgrades to `0002` with no T01-03 objects left, and upgrades again;
  * `alembic check` shows no drift;
  * the tests derive the head.
* Constraints:
  * the status CHECK accepts exactly the eight states;
  * the campus code is required, upper case and unique per tenant;
  * a tenant with campuses cannot be deleted;
  * `UNIQUE (tenant_id, id)` exists.
* Privileges: the runtime roles have no DELETE, `mti_readonly` has no writes, both stay NOBYPASSRLS and own nothing.
* RLS (raw SQL):
  * each tenant sees only its campuses;
  * no tenant context sees nothing;
  * cross-tenant insert, update and move are rejected;
  * only platform and system read all tenants and write them.
* Application layers, also tested as the owner, which bypasses RLS:
  * the ORM filter and the repository isolate tenants on their own;
  * tenant-scoped ORM queries without a tenant raise;
  * `add()` stamps the trusted tenant and rejects another.
* Composite foreign keys reject cross-tenant links.
* `system_context`:
  * publishes the system realm and tenant to both PostgreSQL and the ORM;
  * leaks nothing after success or failure;
  * restores nested contexts;
  * is refused inside an HTTP request.
* The T01-02 tests pass unchanged. There is no API, authentication, memberships, provisioning, frontend, dependency or `audit_events` change.

### Critical Requirement

Never trust arbitrary client-supplied tenant IDs for authorization.

---

## T01-04 — Tenant Identity & Authentication

`users` (identity) separated from `user_credentials` (ADR-0010, D14 amended); memberships and campus scope; `user_sessions`; login, logout, session, and tenant and campus switching; CSRF; rate limits and lockout; password reset and invitation acceptance (with an invitation preview) with post-commit email (D10 amended). UI AUTH-01 … AUTH-03 and AUTH-05 … AUTH-08 follows in T01-09.

Contract: locked decisions D04 (campus selection) and D19 (invitation preview) in `docs/architecture/identity-authentication.md`; UI contract in `docs/ui/T01-04-IDENTITY-AUTHENTICATION-UI.md`.

**Priority:** P0

**Status:** COMPLETED (merged to `main` by PR #20, merge commit `daa6526`).

**Implemented** (decisions D01–D19, ADR-0015, `docs/architecture/identity-authentication.md`):

* Migration `0004`: `users`, `user_credentials`, `tenant_memberships`, `membership_campuses`, `user_sessions`, `password_reset_tokens`, `user_invitations`; composite foreign keys; no DELETE; no read-only access; RLS on every table with equality-matched pre-authentication lookup keys (no `SECURITY DEFINER`).
* Services: sign-in (rate limits, dummy-hash timing, lockout, rehash, membership discovery, D04 campus resolution, HMAC-only session, rotation), per-request session re-validation, session read, institute switch (rotates), campus switch, sign-out, password reset (generic request, 30-minute single-use token, sessions revoked), invitation preview and acceptance (D19).
* API: `/api/v1/auth/{login,logout,password-reset,password-reset/confirm,invitations/preview,invitations/accept}` (anonymous, same-origin check) and `/api/v1/session` (`GET`, `PUT /tenant`, `PUT /campus`; `Access.SESSION`, CSRF token).
* Infrastructure: Redis rate limiter (`auth:` namespace, fail closed, `Retry-After`), `TRUSTED_PROXY_HOPS`, `EmailSender` (SMTP + fake, post-response), `APP_BASE_URL`, `ARGON2_*`, `SMTP_TIMEOUT_SECONDS`; compose `api` uses Redis and Mailpit; CI starts Redis.
* Security events for every authentication outcome (no secrets in metadata).

**Acceptance criteria:**

* Migration `0004` upgrades, downgrades to `0003` without leftovers and upgrades again; `alembic check` shows no drift.
* RLS matrix (raw SQL): credentials never visible to a tenant context; each lookup key reaches exactly its row; memberships by active tenant or own user; identities created only by the system realm.
* One generic 401 for every sign-in failure; lockout 1/5/15/60 minutes; 20/IP and 10/account rate limits with `Retry-After`; fail closed without Redis.
* Sessions re-validated on every request; rotation on sign-in and institute switch; campus semantics per D04; tenant and campus IDOR answer 404.
* Password reset and invitations per the UI contract; tokens never in paths, logs or audit rows; email after commit and response, failures do not roll back.
* All T01-01, T01-02 and T01-03 tests pass; import contracts kept; no frontend changes.

---

## T01-05 — Authorization & RBAC

Permission registry, tenant roles and templates, `role_permissions` with the realm foreign key, membership roles, `authorize()` and `require_permission`, and the route-coverage meta-test extended to permissions (ADR-0011).

Architecture review: decisions D-B1 (campus authorization semantics), D-B2 (system roles immutable to tenants), D-B3 (permission identity `(realm, code)` and the T01 baseline) and D-B4 (migration-based permission sync) are locked. UI contract: `docs/ui/T01-05-AUTHORIZATION-RBAC-UI.md` (AUTHZ-01, RESOURCE-01/02, NAV-01/02, SESSION-01, CAMPUS-01, DASH-01; built in T01-09).

Must support:

```text
Platform scope
Tenant scope
Campus scope where required
Resource permissions
```

**Priority:** P0

**Status:** COMPLETED (PR #21, merge commit `ee956e5`).

**Implemented** (decisions D-B1 … D-B4, ADR-0016, `docs/architecture/authorization.md`):

* **Permission registry:** `(realm, code)` identity, `resource.action` codes and no wildcards, `TENANT` or `CAMPUS` scope for tenant permissions, and a fail-closed step-up hook. The T01 baseline is declared in the modules' `permissions.py`: 15 tenant and 10 platform permissions.
* **Migration `0005`:**
  * `permissions` (read-only at runtime, seeded from a frozen copy), `roles`, `role_permissions` (generated `permission_realm` inside the catalogue foreign key) and `membership_roles`;
  * RLS per tenant, and triggers that keep system roles immutable for every database role;
  * `INSTITUTE_OWNER` and `ADMIN` cloned for existing tenants, with no assignments.
* **Effective permissions:** the union of the roles, resolved with the session. Tenant-wide permissions are kept only with all-campus access (D-B1). They are carried by `RequestContext`.
* **`authorize` and `require_permission`:** `authorize(context, permission, resource=None)` answers 401, 403, or 404 for another tenant's or an unpermitted campus's resource. `require_permission` records `authz.denied`.
* **Session:** `permissions` (sorted) and `roles` (`{name, is_system}`) for the active institute.
* **Route coverage:** every API route has one permission or a reviewed `public_route` / `authenticated_only` exemption.
* **Access service:** custom roles and role assignment, with no escalation, system-role refusal, optimistic versions and audit events. The API follows in T01-08.
* **Platform roles:** the platform role map in code (`SUPER_ADMIN`, `SECURITY_AUDIT_ADMIN`; the others empty).

**Acceptance criteria:**

* Migration `0005` upgrades, downgrades to `0004` without leftovers and upgrades again; no model drift; the database catalogue and the system role clones equal the code.
* D-B2 is refused by the database for tenant contexts, the system realm and the table owner. A tenant role cannot hold a platform, unknown or wildcard permission.
* The HTTP matrix holds:
  * 401 without a session; 403 without the permission;
  * 404 for another tenant's or an unpermitted campus's resource, identical to a missing one;
  * tenant-wide permissions refused to campus-restricted members;
  * the active campus is not the authorization boundary.
* The session exposes sorted permissions and roles without IDs. A tenant switch changes them, a campus switch does not, and a role change is visible on the next read.
* The route-coverage meta-test passes and detects an unprotected route.
* All T01-01 … T01-04 tests pass; import contracts are kept; there are no frontend changes.

**Deviations:**

* Platform role assignment storage is deferred to T01-06, because there are no platform users before then.
* Role administration is service-only until T01-08.
* Feature entitlements are not checked (Phase 15).

---

## T01-06 — Platform Identity & MFA

`platform_users` separated from `platform_user_credentials`; platform roles and sessions; TOTP and recovery codes (mandatory for platform users, optional enrolment for tenant users); a step-up hook; `DATA_ENCRYPTION_KEY` (ADR-0012). UI PLAT-01 and PLAT-02 follow in T01-09.

Architecture review approved; decisions **D6-1 … D6-5 are locked** in `docs/architecture/platform-identity.md`:

* **D6-1 First administrator.** The `create-platform-admin` system-realm CLI creates the first `SUPER_ADMIN`, who must enrol MFA at first sign-in. The CLI never exposes the password and is also the break-glass path.
* **D6-2 Password recovery.** Self-service email reset on the T01-04 model. A reset never bypasses MFA.
* **D6-3 Lost MFA device.** Another `SUPER_ADMIN` resets it under `platform_user.update` (no new permission). It needs step-up and a reason, is audited, revokes the user's sessions and forces re-enrolment.
* **D6-4 MFA mechanisms.** TOTP plus recovery codes only. SMS and email OTP, OTP resend, trusted devices and WebAuthn/passkeys are deferred; the model stays extensible.
* **D6-5 Step-up.** `tenant.suspend`, `tenant.reactivate`, `platform_user.create` and `platform_user.update` require step-up: a 10-minute window, otherwise `403 STEP_UP_REQUIRED`, enforced in `authorize()`.
* **QR code.** No QR dependency; manual setup with the secret and the `otpauth://` URI.

**Priority:** P0

**Status:** COMPLETED (merged to `main` by PR #25, merge commit `9fdb40a`).

**Implemented** (locked decisions D6-1 … D6-5 in `docs/architecture/platform-identity.md`; ADR-0017):

* **Migration `0006`:** platform users, credentials, roles, sessions, MFA factors, recovery codes and reset tokens; tenant `user_mfa_factors`, `user_recovery_codes` and MFA-pending sessions. RLS keyed on the platform realm, `app.platform_user_id` and equality-matched lookup keys; tenant contexts and `mti_readonly` see nothing; no `SECURITY DEFINER`.
* **Security primitives:** AES-256-GCM with `DATA_ENCRYPTION_KEY` and row-bound associated data; RFC 6238 TOTP with replay protection; ten single-use HMAC recovery codes; a realm-neutral `MfaStore`.
* **Platform API:** sign-in, MFA-pending session, enrolment (secret and `otpauth://` URI, no QR), verification, recovery codes, session, step-up, recovery-code regeneration, password reset; `auth:platform` rate limits, lockout, CSRF and the same-origin check.
* **Step-up (D6-5):** `authorize()` requires an MFA verification within 10 minutes for the four step-up permissions, otherwise `403 STEP_UP_REQUIRED`.
* **Lost-MFA reset (D6-3):** service capability under `platform_user.update` with step-up and a reason; the route belongs to T01-07.
* **Tenant MFA:** opt-in enrolment, MFA-pending sign-in, recovery codes and removal with a current code; users without MFA are unaffected.
* **Bootstrap (D6-1):** `python -m app.cli create-platform-admin`, with `--break-glass --reason`.
* **Audit:** `platform.auth.*`, `platform.mfa.*` and tenant `auth.mfa.*` security events, without secrets.

**Acceptance criteria:**

* Migration `0006` upgrades, downgrades to `0005` and upgrades again; no model drift.
* Tenant and platform sessions, cookies, credentials and factors never cross realms; a platform session sees no tenant rows.
* Generic sign-in and reset responses, the dummy hash, lockout and rate limits hold for the platform realm.
* TOTP replay, brute force, pending-session restrictions, session rotation and secret encryption are tested; the secret and codes never appear in later responses, logs or audit metadata.
* Step-up, the MFA reset and the bootstrap CLI behave as locked in D6-1 … D6-5.
* All T01-01 … T01-05 tests pass; route coverage passes; there are no frontend changes.

**Deviations:**

* The MFA reset has no HTTP route until T01-07 (platform user management).
* Step-up and recovery-code regeneration exist for the platform realm only; no tenant permission requires step-up yet.
* No key re-encryption job; a retired key stays in `DATA_ENCRYPTION_RETIRED_KEYS` until one exists.

---

## T01-07 — Platform Administration Foundation (API)

Tenant provisioning (tenant, primary campus, cloned roles, owner invitation); tenant list and detail; suspend and reactivate; platform users; platform audit read. The screens remain in Phase 02.

Architecture review approved; decisions **D7-1 … D7-10 are locked** in `docs/architecture/platform-administration.md`:

* **D7-1 Provisioning write path (INC-39).** A named provisioning transaction publishes only the new tenant's server-generated ID as the trusted tenant; one module only, statically enforced; a narrow `users` insert policy for the owner.
* **D7-2 Platform user administration.** A target-key transaction opened after `authorize()`; the T01-06 own-row rules stay.
* **D7-3 Onboarding.** A dedicated `platform_user_invitations` table (HMAC, single use, expiring); MFA enrolment at first sign-in.
* **D7-4 Suspend and reactivate.** `platform_user.suspend` and `platform_user.reactivate` require step-up (extends D6-5), with a reason and the version; suspension revokes platform sessions.
* **D7-5 Self-protection.** No action on one's own account; the last active `SUPER_ADMIN` is kept, under a row lock.
* **D7-6 Tenant suspension.** Revokes sessions whose active institute is the tenant (`tenant_suspended`), in the same transaction.
* **Defaults D7-7 … D7-10.** Owner with an existing account, owner invitation resend, platform audit read, no `unscoped()` (INC-38 open).

**Priority:** P0

**Status:** COMPLETED (merged to `main` by PR #27, merge commit `fe0b019`).

**Implemented** (ADR-0018):

* **Migration `0007`:** `platform_user_invitations`, `tenants.owner_membership_id`, revoke reasons `tenant_suspended` and `admin_suspended`; existing policies altered in place with one narrow, equality-matched term per key (provisioning, suspension target, owner, administration target, invitation token).
* **Tenants API:** list, detail (with the primary administrator), provisioning in one transaction (tenant, campus, system roles, owner membership and invitation), suspend and reactivate (step-up, reason, version; suspension revokes the institute's sessions), owner invitation resend.
* **Platform users API:** directory, create by invitation, update (name, roles), suspend and reactivate (step-up; sessions revoked), invitation resend, MFA reset (D6-3); public invitation preview and acceptance.
* **Self-protection and the last guardian (D7-5)**, with an advisory lock against concurrent changes.
* **Platform audit read** with filters and pagination.
* **Static boundaries:** the tenant scope keys and the administration key each have one publishing module; no `unscoped()`.

**Acceptance criteria:**

* Migration `0007` upgrades, downgrades to `0006` and upgrades again; no model drift.
* Each new key opens only its target; tenant contexts and the read-only role gain nothing.
* Provisioning produces a working institute whose owner accepts through the T01-04 flow; it never touches another tenant.
* Step-up, reasons, versions, self-protection, session revocation and invitation single use are enforced and audited.
* All T01-01 … T01-06 tests pass; route coverage passes; there are no frontend changes.

**Deviations** (ADR-0018 §9 and Consequences):

* Provisioning also needs narrow terms on `roles_insert` and `role_permissions_insert` (system roles are system-realm-only in 0005).
* Guardian changes are serialised by an advisory lock, not a row lock.
* Added `tenants.owner_membership_id` and the platform revoke reason `admin_suspended`.
* No provisioning idempotency key (T02-12); no MFA or last sign-in in the platform user directory.

---

## T01-08 — Tenant Administration Foundation (API)

Campuses, members (invite, suspend, revoke), member roles and campus scope, custom roles, tenant audit read, and the development seed (D16). The screens remain in Phase 03.

Architecture review approved; decisions **D8-1 … D8-4 are locked** in `docs/architecture/tenant-administration.md`:

* **D8-1 New invitee identity.** `INVITED` identities of new invitees are created through a narrow invitee key published only by the tenant invitation module after authorization; existing accounts are reused unchanged; `DISABLED` → `409`; no tenant-realm-wide `users` INSERT. Migration 0008: `users_insert` term.
* **D8-2 Tenant audit visibility.** Tenant audit reads return only tenant-realm events of the trusted tenant, enforced by `audit_events_tenant_read`; platform-written events, including provisioning, remain platform-only. Migration 0008: policy change.
* **D8-3 Member lifecycle.** `INVITED → ACTIVE` (acceptance), `ACTIVE ⇄ SUSPENDED` (`member.suspend`), `INVITED | ACTIVE | SUSPENDED → REVOKED` (`member.revoke`, with open invitations), `REVOKED → INVITED` (re-invitation of the same row); versioned; no global session revocation (per-request membership re-check). No migration.
* **D8-4 Self-protection and last owner.** No suspension, revocation, campus-scope change or role removal on one's own membership (`403`); at least one `ACTIVE` `INSTITUTE_OWNER` membership per institute (`409`), serialised by a per-tenant transaction advisory lock. No migration.

**Priority:** P0

**Status:** COMPLETED (merged to `main` by PR #29, merge commit `fd70d7d`).

**Implemented** (ADR-0019):

* **Migration `0008`:** the `users_insert` invitee-key term (D8-1), `audit_events_tenant_read` restricted to tenant-realm events (D8-2), and `membership_campuses.removed_at` with UPDATE under the tenant rule (campus scope without DELETE, T01-04 D16).
* **Members API:** list and detail, invitation of new or existing accounts with initial roles and campus scope, resend, suspend, reinstate, revoke, re-invite (same row), campus scope, role assignment and removal; versioned; no session revocation.
* **Owner protection:** self-protection (`403`) and the last active owner (`409`) under a per-tenant advisory lock.
* **Roles API** over the access service, the permission catalogue, campuses (list, detail, create, rename) and the read-only institute summary.
* **Tenant audit read** (`GET /api/v1/audit-events`).
* **Development seed (D16):** `python -m app.cli seed` with `database/seeds/dev.json`.

**Acceptance criteria:**

* Migration `0008` upgrades, downgrades to `0007` (removed campuses are not re-granted) and upgrades again; no model drift.
* The invitee key admits one `INVITED` identity only; tenant readers never see platform-written events; identity rows are never deleted.
* Cross-tenant and cross-campus access is `404`; tenant-wide administration needs all-campus access; no escalation through invitations or role changes.
* Lifecycle transitions, versions, self-protection and the last owner (including concurrent changes) behave as locked.
* All T01-01 … T01-07 tests pass; route coverage passes; there are no frontend changes.

**Deviations** (ADR-0019 §10):

* Campus scope uses `membership_campuses.removed_at` instead of DELETE (T01-04 D16).
* The last-owner `409` on owner-role removal applies to callers holding every owner permission; Administrators are refused earlier by the no-escalation rule (`403`).
* Campus status and archival remain undefined (INC-40).

---

## T01-09 — Frontend Authentication & Session Integration

The same-origin API proxy, session helpers, the AUTH-01 … AUTH-05, PLAT-01 and PLAT-02 pages on the T16 template, guarded shells, tenant and campus switchers, role-aware navigation, and logout.

The readiness review (2026-10-03) found no UX contract for the platform and MFA screens (blocker **B1**). The task is split (option b, extended to three parts by T01-09B D9B-9):

* **T01-09A — Tenant authentication & session.** Built against the frozen UI contracts `docs/ui/T01-04-IDENTITY-AUTHENTICATION-UI.md` and `docs/ui/T01-05-AUTHORIZATION-RBAC-UI.md`: the same-origin proxy (`app/api/[...path]`, browser address as one `X-Forwarded-For` entry for `TRUSTED_PROXY_HOPS=1`), the typed API client and server/client session helpers, AUTH-01 … AUTH-03 and AUTH-05 … AUTH-08 on `AuthenticationTemplate` (T16), tenant MFA verify and recovery (the sign-in step only), the guarded `/app` shell, `TenantContext`, `CampusSwitcher`, the session `UserMenu`, the requirement map, `can()`, `PermissionGate`, AUTHZ-01, RESOURCE-01/02, NAV-01/02, DASH-01 and the T01-05 §11 error matrix.
  **Status:** COMPLETED (implementation `a4a3cfe`; merged to `main` by PR #30, merge commit `2af531b`). The out-of-repository Chromium journeys J1–J10 (D18) were not run.
* **T01-09B — Platform Identity & MFA UX.** Built against the frozen contract `docs/ui/T01-09B-PLATFORM-IDENTITY-MFA-UI.md` (readiness review 2026-10-07, `READY_FOR_IMPLEMENTATION`; **B1 resolved**; decisions D9B-1 … D9B-12): PLAT-01, PLAT-02, PAUTH-01 … PAUTH-07 (forgot and reset password, invitation acceptance, MFA set-up, recovery codes, session ended, step-up), the guarded platform console with permission-aware navigation, and a partial PLAT-52 "Sign-in security" (**D9B-8 accepted**). MFA-pending states are in-memory steps of `/platform/login` (D9B-2); the proxy forwards only the called realm's session cookie (D9B-10). Tenant MFA enrolment moved to T01-09C (**D9B-9 accepted**).
  **Status:** READY_FOR_REVIEW (implemented and verified on `feat/T01-09B-platform-identity-mfa-ux`; committed, not pushed, not merged). The out-of-repository Chromium journeys were not run.
* **T01-09C — Tenant MFA UX.** Opt-in TOTP set-up, recovery codes shown once and turning it off with a current code for tenant users, on the existing T01-06 tenant endpoints (`/api/v1/session/mfa/enrolment`, `/enrolment/confirm`, `/remove`), reusing the T01-09B components; the tenant sign-in MFA step (T01-09A) is unchanged and now covered by additional tests. Contract `docs/ui/T01-09C-TENANT-MFA-UI.md` (D9C-1 … D9C-6): the personal **Sign-in security** page `/app/account/security`, reached from the account menu (D9C-1). Completes D9B-9. Backend limitations kept: no tenant recovery-code count or regeneration, no tenant step-up, no institute MFA policy.
  **Status:** READY_FOR_REVIEW (implemented and verified on `feat/T01-09B-platform-identity-mfa-ux` as a second local commit after T01-09B; not pushed, not merged). The out-of-repository Chromium journeys were not run.

---

## T01-10 — Security Verification Gate

The cross-tenant, realm, IDOR and RBAC matrix across every route, the session-security suite, and the Phase 01 close-out.

Must prove:

```text
Tenant A cannot access Tenant B.
A Tenant Admin cannot perform Platform Admin operations.
An unauthenticated user cannot access protected APIs.
```

**Status:** READY_WITH_D18_DEFERRED (2026-10-07, run locally on `feat/T01-09B-platform-identity-mfa-ux`; not pushed). No BLOCKER, HIGH or MEDIUM finding remains. One genuine defect was fixed in remediation commits `f55ff50` and `71f3d87`: three synthetic leak-check fixtures from T01-09B/C were flagged by the CI gitleaks scan and are now allowlisted by exact path and value. The second commit also covers the self-test lines that name those values. The three proofs above are covered by the backend security and integration suites (route coverage, realm guards, tenancy isolation, platform boundaries). Those suites passed in CI on `main` (`2af531b`), and the backend is unchanged since. The out-of-repository D18 Chromium journeys were not run (environment/runtime limitation). Details: DEVELOPMENT-STATUS.md, T01-10.

---

# PHASE 02 — PLATFORM CONTROL PLANE

## Objective

Build the MTI 360 SaaS administration layer.

---

## T02-01 — Platform Shell

Implement platform-specific shell.

Context:

```text
MTI 360 Platform
All Tenants
```

---

## T02-02 — Platform Login

UI:

```text
PLAT-01
PLAT-02
```

---

## T02-03 — Platform Dashboard

UI:

```text
PLAT-03
```

KPIs:

* Total Tenants
* Active Tenants
* Trial Tenants
* MRR
* ARR
* Active Users
* Students
* Leads
* AI Executions
* Communication Volume
* Storage
* Failed Jobs
* Support Tickets

---

## T02-04 — Tenant Management

Implement:

```text
PLAT-04
PLAT-05
PLAT-06
PLAT-07
PLAT-08
PLAT-09
PLAT-10
```

Features:

* tenant list
* tenant 360
* creation
* onboarding
* status
* usage
* health
* support access

---

## T02-05 — Tenant Lifecycle

Implement:

```text
PROSPECT
TRIAL
PROVISIONING
ACTIVE
PAST_DUE
SUSPENDED
CANCELLED
DEACTIVATED
```

Implement valid state transitions.

---

## T02-06 — Plans & Pricing

UI:

```text
PLAT-11
PLAT-16
```

Implement:

* plans
* features
* entitlements
* limits

---

## T02-07 — Subscription Management

UI:

```text
PLAT-12
PLAT-13
PLAT-14
PLAT-15
```

Implement:

* subscriptions
* invoices
* payments
* coupons
* trials

---

## T02-08 — Usage Metering

UI:

```text
PLAT-17
```

Track:

* users
* students
* storage
* communications
* AI executions
* other billable metrics

---

## T02-09 — Communication Providers

UI:

```text
PLAT-18
```

Support provider configuration through secure abstractions.

---

## T02-10 — Platform AI

UI:

```text
PLAT-19
PLAT-20
PLAT-21
```

Implement:

* AI providers
* models
* cost
* usage
* global guardrails

---

## T02-11 — Platform Integrations

UI:

```text
PLAT-22
```

---

## T02-12 — Provisioning Engine

UI:

```text
PLAT-23
PLAT-49
```

Provision:

```text
Tenant
Admin
Campus
Features
Defaults
Branding
```

---

## T02-13 — Background Jobs

UI:

```text
PLAT-24
```

Implement job monitoring.

---

## T02-14 — Platform Health

UI:

```text
PLAT-25
PLAT-26
PLAT-27
```

---

## T02-15 — Support

UI:

```text
PLAT-28
PLAT-29
PLAT-30
```

Implement controlled support sessions.

---

## T02-16 — Platform Notifications

UI:

```text
PLAT-31
PLAT-32
```

---

## T02-17 — Feature Flags

UI:

```text
PLAT-33
```

---

## T02-18 — Platform Settings

UI:

```text
PLAT-34
```

---

## T02-19 — Platform Security

UI:

```text
PLAT-35
PLAT-36
PLAT-37
PLAT-38
PLAT-39
PLAT-40
```

---

## T02-20 — Platform Analytics

UI:

```text
PLAT-41
PLAT-42
PLAT-43
PLAT-44
PLAT-45
PLAT-46
```

---

## T02-21 — Platform Credentials

UI:

```text
PLAT-47
```

Secrets must never be exposed in UI.

---

## T02-22 — Platform Branding / Domains

UI:

```text
PLAT-48
```

---

## T02-23 — Platform Administrators

UI:

```text
PLAT-50
PLAT-51
PLAT-52
PLAT-53
```

---

# PHASE 03 — TENANT FOUNDATION

## Objective

Build the operational foundation for each MTI.

---

## T03-01 — Tenant Shell

Implement tenant navigation and context.

---

## T03-02 — Institute Profile

UI:

```text
ADMIN-01
ADMIN-02
```

---

## T03-03 — Campus Management

UI:

```text
ADMIN-03
ADMIN-04
```

---

## T03-04 — Tenant Users

UI:

```text
ADMIN-05
ADMIN-06
```

---

## T03-05 — Tenant Roles

UI:

```text
ADMIN-07
```

---

## T03-06 — Tenant Integrations

UI:

```text
ADMIN-08
```

---

## T03-07 — Tenant AI Configuration

UI:

```text
ADMIN-09
```

---

## T03-08 — Notifications

UI:

```text
ADMIN-10
```

---

## T03-09 — Tenant Billing

UI:

```text
ADMIN-11
```

---

## T03-10 — Tenant Audit

UI:

```text
ADMIN-12
```

---

## T03-11 — Tenant Settings

UI:

```text
ADMIN-13
ADMIN-14
```

---

# PHASE 04 — ADMISSIONS

## Objective

Build the complete student acquisition-to-admission journey.

```text
Lead
 ↓
Counselling
 ↓
Application
 ↓
Documents
 ↓
Review
 ↓
Approval
 ↓
Student
```

---

## T04-01 — Lead Foundation

UI:

```text
GROW-07
GROW-08
GROW-09
GROW-10
```

Implement:

* lead source
* lead
* lead status
* lead owner
* lead activity

---

## T04-02 — Lead Pipeline

UI:

```text
ADM-02
```

Implement Kanban/pipeline.

---

## T04-03 — Counselling

UI:

```text
ADM-03
ADM-04
```

Implement:

* counselling queue
* counselling record
* follow-up
* outcome

---

## T04-04 — Applications

UI:

```text
ADM-05
ADM-06
ADM-07
```

Implement:

* application
* applicant
* course preference
* status
* draft
* submission

---

## T04-05 — Application Review

UI:

```text
ADM-08
```

---

## T04-06 — Document Verification

UI:

```text
ADM-09
```

Implement:

* document upload
* verification
* rejection
* remarks

---

## T04-07 — Admission Approval

UI:

```text
ADM-10
```

---

## T04-08 — Student Creation

UI:

```text
ADM-11
ADM-12
ADM-13
ADM-14
ADM-15
```

Implement student profile and admission information.

---

## T04-09 — Admissions Communication

Integrate:

```text
WhatsApp
Email
SMS
```

for appropriate admissions events.

---

## T04-10 — Admissions Tests

Test:

* lead conversion
* application creation
* document verification
* approval
* student creation
* authorization
* tenant isolation

---

# PHASE 05 — ACADEMICS

## Objective

Implement course-to-certificate academic operations.

```text
Course
 ↓
Batch
 ↓
Timetable
 ↓
Attendance
 ↓
Training
 ↓
Examination
 ↓
Certificate
```

---

## T05-01 — Courses

UI:

```text
ACA-01
ACA-02
ACA-03
ACA-04
```

---

## T05-02 — Curriculum

Implement course curriculum structure.

---

## T05-03 — Batches

UI:

```text
ACA-05
ACA-06
ACA-07
```

---

## T05-04 — Timetable

UI:

```text
ACA-08
ACA-09
```

---

## T05-05 — Attendance

UI:

```text
ACA-10
ACA-11
```

---

## T05-06 — Faculty

UI:

```text
ACA-12
ACA-13
ACA-14
```

---

## T05-07 — Training

UI:

```text
ACA-15
ACA-16
ACA-17
ACA-18
```

---

## T05-08 — Examinations

UI:

```text
ACA-19
ACA-20
ACA-21
ACA-22
```

---

## T05-09 — Results

Implement result processing and publishing.

---

## T05-10 — Certificates

UI:

```text
ACA-23
ACA-24
ACA-25
```

---

## T05-11 — Academic Reports

UI:

```text
ACA-26
ACA-27
```

---

## T05-12 — Academic Tests

Test:

* course enrollment
* batch allocation
* attendance
* training
* examinations
* results
* certificates

---

# PHASE 06 — FINANCE

## Objective

Build tenant financial operations.

```text
Fee Structure
 ↓
Invoice
 ↓
Payment
 ↓
Outstanding
 ↓
Refund
 ↓
Reports
```

---

## T06-01 — Finance Foundation

UI:

```text
FIN-01
```

---

## T06-02 — Fee Structure

UI:

```text
FIN-02
FIN-03
```

---

## T06-03 — Invoices

UI:

```text
FIN-04
FIN-05
```

---

## T06-04 — Payments

UI:

```text
FIN-06
FIN-07
```

---

## T06-05 — Outstanding

UI:

```text
FIN-08
```

---

## T06-06 — Refunds

UI:

```text
FIN-09
```

---

## T06-07 — Finance Reports

UI:

```text
FIN-10
```

---

## T06-08 — Payment Integration

Implement secure payment-provider integration where defined.

Never trust client-side payment success.

---

## T06-09 — Financial Security

Require appropriate:

* authorization
* audit
* transaction integrity
* idempotency

---

## T06-10 — Finance Tests

Test:

* fee calculations
* invoices
* payments
* outstanding
* refunds
* tenant isolation
* duplicate payment handling

---

# PHASE 07 — COMPLIANCE

## Objective

Provide compliance management capabilities for maritime training institutes.

---

## T07-01 — Compliance Dashboard

UI:

```text
COM-01
```

---

## T07-02 — Requirements

UI:

```text
COM-02
COM-03
```

---

## T07-03 — Compliance Documents

UI:

```text
COM-04
```

---

## T07-04 — Inspections

UI:

```text
COM-05
COM-06
```

---

## T07-05 — Corrective Actions

UI:

```text
COM-07
```

---

## T07-06 — Compliance Audit

UI:

```text
COM-08
```

---

## T07-07 — Compliance Notifications

Support:

* expiry reminders
* corrective action reminders
* inspection reminders

---

# PHASE 08 — PLACEMENT

## Objective

Connect eligible students with employment opportunities.

---

## T08-01 — Placement Dashboard

UI:

```text
PLC-01
```

---

## T08-02 — Eligible Students

UI:

```text
PLC-02
```

---

## T08-03 — Companies

UI:

```text
PLC-03
PLC-04
```

---

## T08-04 — Opportunities

UI:

```text
PLC-05
PLC-06
```

---

## T08-05 — Placement Tracking

UI:

```text
PLC-07
```

---

## T08-06 — Alumni

UI:

```text
PLC-08
```

---

# PHASE 09 — COMMUNICATION

## Objective

Create a unified communication capability.

---

## T09-01 — Communication Foundation

Implement:

```text
Contacts
Templates
Providers
Message Status
Conversation
```

---

## T09-02 — WhatsApp

UI:

```text
COMMS-01
```

---

## T09-03 — Email

UI:

```text
COMMS-02
```

---

## T09-04 — SMS

UI:

```text
COMMS-03
```

---

## T09-05 — Voice

UI:

```text
COMMS-04
```

---

## T09-06 — Conversation Workspace

UI:

```text
COMMS-05
```

---

## T09-07 — Contacts

UI:

```text
COMMS-06
```

---

## T09-08 — Templates

UI:

```text
COMMS-07
COMMS-08
```

---

## T09-09 — Broadcasts

UI:

```text
COMMS-09
COMMS-10
```

---

## T09-10 — Communication Analytics

UI:

```text
COMMS-11
```

---

## T09-11 — Provider Abstraction

Do not couple business modules directly to a specific communication provider.

---

# PHASE 10 — AUTOMATION

## Objective

Allow MTIs to automate repetitive workflows.

---

## T10-01 — Workflow Model

Implement:

* workflow
* trigger
* condition
* action
* execution
* status

---

## T10-02 — Workflow List

UI:

```text
AUTO-01
```

---

## T10-03 — Workflow Builder

UI:

```text
AUTO-02
```

---

## T10-04 — AI Agents

UI:

```text
AUTO-03
AUTO-04
```

---

## T10-05 — Executions

UI:

```text
AUTO-05
AUTO-06
```

---

## T10-06 — Automation Security

Every automated action must execute through authorized services.

---

## T10-07 — Automation Reliability

Support:

* retry
* failure
* timeout
* idempotency
* execution history

---

# PHASE 11 — AI

## Objective

Introduce controlled, tenant-aware AI capabilities.

---

## T11-01 — AI Foundation

Implement:

* provider abstraction
* model abstraction
* execution model
* usage tracking
* cost tracking

---

## T11-02 — AI Assistant

UI:

```text
AI-01
```

---

## T11-03 — AI Resolution

UI:

```text
AI-02
```

---

## T11-04 — Knowledge

UI:

```text
AI-03
AI-04
```

---

## T11-05 — AI Analytics

UI:

```text
AI-05
```

---

## T11-06 — SQL/Data Agent

UI:

```text
AI-06
```

Default:

```text
READ ONLY
TENANT SCOPED
AUDITED
```

---

## T11-07 — AI Execution

UI:

```text
AI-07
```

Show:

```text
Intent
Tool
Source
Decision
Confidence
Result
Latency
Status
```

---

## T11-08 — AI Configuration

UI:

```text
AI-08
```

---

## T11-09 — AI Guardrails

UI:

```text
AI-09
```

---

## T11-10 — AI Human Approval

Implement confirmation for high-impact operations.

---

## T11-11 — AI Failure Handling

Implement:

* timeout
* retry
* provider failure
* fallback
* graceful degradation

---

## T11-12 — AI Security Tests

Verify:

* tenant isolation
* tool authorization
* SQL restrictions
* data boundaries
* action approval

---

# PHASE 12 — ANALYTICS

## Objective

Provide actionable analytics rather than decorative dashboards.

---

## T12-01 — Executive Analytics

UI:

```text
ANA-01
```

---

## T12-02 — Admissions Analytics

UI:

```text
ANA-02
```

---

## T12-03 — Finance Analytics

UI:

```text
ANA-03
```

---

## T12-04 — Academic Analytics

UI:

```text
ANA-04
```

---

## T12-05 — Marketing Analytics

UI:

```text
ANA-05
```

---

## T12-06 — AI Analytics

UI:

```text
ANA-06
```

---

## T12-07 — Analytics Security

All analytics must respect:

```text
Tenant
Role
Campus
Data Scope
```

---

# PHASE 13 — STUDENT PORTAL

## Objective

Build the mobile-first student experience.

---

## T13-01 — Student Authentication

UI:

```text
STU-01
```

---

## T13-02 — Student Dashboard

UI:

```text
STU-02
```

---

## T13-03 — My Course

```text
STU-03
```

---

## T13-04 — Attendance

```text
STU-04
```

---

## T13-05 — Training

```text
STU-05
```

---

## T13-06 — Examinations

```text
STU-06
```

---

## T13-07 — Fees

```text
STU-07
```

---

## T13-08 — Certificates

```text
STU-08
```

---

## T13-09 — Placement

```text
STU-09
```

---

## T13-10 — Profile

```text
STU-10
```

---

## T13-11 — Student Security

A student can access only their own authorized data.

---

# PHASE 14 — PUBLIC WEBSITE

## Objective

Create the MTI 360 marketing and acquisition experience.

> **Clarification (T00-01, [ADR-0003](docs/adr/0003-marketing-vs-tenant-public-website.md)).**
> Phase 14 is the **Tenant Public Website**: the tenant-branded public website of each Maritime Training Institute (courses, eligibility, fees, admissions, enquiry), served at `frontend/src/app/sites/[site]/`.
> The **MTI 360 marketing website** (the product's own site, currently the root `index.html` / `app.js` / `styles.css`) is tracked separately in the Marketing Website Track (`MKT-*`) below.
> The objective sentence above and some PUB-* screens (Features, Pricing, Request Demo) still describe MTI 360 marketing. This is **not yet resolved** — it is recorded as an open inconsistency in `docs/architecture/spec-inconsistencies.md` and the task list below is intentionally unchanged until that is decided.

---

## T14-01 — Public Website Foundation

Implement:

* responsive layout
* navigation
* footer
* SEO
* performance
* accessibility

---

## T14-02 — Home

```text
PUB-01
```

---

## T14-03 — Features

```text
PUB-02
```

---

## T14-04 — Solutions

```text
PUB-03
```

---

## T14-05 — Pricing

```text
PUB-04
```

---

## T14-06 — Request Demo

```text
PUB-05
```

---

## T14-07 — Contact

```text
PUB-06
```

---

# PHASE 15 — SAAS BILLING & OPERATIONS

## Objective

Complete commercial SaaS capabilities.

---

## T15-01 — Subscription Enforcement

Verify plan-based feature access.

---

## T15-02 — Usage Limits

Implement server-side usage enforcement.

---

## T15-03 — Billing Reconciliation

Verify:

```text
Invoice
Payment
Subscription
Tenant
```

consistency.

---

## T15-04 — Failed Payment Handling

Implement:

* retry
* notification
* grace period
* past-due
* suspension

according to product rules.

---

## T15-05 — Tenant Provisioning Reliability

Test:

* provisioning success
* partial failure
* retry
* rollback/recovery

---

## T15-06 — Platform Operational Monitoring

Verify:

* jobs
* queues
* API
* providers
* database
* storage
* AI

---

# PHASE 16 — SECURITY & HARDENING

## Objective

Perform a dedicated security and reliability pass across the entire system.

---

## T16-01 — Authentication Security Review

Verify:

* session handling
* password security
* MFA
* reset flows
* brute-force protection
* logout

---

## T16-02 — Authorization Review

Review every protected module.

---

## T16-03 — Tenant Isolation Review

Perform systematic cross-tenant testing.

---

## T16-04 — API Security Review

Check:

* authentication
* authorization
* validation
* rate limits
* error handling
* sensitive data exposure

---

## T16-05 — Database Security Review

Check:

* roles
* privileges
* ownership
* migrations
* backups
* sensitive data

---

## T16-06 — File Security Review

Test:

* malicious files
* invalid extensions
* oversized files
* path traversal
* unauthorized download

---

## T16-07 — AI Security Review

Check:

```text
Prompt injection
Tool authorization
Tenant leakage
Data leakage
SQL restrictions
Action approval
Provider boundary
```

---

## T16-08 — Communication Security

Verify provider credentials and webhook handling.

---

## T16-09 — Audit Review

Verify all sensitive operations are appropriately auditable.

---

## T16-10 — Dependency Security

Run dependency/security scans supported by the technology stack.

---

## T16-11 — Performance Review

Measure:

* API latency
* database performance
* page load
* large tables
* dashboards
* AI latency
* background jobs

---

## T16-12 — Accessibility Review

Perform WCAG 2.2 AA review.

---

# PHASE 17 — PRODUCTION READINESS

## Objective

Prepare MTI 360 for real tenant onboarding and production operation.

---

## T17-01 — Production Environment

Verify:

* infrastructure
* environment variables
* secrets
* database
* storage
* queue
* domain
* TLS

---

## T17-02 — Database Migration Process

Verify production migration procedure.

---

## T17-03 — Backup & Restore

Perform actual restore testing.

A backup is not considered validated until restoration is tested.

---

## T17-04 — Monitoring

Implement/verify:

```text
Application monitoring
Error monitoring
Database monitoring
Queue monitoring
API monitoring
Infrastructure monitoring
```

---

## T17-05 — Logging

Verify structured logs and sensitive-data protection.

---

## T17-06 — Alerting

Define alerts for:

* application failure
* database failure
* queue failure
* payment failure
* communication provider failure
* AI provider failure
* storage failure

---

## T17-07 — Disaster Recovery

Document:

* backup strategy
* recovery process
* RPO
* RTO
* incident response

according to the actual infrastructure.

---

## T17-08 — Production Smoke Tests

Run:

```text
Platform Login
Tenant Login
Tenant Creation
Tenant Provisioning
Student Creation
Course Creation
Application
Payment
Communication
AI
Student Portal
Public Website
```

---

## T17-09 — Security Smoke Tests

Verify:

```text
Unauthorized access denied
Cross-tenant access denied
Privileged access audited
Secrets not exposed
```

---

## T17-10 — Production Performance Test

Test realistic tenant/user/data volumes.

---

## T17-11 — Production UI Review

Review all major page templates against:

```text
DESIGN-SYSTEM.md
UI-SCREENS.md
```

---

## T17-12 — Documentation Review

Verify:

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

are internally consistent.

---

## T17-13 — Release Checklist

Production release requires:

```text
Build PASS
Tests PASS
Security PASS
Tenant Isolation PASS
Migration PASS
Backup PASS
Restore PASS
Monitoring PASS
Critical E2E PASS
Documentation PASS
```

---

# MARKETING WEBSITE TRACK (outside product phases)

Added in T00-01 ([ADR-0003](docs/adr/0003-marketing-vs-tenant-public-website.md)). The MTI 360 marketing website promotes MTI 360 itself. It is **not** one of the four product experiences and **not** Phase 14.

Current state: root `index.html`, `app.js`, `styles.css` — **Prototype: YES, Production Ready: NO**. Baseline tag: `marketing-site-v1`.

Rule: these files are changed **only** by an explicit `MKT-*` task.

---

## MKT-01 — Relocate Marketing Website

**Priority:** P2
**Status:** NOT_STARTED

Move `index.html`, `app.js`, `styles.css` to `marketing-site/` in a **rename-only commit**.

### Acceptance Criteria

* Before moving, confirm whether any host deploys from the repository root and update the deploy source in the same change window.
* `git show --stat -M` reports 100%-similarity renames; SHA-256 of the three files is unchanged.
* The page renders identically from its new location.
* No functional or visual changes are included.

---

## MKT-02 — Functional Demo Request

**Priority:** P2
**Status:** NOT_STARTED

Replace the non-functional demo form (it currently shows success without sending data) with a real submission path.

### Acceptance Criteria

* Server-side validation, rate limiting, anti-spam and a consent/privacy notice.
* No fake success state (TASKS.md §21).
* Personal data handled and logged according to CLAUDE.md §67.

---

## MKT-03 — Marketing Website Audit Fixes

**Priority:** P3
**Status:** NOT_STARTED

Address the findings recorded in the T00-01 repository audit, e.g. the dead `#login` link, the light-theme flash for dark-mode visitors, missing System theme option, content hidden when JavaScript fails, lifecycle autoplay pause control, self-hosted fonts and security headers.

---

# 8. CROSS-CUTTING TASKS

These activities apply throughout development.

---

## XC-01 — Tenant Isolation

Every tenant-owned feature must include tenant-isolation tests.

---

## XC-02 — Authorization

Every protected operation must have permission enforcement.

---

## XC-03 — Audit

Sensitive operations must be auditable.

---

## XC-04 — Accessibility

Every new UI feature must follow WCAG 2.2 AA principles.

---

## XC-05 — Responsive Design

Every new UI feature must support the appropriate device sizes.

---

## XC-06 — Loading / Empty / Error States

Every major screen must define these states.

---

## XC-07 — Design-System Compliance

Do not introduce arbitrary colors, typography, spacing or components.

---

## XC-08 — Performance

Avoid:

* N+1 queries
* unnecessary API requests
* huge browser payloads
* unbounded queries

---

## XC-09 — Observability

Important workflows should be traceable through logs/metrics/audit.

---

## XC-10 — Documentation

Material behavior changes require documentation updates.

---

# 9. VERTICAL SLICE IMPLEMENTATION RULE

For major features, Claude Code should prefer this sequence:

```text
Domain Model
     ↓
Database Migration
     ↓
Repository
     ↓
Service
     ↓
Authorization
     ↓
API
     ↓
API Tests
     ↓
UI Data Layer
     ↓
Reusable Components
     ↓
Screen
     ↓
UI States
     ↓
E2E Test
     ↓
Documentation
```

---

# 10. SCREEN IMPLEMENTATION RULE

A screen must not be implemented merely because it exists in `UI-SCREENS.md`.

Before implementation:

```text
1. Identify persona.
2. Identify workflow.
3. Identify entry point.
4. Identify required data.
5. Identify permissions.
6. Identify API dependencies.
7. Identify reusable template.
8. Identify reusable components.
9. Identify loading/empty/error states.
10. Identify related screens.
```

---

# 11. PAGE TEMPLATE STRATEGY

Use the page templates defined in `UI-SCREENS.md`.

Primary templates:

```text
T01 Dashboard
T02 Data List
T03 Detail
T04 Form
T05 Wizard
T06 Kanban
T07 Calendar
T08 Communication Workspace
T09 AI Workspace
T10 Analytics
T11 Workflow Builder
T12 Tenant 360
T13 Platform Operations
T14 Support Workspace
T15 Settings
T16 Authentication
T17 Student Portal
T18 Public Website
```

---

# 12. COMPONENT STRATEGY

Build reusable components before duplicating screens.

Examples:

```text
AppShell
Sidebar
TopBar
PageHeader
DataTable
FilterBar
KPI
ChartCard
Timeline
FileUpload
PermissionGate
TenantContext
CampusSwitcher
AIExecution
AIConfidence
AuditTimeline
TenantHealthCard
AdmissionFunnel
StudentCard
CourseCard
BatchCard
TrainingProgress
AttendanceSummary
FeeSummary
ComplianceSummary
PlacementPipeline
```

---

# 13. UI PRIORITY

The first implementation should prioritize:

```text
P0
Authentication
Multi-tenancy
Platform Control Plane
Tenant Foundation
Core Design System
Admissions Foundation
```

Then:

```text
P1
Academics
Finance
Compliance
Placement
Communication
```

Then:

```text
P2
Automation
AI
Advanced Analytics
Student Portal
Public Website Enhancements
```

---

# 14. MVP RELEASE CANDIDATE

The first meaningful MTI 360 release should demonstrate the complete core lifecycle:

```text
Tenant Created
      ↓
Tenant Admin Login
      ↓
Institute Configured
      ↓
Course Created
      ↓
Lead Created
      ↓
Counselling
      ↓
Application
      ↓
Document Verification
      ↓
Admission
      ↓
Student
      ↓
Batch
      ↓
Training
      ↓
Attendance
      ↓
Fee
      ↓
Payment
      ↓
Certificate
```

This is more valuable than having dozens of incomplete screens.

---

# 15. INITIAL VERTICAL SLICE

The recommended first end-to-end slice is:

```text
Tenant
 ↓
User
 ↓
Course
 ↓
Lead
 ↓
Application
 ↓
Student
 ↓
Batch
 ↓
Fee
```

This validates the architecture across multiple domains.

---

# 16. TESTING MATRIX

| Area           | Unit | Integration | API | E2E | Security |
| -------------- | ---: | ----------: | --: | --: | -------: |
| Authentication |    ✓ |           ✓ |   ✓ |   ✓ |        ✓ |
| Multi-tenancy  |    ✓ |           ✓ |   ✓ |   ✓ |        ✓ |
| Authorization  |    ✓ |           ✓ |   ✓ |   ✓ |        ✓ |
| Platform       |    ✓ |           ✓ |   ✓ |   ✓ |        ✓ |
| Admissions     |    ✓ |           ✓ |   ✓ |   ✓ |        ✓ |
| Academics      |    ✓ |           ✓ |   ✓ |   ✓ |        ✓ |
| Finance        |    ✓ |           ✓ |   ✓ |   ✓ |        ✓ |
| Compliance     |    ✓ |           ✓ |   ✓ |   ✓ |        ✓ |
| Placement      |    ✓ |           ✓ |   ✓ |   ✓ |        ✓ |
| Communication  |    ✓ |           ✓ |   ✓ |   ✓ |        ✓ |
| Automation     |    ✓ |           ✓ |   ✓ |   ✓ |        ✓ |
| AI             |    ✓ |           ✓ |   ✓ |   ✓ |        ✓ |
| Analytics      |      |           ✓ |   ✓ |   ✓ |        ✓ |
| Student Portal |    ✓ |           ✓ |   ✓ |   ✓ |        ✓ |
| Public Website |      |           ✓ |   ✓ |   ✓ |          |

---

# 17. ACCEPTANCE CRITERIA RULE

Every task must have measurable acceptance criteria.

Bad:

```text
Build student module.
```

Good:

```text
An authorized tenant user can create a student.

The API derives tenant context from authenticated identity.

The student is stored against the correct tenant.

An unauthorized tenant cannot retrieve the student.

The UI displays validation errors.

Unit/API/integration tests pass.
```

---

# 18. DEFINITION OF DONE

A task is complete only when:

```text
[ ] Requirements understood
[ ] Existing implementation inspected
[ ] Database changes complete
[ ] API complete
[ ] Authorization complete
[ ] Tenant isolation verified
[ ] UI complete
[ ] Loading state complete
[ ] Empty state complete
[ ] Error state complete
[ ] Validation complete
[ ] Tests complete
[ ] Security reviewed
[ ] Documentation updated
[ ] Build passes
[ ] Relevant tests pass
[ ] DEVELOPMENT-STATUS.md updated
```

Not every checkbox applies to every task, but omissions must be intentional.

---

# 19. CLAUDE CODE EXECUTION RULE

Claude Code should normally execute tasks in this order:

```text
Read Task
    ↓
Read Relevant Specifications
    ↓
Inspect Existing Code
    ↓
Identify Dependencies
    ↓
Create Implementation Plan
    ↓
Implement
    ↓
Run Tests
    ↓
Review Security
    ↓
Review UI
    ↓
Update Documentation
    ↓
Update DEVELOPMENT-STATUS.md
```

---

# 20. DO NOT SKIP FOUNDATION

Claude Code must not jump directly to:

```text
AI
Analytics
Fancy Dashboard
```

before:

```text
Authentication
Authorization
Tenant Isolation
Core Data Model
API Foundation
Design System
```

are stable enough.

---

# 21. DO NOT BUILD FAKE FUNCTIONALITY

Avoid shipping:

```text
Fake charts
Fake AI results
Fake payment success
Fake communication delivery
Fake database records
Fake provisioning status
```

Prototype-only functionality must be explicitly identified.

---

# 22. TASK DEPENDENCY RULE

If a task depends on an incomplete prerequisite:

```text
Do not silently bypass the dependency.
```

Instead:

```text
Mark BLOCKED
Identify prerequisite
Explain why
```

unless a safe parallel implementation is possible.

---

# 23. PARALLEL DEVELOPMENT

Tasks may be developed in parallel when dependencies permit.

Example:

```text
Design System
       │
       ├── Platform UI
       ├── Tenant UI
       └── Student UI
```

But security and shared architecture changes must be coordinated carefully.

---

# 24. CHANGE CONTROL

If implementation reveals that an existing specification is incorrect:

```text
1. Stop the affected implementation.
2. Identify the conflict.
3. Document the proposed change.
4. Update the relevant source document.
5. Update dependent tasks.
6. Continue implementation.
```

Do not silently create a second architecture.

---

# 25. TASK IDs

Task IDs must remain stable.

Do not renumber completed tasks because new tasks are inserted.

New tasks should use the appropriate phase identifier.

Example:

```text
T04-01
T04-02
T04-03
```

If a subtask is required:

```text
T04-03A
T04-03B
```

---

# 26. DEVELOPMENT STATUS INTEGRATION

`DEVELOPMENT-STATUS.md` is the execution state.

`TASKS.md` is the planned work.

Therefore:

```text
TASKS.md
= What should be built

DEVELOPMENT-STATUS.md
= What has actually been built
```

Never use `TASKS.md` as a substitute for development status.

---

# 27. RELEASE MILESTONES

Recommended milestones:

### M0 — Foundation Ready

```text
Phase 00
```

### M1 — Secure SaaS Foundation

```text
Phase 01
```

### M2 — Platform Operations Ready

```text
Phase 02
```

### M3 — Tenant Foundation Ready

```text
Phase 03
```

### M4 — Core Admissions Ready

```text
Phase 04
```

### M5 — Academic Operations Ready

```text
Phase 05
```

### M6 — Financial Operations Ready

```text
Phase 06
```

### M7 — Compliance & Placement Ready

```text
Phase 07
Phase 08
```

### M8 — Communication & Automation Ready

```text
Phase 09
Phase 10
```

### M9 — AI & Analytics Ready

```text
Phase 11
Phase 12
```

### M10 — External Experiences Ready

```text
Phase 13
Phase 14
```

### M11 — Production Ready

```text
Phase 15
Phase 16
Phase 17
```

---

# 28. FIRST IMPLEMENTATION ORDER

When starting actual development, use:

```text
T00-01
T00-02
T00-03
T00-04
T00-05
T00-06
T00-07
T00-08
T00-09
T00-10
T00-10A

↓

T01-00
T01-01
T01-02
T01-03
T01-04
T01-05
T01-06
T01-07
T01-08
T01-09
T01-10

↓

T02 Platform Control Plane

↓

T03 Tenant Foundation

↓

T04 Admissions
```

Do not start the full business-module implementation before the security foundation is established.

---

# 29. PRIORITY RULE

When time or resources are constrained:

```text
Security
   ↓
Tenant Isolation
   ↓
Core Business Workflow
   ↓
Data Integrity
   ↓
Usability
   ↓
Analytics
   ↓
AI Enhancements
   ↓
Visual Enhancements
```

A beautiful screen without secure underlying behavior is not complete.

---

# 30. MASTER SUCCESS CRITERIA

MTI 360 implementation succeeds when:

```text
Multiple MTIs
       ↓
Securely isolated
       ↓
Use the same SaaS platform
       ↓
Configure their own institute
       ↓
Manage admissions
       ↓
Manage students
       ↓
Manage academics
       ↓
Manage finance
       ↓
Manage compliance
       ↓
Manage placement
       ↓
Communicate
       ↓
Automate
       ↓
Use controlled AI
       ↓
Analyze operations
```

without requiring separate application deployments for each tenant.

---

# 31. FINAL IMPLEMENTATION PRINCIPLE

Do not optimize for:

> "How quickly can we generate all the screens?"

Optimize for:

> "How quickly can we build a secure, reusable, production-quality SaaS foundation that allows all required screens and workflows to be implemented consistently?"

The goal is:

```text
Strong Foundation
      +
Reusable Architecture
      +
Reusable Components
      +
Vertical Slices
      +
Automated Testing
      +
Security
      +
Premium UX
      =
Production-Ready MTI 360
```

---

# 32. END STATE

At the completion of all phases, MTI 360 should provide:

```text
Platform Control Plane
        +
Multi-Tenant SaaS
        +
Tenant Operations
        +
Admissions
        +
Academics
        +
Finance
        +
Compliance
        +
Placement
        +
Communication
        +
Automation
        +
AI
        +
Analytics
        +
Student Portal
        +
Public Website
        +
Billing
        +
Security
        +
Observability
```

as one cohesive product.

---

# 33. FINAL RULE

**Never mark a task complete because the screen looks complete.**

A production MTI 360 feature is complete only when:

```text
UI
+
API
+
Business Logic
+
Database
+
Authorization
+
Tenant Isolation
+
Validation
+
Testing
+
Observability
+
Documentation
```

are appropriately implemented and verified.

---

**MTI 360**

**Acquire Students. Simplify Operations. Grow Your Institute.**
