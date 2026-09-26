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

**Status:** READY_FOR_REVIEW (branch `feat/T00-03-docker`)

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

---

# PHASE 01 — AUTHENTICATION & MULTI-TENANCY

## Objective

Establish the security and tenancy foundation before building business modules.

---

## T01-01 — User Identity Model

Implement:

* users
* credentials
* status
* profile
* authentication metadata

---

## T01-02 — Authentication

Implement:

* login
* logout
* session management
* password reset
* account status

### UI

```text
AUTH-01
AUTH-02
AUTH-03
AUTH-04
AUTH-05
```

---

## T01-03 — MFA

Implement MFA architecture and UI.

---

## T01-04 — Platform Identity

Separate platform administrator identity from tenant user context.

---

## T01-05 — Tenant Model

Implement:

```text
Tenant
Tenant Status
Tenant Configuration
Tenant Metadata
```

---

## T01-06 — Campus Model

Implement tenant campuses.

Relationship:

```text
Tenant
  ↓
Campus
```

---

## T01-07 — Tenant Context

Implement secure server-side tenant resolution.

### Critical Requirement

Never trust arbitrary client-supplied tenant IDs for authorization.

---

## T01-08 — Role Model

Implement:

```text
Role
Permission
Role Permission
User Role
```

---

## T01-09 — Authorization Engine

Implement centralized authorization.

Must support:

```text
Platform scope
Tenant scope
Campus scope where required
Resource permissions
```

---

## T01-10 — Tenant Isolation

Implement and test tenant isolation at:

```text
API
Service
Repository
Database
Search
Jobs
Storage
Analytics
AI
```

---

## T01-11 — Audit Foundation

Implement audit framework.

Capture appropriate:

```text
Actor
Tenant
Action
Resource
Timestamp
Result
```

---

## T01-12 — Security Tests

Create cross-tenant security tests.

Must prove:

```text
Tenant A cannot access Tenant B.
```

Test:

* GET
* POST
* PATCH
* DELETE
* Search
* Reports
* Export
* Jobs

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

↓

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
T01-11
T01-12

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
