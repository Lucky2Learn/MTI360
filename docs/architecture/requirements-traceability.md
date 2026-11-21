# Requirements Traceability

- **Status:** Initial version (2026-10-28, R0 of the completion roadmap). Inventory and module level; requirement-level mappings are added slice by slice (§10).
- **Baseline:** `main` at `921460d`, plus the uncommitted 02-C work on `feat/platform-tenant-management`.
- **Owner:** updated with every slice that changes a status below, in the same change as TASKS.md and DEVELOPMENT-STATUS.md.

---

## 1. Purpose

This document links each documented requirement to the screen, API, backend module, permission, database migration, automated tests and verification evidence that implement it. It answers two questions for every product area and screen: **is it built**, and **what proves it**.

It does not restate specifications. Requirements stay in the source documents (§3), tasks in TASKS.md, and the narrative implementation record in DEVELOPMENT-STATUS.md. This document holds the cross-reference and the evidence.

---

## 2. Statuses and how they are assigned

| Status | Assigned when |
|---|---|
| `NOT_STARTED` | No implementation exists on `main` or in the working tree. |
| `IN_PROGRESS` | Implementation exists but is uncommitted or unmerged, or it is merged with completion items its own task still lists as open. |
| `IMPLEMENTED_UNVERIFIED` | Merged to `main` with automated tests, but its verification level (below) is not recorded. |
| `IMPLEMENTED_VERIFIED` | Merged to `main`, and its verification level is recorded with evidence. |
| `BLOCKED` | Cannot proceed until a named decision, credential or dependency is resolved. |
| `DEFERRED_BY_APPROVAL` | Postponed by a recorded, approved decision (TASKS.md, an ADR or a readiness plan). |
| `NOT_APPLICABLE` | Not required for this area, with the justification stated. |

**Verification levels:**

- **Backend / API:** CI on `main` passed, including the PostgreSQL integration tests (`REQUIRE_DATABASE_TESTS=1`), and the result is recorded in DEVELOPMENT-STATUS.md.
- **Screen:** the CLAUDE.md §57 gate (390 / 768 / 1024 / 1440; Light, Dark and System; states; accessibility) is recorded from a real browser. DEVELOPMENT-STATUS.md §48 makes responsive behaviour part of "implemented", so automated tests alone never make a screen `IMPLEMENTED_VERIFIED`.

**Rules:**

- A route, component, endpoint or table existing is **not** evidence of a status. Only a recorded test result, merge or browser check is.
- Where a relationship has not been inspected, the cell says **pending inspection**. That means "not yet audited", not "missing".
- TASKS.md and DEVELOPMENT-STATUS.md keep their own vocabulary (`NOT_STARTED`, `IN_PROGRESS`, `BLOCKED`, `READY_FOR_REVIEW`, `COMPLETED`, `DEFERRED`). A task `COMPLETED` there with deferred D18 browser journeys shows as `IMPLEMENTED_UNVERIFIED` here for its screens.

---

## 3. Sources

| Kind | Documents |
|---|---|
| Product | [PRD.md](../../PRD.md), [APP-FLOW.md](../../APP-FLOW.md), [PLATFORM-ADMIN.md](../../PLATFORM-ADMIN.md) |
| Screens and design | [UI-SCREENS.md](../../UI-SCREENS.md) (217 screen entries), [DESIGN-SYSTEM.md](../../DESIGN-SYSTEM.md), `docs/ui/T01-04…`, `T01-05…`, `T01-09B…`, `T01-09C…` UI contracts |
| Architecture | [ARCHITECTURE.md](../../ARCHITECTURE.md), [docs/adr/](../adr/) (ADR-0001 … ADR-0022; there is no ADR-0009), `docs/architecture/*.md` |
| Plans | [TASKS.md](../../TASKS.md) (task IDs and acceptance criteria), [PHASE-02-MASTER-READINESS.md](PHASE-02-MASTER-READINESS.md), [PHASE-02-1-COURSES-LEADS-READINESS.md](PHASE-02-1-COURSES-LEADS-READINESS.md), [PHASE-02-5-FINANCE-LITE-READINESS.md](PHASE-02-5-FINANCE-LITE-READINESS.md) |
| Status | [DEVELOPMENT-STATUS.md](../../DEVELOPMENT-STATUS.md) |
| Conflicts | [spec-inconsistencies.md](spec-inconsistencies.md) (INC-01 … INC-50) |
| Engineering rules | [CLAUDE.md](../../CLAUDE.md), `frontend/AGENTS.md` |

Order of precedence: CLAUDE.md §2. Where an ADR refines a specification, the ADR applies.

---

## 4. Product scope by phase

Order: TASKS.md §4 with the L1 re-sequencing (2026-10-08) and the ADR-0022 delivery-order change. "Screens" uses UI-SCREENS.md IDs.

### 4.1 Delivered foundation and the Admissions MVP

| Area | Task IDs | Screens | Status | Evidence | Open items |
|---|---|---|---|---|---|
| Phase 00 Foundation | T00-01 … T00-10, T00-10A | — (design system, shell, layout) | `IMPLEMENTED_VERIFIED` (automated); browser checks of the foundation components pending inspection | PR #1 … #13; DEVELOPMENT-STATUS.md §8 | INC-18 … INC-29 (conventions) |
| Phase 01 Authentication & multi-tenancy | T01-00 … T01-10 | AUTH-01 … 08, AUTHZ-01, RESOURCE-02, PLAT-01, PLAT-02, PAUTH-01 … 07, PLAT-52 (partial) | Backend `IMPLEMENTED_VERIFIED` (CI on `main` `2af531b`, recorded in T01-10); screens `IMPLEMENTED_UNVERIFIED` | PR #14 … #31; DEVELOPMENT-STATUS.md §9; T01-10 gate | D18 Chromium journeys deferred; no CI result recorded for PR #31 |
| 02-1 Courses + Leads | T05-01 (minimal), T04-01, T04-02 | ACA-01/02/03, GROW-08/09, ADM-02 | Backend `IMPLEMENTED_VERIFIED`; screens `IMPLEMENTED_UNVERIFIED` | PR #32 (`2ea72f6`); CI on `2ea72f6` with PostgreSQL integration; CodeQL on `230dee2` | D18 not run; GROW-07/10 deferred |
| 02-2 Applications → Student | T04-04 … T04-08 | ADM-05 … ADM-14 | Backend `IMPLEMENTED_VERIFIED`; screens `IMPLEMENTED_UNVERIFIED` | PR #32; ADR-0021 | D18 not run |
| 02-5 Finance-lite | T06-02 … T06-05, parts of T06-09/T06-10 | FIN-02 … FIN-08, ADM-12 Fees | `IN_PROGRESS` (merged; completion items open) | PR #34 (`a5bd01a`); local test runs recorded 2026-10-11; V-02 print check 16/16 (PR #35) | CI and CodeQL result not recorded; D18 not run; INC-48, INC-49 before production use |
| 02-C platform part | T02-04 (minimal), T02-12 (minimal) | PLAT-04, PLAT-05, PLAT-06 (minimal) | `IN_PROGRESS` (uncommitted) | `tenants.test.tsx` page tests; backend tenant API tests (DEVELOPMENT-STATUS.md §10) | R1: responsive and theme browser checks; step-up in a real browser |
| 02-C tenant part | T03-03, T03-04, T03-05 | ADMIN-03 … ADMIN-07 | `IN_PROGRESS` (uncommitted) | 75 mocked-API page tests; backend API unchanged (T01-08) | R1: browser checks; invite → accept journey (Mailpit); INC-50 |
| 02-3 Seed + demo hardening | — (slice) | — | `COMPLETED` (automated, 2026-10-31; browser pending) | `backend/app/seed.py`, `backend/app/cli.py`, `docs/runbooks/demo.md`; seed contract and seed integration tests | Listed in the TASKS.md slice table since 2026-10-31 (§9 below resolved) |
| 02-4 Public enquiry | T14 enquiry capture | hosted enquiry page (T18; INC-52) | `IN_PROGRESS` (2026-11-01) | `test_public_enquiry_api.py`, `test_outbox_worker.py`, `test_tenant_domains.py`, `test_public_enquiry_schema.py` (all passing 2026-11-01), `test_public_enquiry_rules.py`, `enquiry.test.tsx`, proxy tests | Needs outbox, worker and queue (infrastructure D4), `tenant_domains`; INC-27 |
| 02-6 Batches | T05-03 | ACA-05, ACA-06, ACA-07 | `IN_PROGRESS` (implemented, tested and browser-verified on the disposable database 2026-11-20; uncommitted) | [ADR-0025](../adr/0025-batches.md) | — |
| 02-7 Communication (V1.5) | T09 subset | ADM-15, templates | `NOT_STARTED` | — | Provider credentials; outbox |
| 02-8 Admissions dashboard (V1.5) | — | ADM-01 | `NOT_STARTED` | — | — |

### 4.2 Remaining documented scope

| Phase | Task IDs | Screens | Status | Blockers and dependencies |
|---|---|---|---|---|
| 02 Platform Control Plane (rest) | T02-01 … T02-23 (T02-04 partly in 02-C) | PLAT-03, PLAT-07 … PLAT-53 | `NOT_STARTED`, except T02-04 (`IN_PROGRESS`) and the partial overlap of T02-01/T02-02 with T01-09B (§9) | INC-07 plan names (T02-06/07), INC-32 lifecycle (T02-05), INC-30 platform roles |
| 03 Tenant Foundation (rest) | T03-01, T03-02, T03-06 … T03-11 | ADMIN-01, ADMIN-02, ADMIN-08 … ADMIN-14 | `NOT_STARTED`; backend `GET /api/v1/institute` exists (pending inspection against ADMIN-01) | INC-06 role names, INC-40 campus status |
| 04 Admissions (rest) | T04-03, T04-09, T04-10 | ADM-01, ADM-03, ADM-04, ADM-15, GROW-01 … 07, GROW-10 … 12 | `NOT_STARTED` (GROW-07/10 `DEFERRED_BY_APPROVAL`) | Communication (Phase 09) for T04-09 |
| 05 Academics | T05-01 (rest), T05-02 … T05-12 | ACA-04 … ACA-27, DASH-03 | `NOT_STARTED` | 02-6 Batches first |
| 06 Finance (full) | T06-01, T06-06 … T06-10 (rest) | FIN-01, FIN-09, FIN-10, DASH-04 | `DEFERRED_BY_APPROVAL` (FIN-01/09/10, ADR-0022) / `NOT_STARTED` | Payment provider (T06-08); INC-48, INC-49 |
| 07 Compliance | T07-01 … T07-07 | COM-01 … COM-08 | `NOT_STARTED` | — |
| 08 Placement | T08-01 … T08-06 | PLC-01 … PLC-08 | `NOT_STARTED` | — |
| 09 Communication | T09-01 … T09-11 | COMMS-01 … COMMS-11 | `NOT_STARTED` | WhatsApp, email, SMS and voice provider credentials; outbox and worker |
| 10 Automation | T10-01 … T10-07 | AUTO-01 … AUTO-06 | `NOT_STARTED` | Background jobs (T02-13) |
| 11 AI | T11-01 … T11-12 | AI-01 … AI-09 | `NOT_STARTED` | AI provider credentials; governance (CLAUDE.md §42–§47) |
| 12 Analytics | T12-01 … T12-07 | ANA-01 … ANA-06, DASH-01, DASH-02, DASH-05 | `NOT_STARTED` (DASH-01 is an empty landing page, §5.2) | INC-19 chart palette |
| 13 Student Portal | T13-01 … T13-11 | STU-01 … STU-10 | `NOT_STARTED` (placeholder route `/student` only) | Student identity realm (ADR-0005) |
| 14 Tenant Public Website | T14-01 … T14-07 | PUB-01 … PUB-06 | `NOT_STARTED` (placeholder route `/site` only) | INC-03 (PUB list describes the marketing site), INC-27 |
| 15 SaaS Billing & Operations | T15-01 … T15-06 | (PLAT-11 … PLAT-17) | `NOT_STARTED` | T02-06/07 |
| 16 Security & Hardening | T16-01 … T16-12 | — | `NOT_STARTED` (T01-10 covers the Phase 01 scope only) | — |
| 17 Production Readiness | T17-01 … T17-13 | — | `NOT_STARTED` | Production hosting target undefined; no deployment, monitoring or backup configuration (infrastructure/README.md) |
| Marketing Website Track | MKT-01 … MKT-03 | — (not a product experience, ADR-0003) | `NOT_APPLICABLE` to the product scope; tracked separately in TASKS.md | INC-04, INC-26 |

---

## 5. Screen inventory (UI-SCREENS.md, 217 entries)

Counts: Platform 60 (PLAT 53, PAUTH 7), Tenant 141, Student 10, Public 6. The specification totals of ~222 are INC-01. Summary counts are in DEVELOPMENT-STATUS.md §27.

"Unverified" below means `IMPLEMENTED_UNVERIFIED`: merged with automated tests, no recorded §57 browser gate. Routes are given where the route was inspected; otherwise **pending inspection**.

### 5.1 Platform Control Plane (60)

| ID | Screen | Status | Route / evidence |
|---|---|---|---|
| PLAT-01 | Platform Login | `IMPLEMENTED_UNVERIFIED` | `/platform/login`; T01-09B, PR #31 |
| PLAT-02 | Platform MFA | `IMPLEMENTED_UNVERIFIED` | step of `/platform/login` (D9B-2); PR #31 |
| PLAT-03 | Platform Dashboard | `NOT_STARTED` | `/platform` is a placeholder |
| PLAT-04 | Tenant List | `IN_PROGRESS` | `/platform/tenants`; uncommitted; core journey in a browser 2026-10-25; Plan and Users columns need T02-06/07 |
| PLAT-05 | Tenant 360 | `IN_PROGRESS` | `/platform/tenants/[tenantId]`; minimal summary, suspend/reactivate, resend invitation; full Tenant 360 not built |
| PLAT-06 | Create Tenant | `IN_PROGRESS` | `/platform/tenants/new`; uncommitted |
| PLAT-07 … PLAT-51 | Tenant onboarding … Platform Roles & Permissions (45 entries) | `NOT_STARTED` | Remaining T02-04 and T02-05 … T02-23; navigation items `UNRELEASED` |
| PLAT-52 | Platform Admin Profile | `IMPLEMENTED_UNVERIFIED` (partial) | `/platform/profile`, "Sign-in security" only (D9B-8 accepted) |
| PLAT-53 | Platform Settings | `NOT_STARTED` | — |
| PAUTH-01 | Platform Forgot Password | `IMPLEMENTED_UNVERIFIED` | `/platform/forgot-password`; PR #31 |
| PAUTH-02 | Platform Reset Password | `IMPLEMENTED_UNVERIFIED` | `/platform/reset-password`; PR #31 |
| PAUTH-03 | Platform Accept Invitation | `IMPLEMENTED_UNVERIFIED` | `/platform/accept-invitation`; PR #31 |
| PAUTH-04 | Set Up Two-Step Verification | `IMPLEMENTED_UNVERIFIED` | sign-in step (route pending inspection); PR #31 |
| PAUTH-05 | Recovery Codes | `IMPLEMENTED_UNVERIFIED` | sign-in step and PLAT-52 (route pending inspection); PR #31 |
| PAUTH-06 | Platform Session Ended | `IMPLEMENTED_UNVERIFIED` | `/platform/session-ended`; PR #31 |
| PAUTH-07 | Step-Up Verification | `IMPLEMENTED_UNVERIFIED` | dialog; PR #31; a real-browser prompt after the 10-minute window is an R1 check |

PLAT-07 … PLAT-51 individually: PLAT-07 Tenant Onboarding, 08 Tenant Status, 09 Tenant Usage & Health, 10 Tenant Users / Support Access, 11 Plans & Pricing, 12 Subscriptions, 13 Billing & Invoices, 14 Payment Transactions, 15 Coupons / Discounts / Trials, 16 Feature Entitlements, 17 Usage Metering, 18 Communication Providers, 19 AI Providers / Models, 20 AI Cost & Usage, 21 Global AI Guardrails, 22 Global Integrations, 23 Tenant Provisioning, 24 Background Jobs, 25 System Health, 26 API / Webhook Monitoring, 27 Incident Dashboard, 28 Support Tickets, 29 Support Ticket Detail, 30 Controlled Support Session, 31 Platform Notifications, 32 Platform Templates, 33 Feature Flags, 34 Global Settings, 35 Security Dashboard, 36 Platform Audit Logs, 37 Login / Session Audit, 38 Data Access Audit, 39 Data Retention, 40 Backup / Restore Status, 41 Platform Analytics, 42 Tenant Growth, 43 Revenue Analytics, 44 Retention / Churn, 45 Subscription Analytics, 46 Platform AI Analytics, 47 API Keys / Service Credentials, 48 Domain / Branding, 49 Tenant Provisioning Templates, 50 Platform Admin Users, 51 Platform Roles & Permissions. All `NOT_STARTED` as screens. Note: APIs already exist for platform users (8 operations, T01-07) and platform audit events (1 operation); their screens (PLAT-50, PLAT-36) are not built.

### 5.2 Tenant Application (141)

**Authentication and access states (10)**

| ID | Screen | Status | Route / evidence |
|---|---|---|---|
| AUTH-01 | Tenant Login | `IMPLEMENTED_UNVERIFIED` | `/login`; T01-09A, PR #30 |
| AUTH-02 | Forgot Password | `IMPLEMENTED_UNVERIFIED` | `/forgot-password`; PR #30 |
| AUTH-03 | Reset Password | `IMPLEMENTED_UNVERIFIED` | `/reset-password`; PR #30 |
| AUTH-04 | MFA | `IMPLEMENTED_UNVERIFIED` | sign-in step of `/login` (PR #30); enrolment at `/app/account/security` (T01-09C, PR #31) |
| AUTH-05 | Session / Access Denied | `IMPLEMENTED_UNVERIFIED` | `/session-ended`; PR #30 |
| AUTH-06 | Accept Invitation | `IMPLEMENTED_UNVERIFIED` | `/accept-invitation`; PR #30 |
| AUTH-07 | Choose Institute | `IMPLEMENTED_UNVERIFIED` | `/select-institute`; PR #30 |
| AUTH-08 | Choose Campus | `IMPLEMENTED_UNVERIFIED` | `/select-campus`; PR #30 |
| AUTHZ-01 | Access Denied | `IMPLEMENTED_UNVERIFIED` | in-shell state (`shells/AccessStates.tsx`); PR #30 |
| RESOURCE-02 | Not Found (in the shell) | `IMPLEMENTED_UNVERIFIED` | `app/app/not-found.tsx`; PR #30 |

**Dashboards (5):** DASH-01 Executive Dashboard `NOT_STARTED` (an empty landing page exists from T01-09A; the specified content is not built). DASH-02 Admissions, DASH-03 Academic, DASH-04 Finance and DASH-05 Operations dashboards: `NOT_STARTED`.

**Grow (12)**

| ID | Screen | Status | Route / evidence |
|---|---|---|---|
| GROW-01 … GROW-06 | Marketing Dashboard, Campaigns, Campaign Detail, Website Dashboard, Website Pages, Website Page Editor | `NOT_STARTED` | — |
| GROW-07 | Lead Sources | `DEFERRED_BY_APPROVAL` | 02-1 scope (TASKS.md T04-01) |
| GROW-08 | Lead List | `IMPLEMENTED_UNVERIFIED` | `/app/admissions/leads` (INC-45: canonical page under Admissions); PR #32 |
| GROW-09 | Lead Detail | `IMPLEMENTED_UNVERIFIED` | `/app/admissions/leads/[leadId]`; PR #32 |
| GROW-10 | Lead Import | `DEFERRED_BY_APPROVAL` | 02-1 scope (TASKS.md T04-01) |
| GROW-11, GROW-12 | Content & Social, Social Content Calendar | `NOT_STARTED` | — |

**Admissions (15)**

| ID | Screen | Status | Route / evidence |
|---|---|---|---|
| ADM-01 | Admissions Dashboard | `NOT_STARTED` | slice 02-8 |
| ADM-02 | Lead Pipeline | `IMPLEMENTED_UNVERIFIED` | board view of the Leads page (route pending inspection); no drag-and-drop by scope; PR #32 |
| ADM-03, ADM-04 | Counselling Queue, Counselling Detail | `NOT_STARTED` | T04-03 |
| ADM-05 | Applications | `IMPLEMENTED_UNVERIFIED` | `/app/admissions/applications`; PR #32 |
| ADM-06 | Application Detail | `IMPLEMENTED_UNVERIFIED` | `/app/admissions/applications/[applicationId]`; PR #32 |
| ADM-07 | New Application | `IMPLEMENTED_UNVERIFIED` | `/app/admissions/applications/new` (T05 wizard); PR #32 |
| ADM-08 | Application Review | `IMPLEMENTED_UNVERIFIED` | route pending inspection (commit `e89ab78`, "screens ADM-05 … ADM-14"); PR #32 |
| ADM-09 | Document Verification | `IMPLEMENTED_UNVERIFIED` | `/app/admissions/documents`; PR #32 |
| ADM-10 | Admission Approval | `IMPLEMENTED_UNVERIFIED` | route pending inspection (`e89ab78`); PR #32 |
| ADM-11 | Students | `IMPLEMENTED_UNVERIFIED` | `/app/admissions/students`; PR #32 |
| ADM-12 | Student Profile | `IMPLEMENTED_UNVERIFIED` | `/app/admissions/students/[studentId]`; Fees section from 02-5 (PR #34) |
| ADM-13 | Student Admission | `IMPLEMENTED_UNVERIFIED` | route pending inspection (`e89ab78`); PR #32 |
| ADM-14 | Student Documents | `IMPLEMENTED_UNVERIFIED` | route pending inspection (`e89ab78`); PR #32 |
| ADM-15 | Student Communication | `NOT_STARTED` | slice 02-7 |

**Academics (27)**

| ID | Screen | Status | Route / evidence |
|---|---|---|---|
| ACA-01 | Courses | `IMPLEMENTED_UNVERIFIED` | `/app/academics/courses`; PR #32 |
| ACA-02 | Course Detail | `IMPLEMENTED_UNVERIFIED` | `/app/academics/courses/[courseId]`; PR #32 |
| ACA-03 | Create Course | `IMPLEMENTED_UNVERIFIED` | `/app/academics/courses/new` and `/[courseId]/edit`; PR #32 |
| ACA-04 | Course Curriculum | `NOT_STARTED` | stays in Phase 05 (L1) |
| ACA-05 … ACA-07 | Batches, Batch Detail, Create Batch | `IMPLEMENTED`, browser-verified 2026-11-20 (390-1440 px, Light/Dark/System; disposable database); uncommitted | slice 02-6 |
| ACA-08 … ACA-27 | Timetable … Academic Reports (20 entries) | `NOT_STARTED` | Phase 05 |

ACA-08 … ACA-27 individually: 08 Timetable, 09 Timetable Editor, 10 Attendance, 11 Attendance Detail, 12 Faculty, 13 Faculty Profile, 14 Faculty Allocation, 15 Training Dashboard, 16 Training Plan, 17 Training Session, 18 Training Session Detail, 19 Training Progress, 20 Examinations, 21 Examination Detail, 22 Examination Schedule, 23 Results, 24 Certificates, 25 Certificate Detail, 26 Certificate Generation, 27 Academic Reports.

**Finance (10)**

| ID | Screen | Status | Route / evidence |
|---|---|---|---|
| FIN-01 | Finance Dashboard | `DEFERRED_BY_APPROVAL` | ADR-0022 |
| FIN-02 | Fee Structure | `IN_PROGRESS` (merged) | `/app/finance/fee-structure`; PR #34 |
| FIN-03 | Fee Structure Detail | `IN_PROGRESS` (merged) | `/app/finance/fee-structure/[structureId]` (+ `/new`, `/edit`); PR #34 |
| FIN-04 | Invoices | `IN_PROGRESS` (merged) | `/app/finance/invoices` (+ `/new` from Student 360 Fees); PR #34 |
| FIN-05 | Invoice Detail | `IN_PROGRESS` (merged) | `/app/finance/invoices/[invoiceId]` (+ `/print`, print output verified by V-02); PR #34 |
| FIN-06 | Payments | `IN_PROGRESS` (merged) | `/app/finance/payments`; PR #34 |
| FIN-07 | Payment Detail | `IN_PROGRESS` (merged) | `/app/finance/payments/[paymentId]` (+ `/receipt`, print output verified by V-02); PR #34 |
| FIN-08 | Outstanding | `IN_PROGRESS` (merged) | `/app/finance/outstanding`; PR #34 |
| FIN-09 | Refunds | `DEFERRED_BY_APPROVAL` | ADR-0022 |
| FIN-10 | Finance Reports | `DEFERRED_BY_APPROVAL` | ADR-0022 |

FIN-02 … FIN-08 are `IN_PROGRESS` rather than `IMPLEMENTED_UNVERIFIED` because slice 02-5 itself stays `IN_PROGRESS` until its CI result and D18 journeys are recorded (TASKS.md 02-5).

**Compliance (8):** COM-01 Compliance Dashboard, 02 Requirements, 03 Requirement Detail, 04 Compliance Documents, 05 Inspections, 06 Inspection Detail, 07 Corrective Actions, 08 Compliance Audit. All `NOT_STARTED` (Phase 07).

**Placement (8):** PLC-01 Placement Dashboard, 02 Eligible Students, 03 Companies, 04 Company Detail, 05 Opportunities, 06 Opportunity Detail, 07 Placement Tracking, 08 Alumni. All `NOT_STARTED` (Phase 08).

**Communication (11):** COMMS-01 WhatsApp Workspace, 02 Email Workspace, 03 SMS, 04 Voice, 05 Conversation Detail, 06 Contacts, 07 Templates, 08 Template Editor, 09 Broadcasts, 10 Broadcast Detail, 11 Communication Analytics. All `NOT_STARTED` (Phase 09; provider credentials needed).

**Automation (6):** AUTO-01 Workflow List, 02 Workflow Builder, 03 AI Agents, 04 Agent Detail, 05 Executions, 06 Execution Detail. All `NOT_STARTED` (Phase 10).

**AI (9):** AI-01 AI Assistant, 02 AI Resolution, 03 AI Knowledge, 04 Knowledge Detail, 05 AI Analytics, 06 SQL / Data Agent, 07 AI Execution, 08 AI Configuration, 09 AI Guardrails. All `NOT_STARTED` (Phase 11).

**Analytics (6):** ANA-01 Executive, 02 Admissions, 03 Finance, 04 Academic, 05 Marketing, 06 AI Analytics. All `NOT_STARTED` (Phase 12).

**Tenant Administration (14)**

| ID | Screen | Status | Route / evidence |
|---|---|---|---|
| ADMIN-01 | Institute Profile | `NOT_STARTED` | API `GET /api/v1/institute` exists (T01-08); UI not built |
| ADMIN-02 | Institute Branding | `NOT_STARTED` | — |
| ADMIN-03 | Campuses | `IN_PROGRESS` | `/app/administration/campuses`; uncommitted; 24 page tests |
| ADMIN-04 | Campus Detail | `IN_PROGRESS` | `/app/administration/campuses/[campusId]`; uncommitted |
| ADMIN-05 | Users | `IN_PROGRESS` | `/app/administration/users`; uncommitted; 32 page tests |
| ADMIN-06 | User Detail | `IN_PROGRESS` | `/app/administration/users/[memberId]`; uncommitted |
| ADMIN-07 | Roles & Permissions | `IN_PROGRESS` | `/app/administration/roles` and `/[roleId]`, read-only; uncommitted; 19 page tests |
| ADMIN-08 … ADMIN-14 | Integrations, AI Configuration, Notifications, Billing, Audit Logs, Settings, Security | `NOT_STARTED` | API `GET /api/v1/audit-events` exists (T01-08) for ADMIN-12; UI not built |

### 5.3 Student Portal (10)

STU-01 Student Login, 02 Student Dashboard, 03 My Course, 04 Attendance, 05 Training, 06 Examinations, 07 Fees, 08 Certificates, 09 Placement, 10 Profile. All `NOT_STARTED` (Phase 13). Only the placeholder route `/student/[[...slug]]` exists.

### 5.4 Public Website (6)

PUB-01 Home, 02 Features, 03 Solutions, 04 Pricing, 05 Request Demo, 06 Contact. All `NOT_STARTED` (Phase 14). Only the placeholder route `/site/[[...slug]]` exists. INC-03: the PUB list partly describes the MTI 360 marketing website, not the Tenant Public Website (ADR-0003).

---

## 6. Module traceability (backend and frontend)

API operation counts come from the application's OpenAPI document (2026-10-28, 121 operations including `/health`). Permissions are the keys declared in each module's `permissions.py`.

| Module (backend) | API (operations) | Permissions | Migration | Backend tests (examples) | Screens and frontend tests | Status |
|---|---|---|---|---|---|---|
| `identity` (tenant auth, session, members) | `/auth/*` 8, `/session*` 6, `/members*` 11 | `member.invite`, `member.read`, `member.revoke`, `member.suspend`, `member.update` | 0004, 0006 (MFA), 0008 | `test_authentication_api`, `test_tenant_mfa_api`, `test_members_api`, `test_session_*`, `security/test_identity_boundaries` | AUTH-01 … 08 (`features/identity/*.test.tsx`); ADMIN-05/06 (`users.test.tsx`) | API `IMPLEMENTED_VERIFIED`; screens per §5 |
| `access` (roles, permissions) | `/roles*` 5, `/permissions` 1 | `role.assign`, `role.create`, `role.delete`, `role.read`, `role.update` | 0005, 0008 | `test_authorization_api`, `test_access_service`, `test_permission_sync`, `test_tenant_roles_campuses_api` | ADMIN-07 (`roles.test.tsx`) | API `IMPLEMENTED_VERIFIED`; role create/edit/delete UI not built |
| `institute` (institute, campuses) | `/institute` 1, `/campuses*` 4 | `campus.create`, `campus.read`, `campus.update` (institute read uses `tenant.profile.read`) | 0003, 0008 | `test_tenant_roles_campuses_api`, `test_tenancy_isolation` | ADMIN-03/04 (`campuses.test.tsx`); ADMIN-01 not built | API `IMPLEMENTED_VERIFIED` |
| `audit` | `/audit-events` 1, `/platform/audit-events` 1 | `audit.read` | 0002 | `test_audit_foundation`, `test_tenant_audit_api`, `test_platform_audit_api` | ADMIN-12, PLAT-36 not built | API `IMPLEMENTED_VERIFIED` |
| `tenants` (platform tenant management) | `/platform/tenants*` 6 | `tenant.create`, `tenant.read`, `tenant.suspend`, `tenant.reactivate`, `tenant.profile.read` | 0003, 0007 | `test_platform_tenants_api` (modified in the working tree), `security/test_platform_administration_boundaries` | PLAT-04/05/06 (`tenants.test.tsx`) | API `IMPLEMENTED_VERIFIED` (T01-07); working-tree test changes `IN_PROGRESS` |
| `platform_identity` | `/platform/auth*` 10, `/platform/session*` 3, `/platform/platform-users*` 8 | `platform_user.create`, `.read`, `.update`, `.suspend`, `.reactivate` | 0006, 0007 | `test_platform_auth_api`, `test_platform_users_api`, `test_platform_security`, `test_platform_bootstrap` | PLAT-01/02, PAUTH-01 … 07, PLAT-52 partial; PLAT-50 not built | API `IMPLEMENTED_VERIFIED` |
| `courses` | `/courses*` 5 | `course.manage`, `course.read` | 0009 | `test_courses_api`, `test_courses_leads_cross_tenant` | ACA-01/02/03 (`courses.test.tsx`) | API `IMPLEMENTED_VERIFIED` |
| `leads` | `/leads*` 12, `/lead-follow-ups/*` 3 | `lead.assign`, `lead.create`, `lead.read`, `lead.update` | 0009 | `test_leads_api`, `test_lead_follow_ups_api` | GROW-08/09, ADM-02 (`leads-list.test.tsx`, `lead-pages.test.tsx`) | API `IMPLEMENTED_VERIFIED` |
| `applications` | `/applications*` 11 | `application.create`, `.read`, `.review`, `.update` | 0010 | `test_applications_api`, `test_admissions_cross_tenant` | ADM-05 … 08, ADM-10 (`applications.test.tsx`; screen-to-test mapping pending inspection) | API `IMPLEMENTED_VERIFIED` |
| `documents` | `/documents*` 4 | `document.read`, `document.upload`, `document.verify` | 0010 | `test_documents_api`, `test_s3_storage` (real-S3 test runs separately) | ADM-09 (`documents.test.tsx`); ADM-14 (`students.test.tsx`) | API `IMPLEMENTED_VERIFIED` |
| `students` | `/students*` 4 | `admission.approve`, `student.read` | 0010 | `test_students_api` | ADM-11 … 13 (`students.test.tsx`; screen-to-test mapping pending inspection) | API `IMPLEMENTED_VERIFIED` |
| `finance` | `/fee-structures*` 5, `/invoices*` 5, `/payments*` 5, `/finance/summary` 1 | `fee_structure.manage`, `fee_structure.read`, `invoice.cancel`, `invoice.issue`, `invoice.read`, `payment.record`, `payment.reverse` | 0011 | `test_fee_structures_api`, `test_invoices_api`, `test_finance_integrity`, `test_finance_cross_tenant`, `test_sequence_periods` | FIN-02 … 08 (`fee-structure`, `invoices`, `payments` tests, `money.test.ts`) | `IN_PROGRESS` (merged; CI not recorded) |

Every module's routes are also covered by the security suites: `security/test_route_coverage`, `test_realm_guards`, `test_cross_tenant_registry` (with `tests/cross_tenant_registry.py`) and `test_authorization_boundaries`. Migration `0001_baseline` starts and protects the migration history (no application tables).

**Mapping status of this table:** module level, inspected 2026-10-28. Endpoint ↔ permission ↔ test mappings per route are **pending inspection** (§10).

---

## 7. Cross-cutting requirements

| Requirement (source) | Implementation evidence | Status |
|---|---|---|
| Tenant isolation (CLAUDE.md §5–§6, §55; ADR-0004, ADR-0014) | RLS and composite tenant keys (migrations 0003+); `test_tenancy_isolation`, `security/test_cross_tenant_registry` (fails when a business route is not registered), per-slice cross-tenant suites | `IMPLEMENTED_VERIFIED` for the delivered modules (CI on `2ea72f6`); finance suite local only |
| Authentication and sessions (§9; ADR-0010, ADR-0015, ADR-0017) | identity and platform_identity modules; `test_rate_limiting`, `test_session_*`, `security/test_identity_boundaries` | `IMPLEMENTED_VERIFIED` (API); D18 browser journeys deferred |
| MFA and step-up (D6-5, D7-4) | platform MFA and step-up; tenant MFA opt-in (T01-09C) | API `IMPLEMENTED_VERIFIED`; the real-browser step-up prompt is an R1 check |
| Authorization and RBAC (§10–§11; ADR-0011, ADR-0016) | permission requirements per route; `security/test_authorization_boundaries`, `test_realm_guards`; no role-name gating | `IMPLEMENTED_VERIFIED` (delivered routes) |
| Audit (§51; ADR-0013) | audit module; audit read APIs | `IMPLEMENTED_VERIFIED` (API); audit screens not built |
| File uploads (§50; ADR-0021, INC-22) | documents validation pipeline, private object storage, `test_documents_api` | `IMPLEMENTED_VERIFIED` (admission documents) |
| Background jobs and outbox (§53) | none; infrastructure decision D4 defers `worker` | `NOT_STARTED` (blocks 02-4, 02-7) |
| Responsive, themes, accessibility gate (§13–§19, §38, §57) | automated axe in Light and Dark in page tests; no recorded four-width, three-theme browser gate | `IN_PROGRESS` (no screen browser-verified) |
| Observability, health, monitoring (§68) | `/health` endpoint; request logging middleware (`app/core/middleware.py`) | `IN_PROGRESS`; monitoring and alerting `NOT_STARTED` (Phase 17) |
| AI governance (§42–§47) | none | `NOT_STARTED` (Phase 11) |
| Dependency security (§74; T16-10) | audit workflow; certifi PYSEC-2026-4320 open (DEVELOPMENT-STATUS.md, PR #36 entry) | `IN_PROGRESS` |
| Backups and recovery (§86; T17-03, T17-07) | none | `NOT_STARTED` |

---

## 8. Open dependencies and inconsistencies

Decisions that block or condition scope (by existing ID; details in [spec-inconsistencies.md](spec-inconsistencies.md)):

| ID | Subject | Blocks |
|---|---|---|
| INC-01 | Screen count (217 vs ~222) | Progress metrics only |
| INC-03 | Public Website meaning (decided by ADR-0003; specs not updated) | Phase 14 screen list |
| INC-06 | Tenant role names | Business role templates |
| INC-07 | Subscription plan names | T02-06, T02-07, PLAT-04 Plan column |
| INC-27 | Tenant Public Website route prefix | 02-4, Phase 14 |
| INC-30 | Platform role names | T02-23 |
| INC-32 | Tenant lifecycle transitions | T02-05 |
| INC-40 | Campus status vocabulary | Campus archiving (ADMIN-04) |
| INC-48, INC-49 | Tax treatment; financial-year date basis | Production use of Finance |
| INC-50 | Tenant administration screens | 02-C tenant part (in progress) |

External dependencies: WhatsApp, SMS, voice, email-provider, payment-gateway and AI-provider credentials; a production hosting target.

The register currently holds 50 entries: 26 `OPEN`, 18 `DECIDED-BY-ADR`, 5 `CLOSED` and 1 `RESOLVED`.

---

## 9. Open tracker items (not corrected in R0)

R0 corrected five items (DEVELOPMENT-STATUS.md §37, 2026-10-28). These remain and need a decision or a later documentation task:

1. **T01-10 label.** `READY_WITH_D18_DEFERRED` is not one of the statuses in TASKS.md §5 or DEVELOPMENT-STATUS.md §4.
2. **No CI evidence recorded for PR #31, #34, #35, #36 and #37.** Branch protection is not applied (docs/architecture/ci.md §8), so a merge alone does not prove that `ci-ok` passed. The GitHub CLI is not installed locally, so the results could not be read in R0.
3. **Milestones.** M2 … M11 are defined by the original phase numbers; the re-sequenced Phase 02 Admissions MVP has no milestone ID.
4. **DEVELOPMENT-STATUS.md §10.** Phase 02 (Platform Control Plane) shows `NOT_STARTED` and "0 / 23", although T02-04 is `IN_PROGRESS`.
5. **T02-01 Platform Shell and T02-02 Platform Login** show `NOT_STARTED`, although T01-09B delivered the guarded platform console and PLAT-01/02. The overlap is not reconciled.
6. **DEVELOPMENT-STATUS.md §6 Current Objective** still describes the Phase 00/01 foundation sequence.
7. **DEVELOPMENT-STATUS.md §26 Cross-cutting status** shows every area as `NOT_STARTED`; §7 above has the evidence.
8. **DEVELOPMENT-STATUS.md §30 … §32** (enterprise, tenant and AI component status) are not reconciled with the components built since Phase 00 (pending inspection).
9. ~~**TASKS.md Phase 02 slice table** has no row for 02-3 (Seed + demo hardening), which DEVELOPMENT-STATUS.md §9A lists.~~ Resolved 2026-10-31: the row was added.

---

## 10. Outstanding mapping work

| Work | Trigger | State |
|---|---|---|
| Per-route mapping: operation → permission → campus scope → audit event → tests, for every module in §6 | Each slice that touches a module | Pending inspection |
| Routes for ADM-02, ADM-08, ADM-10, ADM-13, ADM-14, PAUTH-04, PAUTH-05 | R1 or the next Admissions slice | Pending inspection |
| Acceptance criteria of each completed slice (02-1, 02-2, 02-5 readiness plans) → test names | When the slice's D18 journeys are run | Pending inspection |
| Phase 00 foundation components → §56 browser checks | A design-system review task | Pending inspection |
| PRD and APP-FLOW workflows → screens (beyond the screen IDs in §5) | Before each new phase | Pending inspection |
| Browser evidence (§57) per screen | R1 (02-C), then each slice | Not started; no screen verified |
| CI evidence for PR #31 and #34 … #37 | When CI results are available | Open (§9 item 2) |

---

## 11. Maintenance

- Update this document in the same change as the task's TASKS.md and DEVELOPMENT-STATUS.md updates.
- Change a status only with evidence: a merge commit, a recorded test or CI result, or a recorded browser check. Name the evidence in the row.
- Never mark a screen `IMPLEMENTED_VERIFIED` without a recorded §57 browser gate, and never record a browser check that the user has not run.
- Keep requirement text in the source documents; link to it here.
