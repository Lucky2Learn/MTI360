# Phase 02 Master Readiness & Module Sequencing

- **Status:** Readiness review (2026-10-08), on `main` at `9009db5` (T01 complete: PR #31). Documentation only. No code, migration, manifest or runtime change.
- **Sources verified:** PRD.md (§10–13, §26–39, §60, §72–77, §85), APP-FLOW.md (§5, §8–21, §26, §36–46), UI-SCREENS.md (§12–18, §28), TASKS.md (Phases 02–05), ARCHITECTURE.md (§7, §12–15, §31, §49, phase list), CLAUDE.md, DESIGN-SYSTEM.md (templates), ADR-0001 … ADR-0019, `docs/architecture/*` (tenancy, authorization, backend-foundation, repository-structure, environments, spec-inconsistencies), migrations 0001–0008, `backend/app/**`, `frontend/src/**`, the dev seed, and git history (158 commits on `main`).
- **Audience:** the product owner, and the Claude Code session that implements the next slice.

---

## 1. Executive Summary

T01 delivered a complete, verified **security and tenancy foundation**, but **no business functionality**. There are no leads, courses, applications, students, documents or fees, and every tenant navigation page except the empty Dashboard is an `UNRELEASED` placeholder.

The repository's own specifications agree on what the business core is:

- **PRD §72** "Commercial MVP — GROW + ADMIT";
- **APP-FLOW §43** "MVP Application Flow, Phase 1": `Courses → Leads → Lead 360 → … → Application → Documents → Student`;
- **TASKS Phase 04** "Admissions".

They disagree on order. TASKS.md puts the **Platform Control Plane** (Phase 02) and the **Tenant Foundation** (Phase 03) first, and **Courses** in Phase 05, *after* Admissions. That order cannot produce a usable product: an application needs a course to apply for (APP-FLOW §16 "Course Selection").

**Recommendation.** The first vertical slice is **Admissions Core**, operated by staff:

```text
Course catalogue (minimal) → Lead → Follow-up / counselling → Application (staff-assisted)
→ Documents → Verification → Admission approval → Student (Student 360 basics)
```

Two thin onboarding enablers run alongside it, both on existing T01 APIs:

- tenant member and role administration screens (ADMIN-05/06/07);
- a minimal platform tenant-provisioning UI.

Fees, batches, WhatsApp/email, the public enquiry form, dashboards and AI follow in that order, as separate slices. Nothing in T01 needs redesigning.

**Readiness verdict:** `READY_FOR_IMPLEMENTATION` once the seven decisions in §28 are confirmed. All are product or security choices with a recommended answer; none needs a new ADR cycle beyond recording it.

---

## 2. Current MTI 360 State

Inventory verified against the code (not the roadmap).

| Category | What exists |
|---|---|
| **A. Implemented (backend + frontend)** | Tenant and platform sign-in, MFA, recovery codes, step-up, password reset, invitations, session, institute and campus selection; guarded `/app` and `/platform` shells; permission-aware navigation; tenant "Sign-in security" (T01-09C) and platform "Sign-in security" (partial PLAT-52) |
| **B. Partially implemented** | Tenant Dashboard (DASH-01, empty state only); platform Overview (empty state) |
| **C. Architecture only** | Tenant Public Website (`/api/v1/public/*`: router exists, no routes; `tenant_domains` table not created; INC-27 route prefix open); Student Portal realm (router denies everything); object storage (S3 settings and local SeaweedFS service, **no client code**); background jobs (`core/jobs` and the queue library deferred, D4; transactional outbox planned); event bus (ARCHITECTURE §14, not built); AI platform |
| **D. UI only** | Placeholder pages for every tenant module (Grow, Admissions, Academics, Finance, Compliance, Placement, Communication, Automation, AI, Analytics), all `UNRELEASED`; `/site/*` structural preview; design-system showcase; marketing website (root `index.html`, separate, ADR-0003) |
| **E. Backend only (API, no screens)** | Tenant administration: members (invite, resend, suspend, reinstate, revoke, campus scope, roles), roles (CRUD, permission catalogue), campuses (list, create, update), institute summary, tenant audit read (T01-08). Platform administration: tenant provisioning, list, detail, suspend, reactivate, owner invitation; platform users; platform audit (T01-07) |
| **F. Not implemented** | Courses, leads, counselling, applications, documents, verification, admissions, students, batches, timetable, attendance, faculty, exams, certificates, finance, compliance, placement, communication, workflows, AI, analytics, billing |

**Product functionality completion: 0%** (as DEVELOPMENT-STATUS.md also states). T01 is the prerequisite, not the product.

---

## 3. What T01 Provides (reuse, do not rebuild)

| Capability | Where | Use in Phase 02 |
|---|---|---|
| Realm routers, guards and `RequestContext` (tenant, principal, permissions, campus scope) | `app/api/realms.py`, `app/core/context.py` | Every new tenant route is mounted on the tenant `AUTHENTICATED` router |
| `authorize(context, permission, resource)` with tenant and campus semantics (D-B1) | `app/core/authz` | Resources expose `tenant_id` and `campus_id`. **A NULL `campus_id` is visible to anyone holding the campus-scoped permission** (engine behaviour) |
| Tenant RLS, ORM tenant filter, tenant-scoped repository, `context_transaction` | `app/core/tenancy`, `app/core/db` | Every new table: `tenant_id`, RLS on the trusted tenant, composite foreign keys within the tenant |
| Optimistic locking (`version`, `409 CONFLICT`), offset pagination (D13), error envelope, request IDs | `app/core` | All mutable business records and lists |
| Append-only audit with security and business categories (ADR-0013) | `app/core/audit` | Admission decisions, verification, status changes |
| Permission registry plus migration-only sync (D-B3, D-B4); system role templates (D-B2) | `app/modules/access` | New admission permissions and new role templates (§13) |
| Email sender (SMTP, fake for tests), post-commit dispatch, at most once | `app/integrations/email` | Not needed by the first slice (§16) |
| Redis rate limiting | `app/core/ratelimit.py` | Public enquiry endpoint (later slice) |
| Same-origin proxy (realm-scoped cookies), server session gate, `TenantSessionProvider.request` (T01-05 error matrix), `PermissionGate`, requirement map | `frontend/src/lib/**` | Every new page and mutation |
| Design system: DataTable, FilterBar, Pagination, Search, Tabs, Drawer, Dialog/AlertDialog, FileUpload (client checks), Timeline, Kpi, Badge, EmptyState/ErrorState, Skeleton, Combobox, DatePicker, CopyButton, SecretValue/CodeList; shells; T16 template | `frontend/src/design-system`, `frontend/src/shells` | Build the T02/T03/T05/T06 page templates **from these**, not new components |
| Dev seed (institutes, campuses, members, system roles) | `backend/app/seed.py`, `database/seeds/dev.json` | Extend with courses, leads and applications for the demo |
| CI: CodeQL, gitleaks, dependency audit, PostgreSQL/Redis integration, route-coverage and cross-tenant meta-tests | `.github/workflows` | Every new route needs a cross-tenant test case (tenancy.md) |

**Data access on the frontend is already decided** (repository-structure.md §2): server components call the backend server-side; **TanStack Query** for client server-state; **Zod** for form UX validation; **TypeScript API types generated from FastAPI's OpenAPI**. None is installed yet (deferred by T01-09A). The first slice installs and wires them; this is not a new decision.

---

## 4. Business Domain Map

Derived from PRD §17–§70, the APP-FLOW flows and the tenant navigation (`frontend/src/shells/experiences/tenant.ts`).

| Pillar | Domains (navigation) | Core entities (PRD/APP-FLOW) |
|---|---|---|
| **GROW** | Marketing, Campaigns, Website, Leads, Content & Social | Campaign, Lead source, Website page, Enquiry, Lead |
| **ADMIT** | Leads (pipeline), Counselling, Applications, Documents, Students | Lead, Follow-up, Counselling record, Application, Document, Verification, Admission, Student |
| **RUN — Academics** | Courses, Batches, Timetable, Attendance, Faculty, Training, Examinations, Certificates | Course, Batch, Allocation, Session, Attendance, Faculty, Exam, Result, Certificate |
| **RUN — Finance** | Fee Structure, Invoices, Payments, Outstanding, Refunds, Reports | Fee structure, Invoice, Payment, Receipt, Refund |
| **COMPLY** | Compliance dashboard, Requirements, Documents, Inspections, Corrective actions, Audit | Requirement, Compliance document, Inspection |
| **RUN — Placement** | Placement, Companies, Opportunities, Alumni | Company, Opportunity, Placement |
| **AUTOMATE** | Communication (WhatsApp, Email, SMS, Voice, Templates), Automation, AI, Analytics | Message, Template, Workflow, Agent, Execution |
| **Administration** | Institute, Campuses, Users, Roles, Audit, Settings | **exists (T01)**: tenant, campus, membership, role, audit |
| **Experiences** | Student Portal (STU-*), Tenant Public Website (PUB-*) | Student account (separate realm, ADR-0005); verified domain |

**Spec overlaps to resolve in implementation, not redesign:**
- "Leads" appears under both Grow and Admissions in the navigation, and GROW-08/09 (Lead List/Detail) overlap ADM-03/04 (Counselling Queue/Detail). Use **one Lead record** (GROW-09 is the Lead 360). Counselling is follow-ups and notes on that lead. ADM-03 is the counsellor's filtered queue.
- DASH-02 and ADM-01 are both "Admissions Dashboard". Build one (later).
- The Admissions navigation group carries a hard-coded demo badge ("12 new enquiries"). Replace it with real data or remove it when the module ships.

---

## 5. Domain Dependency Graph

```text
                        (exists) Tenant ─ Campus ─ Members/Roles ─ Audit
                                           │
                                   ┌───────┴────────┐
                                   ▼                ▼
                         Course catalogue      Lead sources (enum)
                                   │                │
                                   └──────┬─────────┘
                                          ▼
                                        Lead ──► Follow-up / Notes (Activity)
                                          │ convert (staff)
                                          ▼
                                     Application ──► Documents ──► Verification
                                          │ approve
                                          ▼
                                      Admission ──► Student (person) ──► Student 360
                                          │                 │
                           ┌──────────────┼─────────────────┤
                           ▼              ▼                 ▼
                    Fee/Invoice/     Batch allocation   Communication
                    Payment (V1)     (needs Batch, V1)  (events, V1.5)
                                          │
                                          ▼
                        Timetable → Attendance → Exams → Certificates → Placement
```

| Dependency | Kind | Notes |
|---|---|---|
| Application → Course | **Hard** | APP-FLOW §16 "Course Selection"; PRD §29 eligibility depends on the course |
| Lead → Course | Soft | "Interested course" (PRD §27); a lead may exist without one |
| Application → Lead | Soft | A walk-in may start an application directly; conversion links them when they exist |
| Documents → Application | **Hard** (first slice) | Student documents later reuse the same document capability |
| Admission → Application (approved) | **Hard** | APP-FLOW §18 |
| Student → Admission | **Hard** | The student is created at admission (§28 L3) |
| Fee/Payment → Admission | Hard for Finance; **not for Admission** in the MVP (§17, §28 L3) | |
| Batch allocation → Batch → Course | **Hard** | Batch is an Academics entity; allocation follows admission |
| Communication → domain events | Optional integration | Triggers on lead created, application submitted and so on (APP-FLOW §42) |
| AI Admission Agent → courses (knowledge), leads, communication | Future | Needs real data and channels first |
| Public enquiry → Lead, `tenant_domains` | Optional integration | Leads can be entered by staff from day one |
| Platform provisioning UI → tenant API (exists) | Reusable | Needed to onboard a real customer without API calls |

---

## 6. Candidate First Vertical Slices

Scores: H = high, M = medium, L = low (risk: H is bad).

| Criterion | A Marketing→Lead→Applicant→Admission | B Lead→Applicant→Application→Admission→Student | C Admissions-first (no leads) | D Academics-first | E Finance-first | F Website→Lead→Admission→Student→Batch | **G Admissions Core (recommended)** |
|---|---|---|---|---|---|---|---|
| Business value | H | H | M | M | M | H | **H** |
| User value (counsellor, admissions) | M | H | M | L | L | H | **H** |
| Revenue value (sells MTI 360) | H | H | M | L | M | H | **H** |
| Technical dependencies | H (public domains, TLS, abuse controls) | M | M | M | H (needs admissions) | **very H** | **M** |
| Screens (approx.) | ~14 | ~16 | ~10 | ~12 | ~10 | ~24 | **~17 incl. courses** |
| APIs (approx.) | ~25 | ~30 | ~20 | ~20 | ~18 | ~45 | **~32** |
| Database complexity | M | M | M | M | M | H | **M** |
| Reusability (templates, activity, documents) | M | H | M | M | L | H | **H** |
| Time to MVP | Slow | Medium | Fast | Medium | Slow | Slowest | **Medium** |
| Ability to demo a real workflow | M (stops at admission, gap at course) | H | M | L (no students arrive) | L (nothing to bill) | H | **H** |
| Ability to onboard a real MTI | L (missing course) | M (missing course) | M | L | L | H | **H** (with the onboarding enablers) |
| Future extensibility | M | H | M | M | M | H | **H** |
| Risk | H | M | M | M | H | H | **L–M** |

- **A** front-loads the riskiest piece (anonymous public intake, domains) and still lacks courses.
- **B** is close to right, but it has no course catalogue (a hard dependency) and assumes a separate Applicant entity the specs don't require (§12).
- **C** without leads loses the GROW half of the commercial MVP (PRD §72).
- **D, E**: nothing flows into them yet.
- **F** is the right end state but too large for one slice.
- **G** is B plus the minimal course catalogue, staff-assisted application and an explicit stop point. Public capture, finance and batches come next.

---

## 7. Recommended First Vertical Slice

**Admissions Core (G).** Staff-operated, from enquiry to admitted student, on a minimal course catalogue:

1. **Course catalogue (minimal)**: create, edit, activate and archive courses (name, code, category Pre-Sea/Post-Sea, duration, eligibility text, status). No curriculum, fees or batches.
2. **Lead management**: manual lead entry, duplicate warning, source, interested course, campus, assignment to a counsellor, status pipeline with recorded transitions, follow-ups (due date, outcome) and notes, Lead 360.
3. **Application**: started from a lead ("Convert to applicant") or directly, in a staff-assisted wizard (personal, contact, education, course and campus, declaration), saved as a draft, then submitted.
4. **Documents and verification**: upload against an application (type, file), verify or reject with a reason, re-upload.
5. **Review and admission**: review an application (approve, reject, or correction required), then approve admission (permission-gated), which generates the admission number and creates or links the **Student**.
6. **Students**: list, and Student Profile with Personal, Admission, Course, Documents and Activity sections. The other ADM-12 sections show intentional empty states until their modules ship.

**Why:** it is the PRD's commercial MVP core (GROW + ADMIT), the APP-FLOW Phase 1 flow and TASKS Phase 04, in the order the dependencies require. It needs no new infrastructure beyond object storage, it is demonstrable end to end, and it is what a real institute's admissions office uses daily.

---

## 8. First Real Customer Journey

Derived from APP-FLOW §8–§18 and §41. **Bold** steps are in the first release.

```text
**Platform admin provisions the institute (owner invited)**        T01 API + thin UI (§22, track C)
**Owner signs in, adds campuses, invites counsellors**            T01 API + ADMIN-05/06/07 screens
**Admissions manager creates courses**                            Slice 1
Prospective student enquires (website / phone / walk-in / WhatsApp)
**Counsellor (or manager) enters the lead**                       Slice 1 (manual)
   (public website enquiry form creates the lead)                 Slice 4
**Duplicate warning → lead assigned to a counsellor**
**Counsellor contacts, records follow-ups and notes, qualifies**
**Converts to applicant: application started (staff-assisted)**   Slice 2
**Personal → contact → education → course/campus → declaration → submit**
**Documents uploaded (CDC, passport, marksheets, medical …)**
**Verification: verify / reject (reason) / re-upload**
**Application review: approve / reject / correction required**
**Admission approved → admission number → Student created**       ← FIRST RELEASE STOPS HERE
Fee plan → invoice → payment (manual record) → receipt            V1 (Finance-lite)
Batch allocation → Enrolled                                       V1 (Batches)
Welcome communication (email / WhatsApp)                          V1.5
```

**The first usable release stops at "Admission approved → Student created".** At that point an institute can run its entire admissions desk in MTI 360. Fees and batch allocation are the next two slices; they don't block real use of admissions.

---

## 9. Phase 02 MVP Boundary

**In scope (MVP = Slices 1–2 plus onboarding enablers)**
- Minimal course catalogue.
- Leads: manual entry, CSV-free; sources as a fixed list; assignment; pipeline; follow-ups; notes; Lead 360; duplicate warning.
- Staff-assisted application: draft, submit, review.
- Documents on applications: upload, verify, reject, re-upload; secure storage and download.
- Admission approval with admission number; Student record (create or link) and Student 360 basics.
- Shared capabilities: page templates T02/T03/T05/T06, activity timeline and notes, status transitions, campus-scoped list filtering, file storage.
- Admission permissions and two business role templates.
- Tenant member/role admin screens; minimal platform tenant-provisioning screens.
- Seed data for the demo; cross-tenant and campus-scope tests for every route.

**Out of scope for the MVP**
- Applicant self-service and online application.
- Public website builder.
- Campaigns, content and social.
- WhatsApp, SMS, voice and email automation.
- Workflow builder and AI.
- Lead scoring.
- CSV import.
- Analytics dashboards beyond simple counts.
- Finance, batches and every other Academics module.
- Student Portal; compliance; placement; billing and subscriptions.

**Deferred (ordered):**
1. Public enquiry capture (Slice 4).
2. Finance-lite.
3. Batches and allocation.
4. Admissions dashboard.
5. Email and WhatsApp communication.
6. Lead import (GROW-10).
7. Applicant self-service (needs the student/public realm).
8. AI Admission Agent.

---

## 10. Required Screens

IDs from UI-SCREENS.md; templates as specified there. "Status": all are UI placeholders today except where noted. Routes follow the existing tenant navigation (`/app/<group>/<page>`), with detail routes nested under them.

| Priority | ID | Screen | Persona | Purpose | Route | Depends on | Backend |
|---|---|---|---|---|---|---|---|
| P0 | ACA-01 | Courses | Admissions manager | Course catalogue list | `/app/academics/courses` | — | Course list |
| P0 | ACA-02 | Course Detail | Admissions manager, counsellor | View or edit a course | `/app/academics/courses/[id]` | ACA-01 | Course read/update |
| P0 | ACA-03 | Create Course | Admissions manager | Create a course (T04 form) | `/app/academics/courses/new` | — | Course create |
| P0 | GROW-08 | Lead List | Counsellor, manager | Leads with filters, search, assignment | `/app/admissions/leads` (single Leads entry, §4) | Courses | Lead list/create |
| P0 | GROW-09 | Lead Detail (Lead 360) | Counsellor | Profile, course interest, status, follow-ups, notes, activity, applications | `/app/admissions/leads/[id]` | GROW-08 | Lead read/update, transitions, follow-ups, notes |
| P0 | ADM-02 | Lead Pipeline | Manager, counsellor | Kanban by status (T06) | `/app/admissions/pipeline` | GROW-08 | Lead list grouped by status, transitions |
| P0 | ADM-07 | New Application | Counsellor | Staff-assisted wizard (T05), draft and resume | `/app/admissions/applications/new?lead=` | Lead, Course | Application create/update |
| P0 | ADM-05 | Applications | Counsellor, manager | List by status | `/app/admissions/applications` | — | Application list |
| P0 | ADM-06 | Application Detail | Counsellor, reviewer | Sections, documents, activity, actions | `/app/admissions/applications/[id]` | ADM-05 | Application read, submit |
| P0 | ADM-09 | Document Verification | Verifier | Document queue and verify/reject | `/app/admissions/documents` (queue) plus a panel on ADM-06 | Documents | Document list, verify, reject, download |
| P0 | ADM-08 | Application Review | Admissions manager | Decision: approve, reject, correction | panel/route on ADM-06 | ADM-09 | Review decision |
| P0 | ADM-10 | Admission Approval | Admissions manager | Confirm admission (permission-gated) | panel/route on ADM-06 | ADM-08 | Admit |
| P0 | ADM-11 | Students | Admissions, staff | Student list | `/app/admissions/students` | — | Student list |
| P0 | ADM-12 | Student Profile | Staff | Student 360 (Personal, Admission, Course, Documents, Activity; other sections empty-state) | `/app/admissions/students/[id]` | ADM-11 | Student read, timeline |
| P0 | ADM-13 / ADM-14 | Student Admission / Documents | Staff | Sections of ADM-12 | tabs of ADM-12 | ADM-12 | Admission, documents |
| P0 (onboarding) | ADMIN-05 / 06 / 07 | Users, User Detail, Roles & Permissions | Owner, admin | Invite counsellors, assign roles and campuses | `/app/administration/*` | — | **exists (T01-08)** |
| P0 (onboarding) | PLAT-04 / 05 / 06 (minimal) | Tenant List, Tenant 360 (summary), Create Tenant (owner invite only) | Super Admin | Provision a real institute | `/platform/tenants*` | — | **exists (T01-07)** |
| P1 | ADM-03 | Counselling Queue | Counsellor | "My follow-ups due" (filtered Lead List) | `/app/admissions/counselling` | GROW-09 | Follow-up list |
| P1 | ADM-01 | Admissions Dashboard | Manager | Counts by status, follow-ups due, conversions | `/app/admissions` | Slices 1–2 | Aggregates |
| P1 | ADMIN-01 / 03 / 04 | Institute Profile, Campuses, Campus Detail | Owner | Read institute; manage campuses | `/app/administration/*` | — | **exists** |
| P1 | GROW-07 | Lead Sources | Manager | Configure sources (fixed list in the MVP) | — | — | later |
| P2 | GROW-10, ADM-04, ADM-15, ACA-04…07, FIN-*, PUB-* | Lead import, counselling detail, student communication, curriculum, batches, finance, public pages | | | | | later slices |

ADM-08/09/10 keep their IDs. Because they share the T03 detail template, they can render as panels and actions of ADM-06 (no redesign, CLAUDE §59).

---

## 11. Required APIs

All under `/api/v1` (tenant realm, `AUTHENTICATED` router), CSRF on unsafe methods, tenant from session only, lists paginated (D13), mutations with `version` (409), audited where marked. Permissions are defined in §13.

| P | Method | Endpoint | Purpose | Permission | Entity |
|---|---|---|---|---|---|
| P0 | GET / POST | `/courses` | List (status filter, search) / create | `course.read` / `course.manage` | Course |
| P0 | GET / PATCH | `/courses/{id}` | Read / update (incl. status ACTIVE/ARCHIVED) | `course.read` / `course.manage` | Course |
| P0 | GET / POST | `/leads` | List (status, owner, course, campus, source, due, search) / create (returns duplicate candidates) | `lead.read` / `lead.create` | Lead |
| P0 | GET / PATCH | `/leads/{id}` | Read / update profile | `lead.read` / `lead.update` | Lead |
| P0 | POST | `/leads/{id}/transition` | Status change with reason (recorded) | `lead.update` | Lead |
| P0 | POST | `/leads/{id}/assign` | Assign owner (counsellor) and campus | `lead.assign` | Lead |
| P0 | GET / POST | `/leads/{id}/follow-ups`; PATCH `/follow-ups/{id}` | Schedule / complete with outcome | `lead.update` | Follow-up |
| P0 | GET / POST | `/leads/{id}/activity` (notes) | Timeline and add note | `lead.read` / `lead.update` | Activity |
| P0 | GET / POST | `/applications` | List / create (from lead or direct) | `application.read` / `application.create` | Application |
| P0 | GET / PATCH | `/applications/{id}` | Read / save draft sections | `application.read` / `application.update` | Application |
| P0 | POST | `/applications/{id}/submit` | Validate completeness → SUBMITTED | `application.update` | Application |
| P0 | POST | `/applications/{id}/review` | APPROVED / REJECTED / CORRECTION_REQUIRED + reason | `application.review` | Application (audited) |
| P0 | GET / POST | `/applications/{id}/documents` | List / upload (server-validated, stored) | `document.read` / `document.upload` | Document, StoredFile |
| P0 | GET | `/documents?status=UNDER_REVIEW` | Verification queue | `document.read` | Document |
| P0 | GET | `/documents/{id}/download` | Short-lived download URL or stream (attachment) | `document.read` | Document |
| P0 | POST | `/documents/{id}/verify`, `/documents/{id}/reject` | Verification decision (+ reason) | `document.verify` | Document (audited) |
| P0 | POST | `/applications/{id}/admit` | Admission number, Admission, Student create-or-link | `admission.approve` | Admission, Student (audited) |
| P0 | GET | `/students`, `/students/{id}` | List / Student 360 | `student.read` | Student |
| P0 | GET | `/students/{id}/activity` | Timeline | `student.read` | Activity |
| P1 | GET | `/admissions/summary` | Dashboard counts | `lead.read` + `application.read` | aggregates |
| exists | — | `/members*`, `/roles*`, `/permissions`, `/campuses*`, `/institute`, `/audit-events` | Tenant admin (T01-08) | existing | — |
| exists | — | `/platform/tenants*` | Provisioning (T01-07) | existing (step-up where locked) | — |
| Slice 4 | POST | `/api/v1/public/enquiries` | Anonymous enquiry → Lead in the host-resolved tenant | none (public realm), rate-limited | Lead |

No generic "entity" or "workflow" API. State changes are explicit, named commands (`transition`, `submit`, `review`, `admit`, `verify`), each authorizing its own permission.

---

## 12. Required Domain Entities

Conceptual only. The database design belongs to the implementation task. Every entity has `tenant_id`, RLS on the trusted tenant, composite foreign keys within the tenant, and a UUID.

| Entity | Purpose | Key relationships | Campus | Lifecycle | Audit | `version` | When |
|---|---|---|---|---|---|---|---|
| **Course** | Catalogue item | — | none (tenant-wide; `campus_id` NULL by design) | DRAFT → ACTIVE → ARCHIVED | business event on status change | yes | **now** |
| **Lead** | Prospect | interested Course (opt), owner membership (opt), campus (opt) | **nullable** (institute pool until assigned, L6) | NEW → CONTACTED → QUALIFIED → COUNSELLING → INTERESTED → APPLICATION → ADMITTED; LOST, DEFERRED, NOT_ELIGIBLE, DUPLICATE (APP-FLOW §10) | every transition recorded (APP-FLOW §10) | yes | **now** |
| **Follow-up** | Scheduled counsellor task on a lead | Lead, assignee | inherits lead | OPEN → DONE (outcome) / CANCELLED | activity | yes | **now** |
| **Activity** (shared) | Business timeline: notes, transitions, uploads, decisions | polymorphic subject (lead, application, student) within the tenant | inherits subject | append-only | — (is itself a record) | no | **now** |
| **Application** | Per-course application with the applicant's details as entered | Lead (opt), Course, campus | **required at submit** | DRAFT → SUBMITTED → UNDER_REVIEW → DOCUMENT_VERIFICATION → ELIGIBLE → APPROVED → ADMITTED; REJECTED, CORRECTION_REQUIRED, NOT_ELIGIBLE (APP-FLOW §16) | submit, decisions | yes | **now** |
| **Document** | A required or optional document on an application (later the student) | Application, StoredFile, document type | inherits | UPLOADED → UNDER_REVIEW → VERIFIED / REJECTED → re-upload (PRD §39) | verify/reject (who, reason) | yes | **now** |
| **StoredFile** (shared) | Object-storage metadata | — | inherits owner | immutable | upload | no | **now** |
| **Admission** | The admission decision for one application/course | Application (1:1), Student, Course, campus | required | ADMITTED (later ENROLLED / CANCELLED / DEFERRED) | yes (financially relevant later) | yes | **now** |
| **Student** | The person, reused across courses (Post-Sea students return for refreshers) | Admissions (1:n), source Lead(s) | **home campus** of the first admission | ACTIVE (later ALUMNI and others) | creation, merge/link | yes | **now** |
| Admission-number counter | Tenant-scoped, gap-tolerant sequence | — | per tenant (or per campus, L-decision in implementation) | — | — | row lock | **now** |
| Lead source | Fixed enum in the MVP | — | — | — | — | — | enum now, table P1 |
| Applicant (separate) | — | — | — | — | — | — | **not needed** (§28 L2) |
| Fee structure, Invoice, Payment, Receipt | Finance-lite | Admission, Course | campus | — | yes | yes | V1 |
| Batch, Allocation | Academics | Course, campus, Admission | campus | — | yes | yes | V1 |
| `tenant_domains` | Verified host → tenant (ADR-0004) | Tenant | — | PENDING → VERIFIED | yes | yes | Slice 4 |

---

## 13. RBAC / Permissions

**Existing** tenant permissions (15) cover administration only: `member.*`, `role.*`, `campus.*`, `tenant.profile.read`, `audit.read`. **No business permission exists.**

**New** (tenant realm; added by migration with system-role clone rows, D-B4; constants only, no literals):

| Code | Scope (D-B1) | Notes |
|---|---|---|
| `course.read` | **campus** | Courses have NULL campus, so campus-restricted staff can read the catalogue. `tenant` scope would lock them out |
| `course.manage` | tenant | Create, edit, activate, archive |
| `lead.read`, `lead.create`, `lead.update` | campus | Unassigned (NULL-campus) leads are visible to all holders: the triage pool (L6) |
| `lead.assign` | campus | Assign owner and campus |
| `application.read`, `application.create`, `application.update` | campus | |
| `application.review` | campus | Approve, reject, correction |
| `document.read`, `document.upload` | campus | |
| `document.verify` | campus | |
| `admission.approve` | campus | Explicitly permission-gated (UI-SCREENS ADM-10). **Candidate for `requires_step_up`**: decide in L7 (recommend no step-up for the MVP; revisit with Finance) |
| `student.read` | campus | `student.update` arrives with editable Student 360 (P1) |

**Roles:**
- `INSTITUTE_OWNER` and `ADMIN` automatically hold every tenant permission (template = "everything").
- Add two **system role templates** (resolves INC-06 for admissions; L7):
  - `ADMISSIONS_MANAGER`: all of the above;
  - `COUNSELLOR`: `course.read`, `lead.*` except `lead.assign`, `application.read`/`.create`/`.update`, `document.read`/`.upload`, `student.read`.
- A separate "Document verifier" is a **custom role** (T01-08 already supports it).

**List queries must apply the same campus rule as `authorize()`:** `campus_id IS NULL OR campus_id = ANY(scope)` for restricted members. One shared repository helper with a test, so lists and details can never disagree (404 for out-of-scope details, D-B1).

No role-name checks anywhere (T01-05); the UI uses `can()` / `PermissionGate` plus the requirement map, which replaces `UNRELEASED` with the new permissions.

---

## 14. Multi-Tenancy & Campus Scope

| Entity | Tenant boundary | Campus boundary | Cross-campus visibility | Platform access | Student/public realm later |
|---|---|---|---|---|---|
| Course | RLS, tenant | none (catalogue) | all staff with `course.read` | no (support sessions, Phase 02 platform track) | Public site reads **published** courses via `/api/v1/public` (Slice 4+) |
| Lead | RLS | nullable; assigned campus | NULL = institute pool; assigned = campus members only | no | Public enquiry creates a lead in the **host-resolved** tenant; body `tenant_id` rejected (tenancy.md) |
| Follow-up, Activity | RLS | inherit subject | inherit | no | no |
| Application | RLS | required at submit | campus members; all-campus managers | no | Applicant self-service needs the student/public realm (deferred, L4) |
| Document, StoredFile | RLS; object keys prefixed by tenant, never user-supplied names | inherit | inherit | no | Student uploads via the student realm (later) |
| Admission, Student | RLS | campus of admission / home campus | Student visible to campus members of any of their admissions (P1); MVP: home campus | no | Student account linked later (ADR-0005) |

Leakage guards:
- Every new route gets a cross-tenant **and** a cross-campus test (the route-coverage meta-test enforces cross-tenant cases).
- Object keys never come from the client, and downloads authorize the document first.
- Duplicate detection stays **within the tenant** (never cross-tenant matching).
- Admission numbers are unique per tenant.

---

## 15. Public Website / Lead Capture Strategy

- **The marketing website** (root files, ADR-0003) is out of scope and unchanged.
- **The Tenant Public Website** is experience 4. Its tenant must be resolved **server-side from a verified `tenant_domains` host** (ADR-0004, tenancy.md); `/api/v1/public/*` is anonymous and never takes a tenant from the body.

**Recommendation: B, a thin integration dependency, built as Slice 4 (not in the first slice).**
- **Day one:** staff enter leads manually (walk-ins and phone are a large share of MTI enquiries). The slice is fully usable without public intake.
- **Slice 4 (simplest enterprise-safe option):** a **hosted enquiry page** on a **platform-issued tenant subdomain** (for example `<tenant-slug>.<platform-domain>`).
  - It is recorded as a `tenant_domains` row that is **verified by construction**: the platform owns the domain.
  - The page calls `POST /api/v1/public/enquiries`, with Redis rate limits (IP + tenant), a honeypot field, a consent checkbox and personal-data minimisation.
  - The institute's own website links or embeds it (link or iframe).
  - No DNS verification flow, no customer TLS and no website builder are needed. This also settles INC-27 (route prefix) as part of that slice.
- **Rejected for now:**
  - a tenant website builder (GROW-04/05/06, Phase 14);
  - custom domains (needs DNS verification and TLS automation);
  - webhooks from third-party site builders;
  - a "form key" in the URL as tenant identity (a new tenant-resolution source that ADR-0004 doesn't allow);
  - direct application from public pages (needs an applicant identity: L4).

---

## 16. Communication Strategy

The first slice **does not require** email, WhatsApp, SMS, voice, notifications, templates or campaigns. Counsellors see their work in their queue and follow-ups (pull, not push).

- **Slice 4** (public enquiry) is the first place an outbound message matters: an acknowledgement email. It introduces the **transactional outbox + worker + queue library** that backend-foundation.md already plans, replacing at-most-once direct dispatch. That is the right moment to choose the queue library (D4), and not earlier.
- **WhatsApp** (PRD MVP item 15) is a V1.5 slice: provider adapter, templates, consent, delivery status (CLAUDE §48). It builds on the events emitted by Slices 1–2.
- In Slices 1–2, emit **domain events as records** (an Activity entry and an audit row, named after APP-FLOW §42), so Communication and Automation can subscribe later without changing the admissions services. Do not build an event bus yet.

---

## 17. Finance Dependency

- **Is admission possible before payment?** In the specs the admission flow is `Approved → Admission → admission number → Fee plan → Payment → Receipt → Student created → Batch` (APP-FLOW §18; PRD §29 places "Fee" before "Admission"). **Recommendation (L3):** in the MVP, admission approval creates the Admission and the Student, and **payment gates enrolment and batch allocation, not admission**. Institutes commonly admit, then collect fees. A later setting can require payment before confirming admission.
- **Is fee generation required for the first demo?** No.
- **Minimum finance (V1, Slice 5):**
  - a fee amount per course (or a simple fee structure);
  - an invoice raised on admission;
  - a **manually recorded payment** (cash, bank transfer, UPI reference) and a receipt;
  - an outstanding balance.
- **No** payment gateway, instalments, refunds, discounts, scholarships or reconciliation until later.
- Financial actions are audited and need their own permissions (`finance.*`). Step-up for refunds is a V2 decision.

---

## 18. Academics Dependency

| Entity | Needed when | Why |
|---|---|---|
| **Course (minimal)** | **Slice 1** | Applications and leads reference it. Curriculum (ACA-04) is not needed |
| Student | Slice 2 (created at admission) | Student 360 basics |
| Batch | V1 (Slice 6) | Batch allocation follows admission and payment (APP-FLOW §18, §21) |
| Faculty | With batches, but only as a reference (faculty mapping on a batch); a Faculty module later | |
| Timetable, Attendance, Training, Exams, Certificates | V2 (RUN phase, PRD §73) | Need batches and enrolled students |

TASKS.md puts courses in Phase 05, after Admissions. That order must change so a **minimal course catalogue comes first** (L1). The full Academics module stays where it is.

---

## 19. Reusable Capabilities

Build these once, but only those with at least two confirmed consumers in the next slices:

| Capability | Consumers | Notes |
|---|---|---|
| **Page templates T02 Data List, T03 Detail, T05 Wizard, T06 Kanban** | courses, leads, applications, students, documents; T05 in the application wizard and later the provisioning wizard; T06 in the pipeline and later batches | CLAUDE §25; compose existing components |
| **Server-data pattern** (server-component reads, TanStack Query, Zod, OpenAPI-generated types) | every page | Already decided in repository-structure.md |
| **List query conventions** (filters, search, sort allow-list, pagination, campus filter helper) | every list | Extends T01 pagination; one campus helper (§13) |
| **Status transition helper** (allowed-transition table, reason, activity, audit) | lead, application, document, admission; later invoice, batch | Domain-level, no workflow engine |
| **Activity timeline and notes** | lead, application, student; later finance, batch | APP-FLOW §38. **Separate from audit**: audit is compliance and security; activity is the business timeline readable with the entity's permission |
| **File storage + document capability** (validation pipeline, object storage, download authorization) | application documents, student documents; later certificates, compliance documents | ARCHITECTURE §7, §31, §49; INC-22 limits (L5) |
| **Tenant-scoped number sequence** | admission numbers; later invoice and receipt numbers, student IDs | Row-locked counter |
| Duplicate check (normalised mobile/email within the tenant) | leads; student create-or-link | Warn, don't block |

**Not now:** comments/@mentions, approval-workflow engine, notifications centre, import/export, bulk actions, global search (APP-FLOW §37 — after 3+ searchable entities exist), generic entity history beyond the activity timeline.

---

## 20. AI Timing

**B, then D:** after the first business workflow **and** the first communication channel, once operational data exists.
- The AI Admission Agent (PRD §28) answers from institute-approved knowledge (courses, eligibility, fees), qualifies leads, and creates leads through **governed tools**. It needs courses, leads, communication channels and RAG first.
- Introducing it before the admissions services exist would mean the agent calling services that are still changing, or bypassing them. Both are prohibited (CLAUDE §43).
- The admissions services built now are the future tools: keep them as service-layer commands with explicit permissions, so an agent can call them under the same authorization later.

---

## 21. Product Demo Strategy

A convincing ~10-minute demo uses one seeded institute, for example "Coastal Maritime Training Institute" with Kochi and Visakhapatnam campuses, with an owner, an admissions manager and two counsellors, all in the realistic maritime data style of CLAUDE §61.

1. The admissions manager opens **Courses**: "GP Rating (Pre-Sea)", "DNS", "STCW Basic Safety (Post-Sea)".
2. A walk-in enquiry: the counsellor creates a lead and the **duplicate warning** fires on a known mobile number. The lead is assigned to the Kochi campus.
3. **Pipeline (Kanban)**: drag to CONTACTED and then QUALIFIED. The activity timeline records each move and a follow-up is scheduled.
4. **Convert to applicant**: the wizard runs from personal details to education, course and campus, then the declaration; save as draft, resume, submit.
5. Upload the **CDC, passport and medical certificate**. The verifier rejects one ("Medical certificate expired"), it is re-uploaded, then verified.
6. **Review**: approve, then **Admission approval** (manager only; the counsellor doesn't see the button and the API refuses). An admission number is generated.
7. **Student 360**: profile, admission, course, documents and the full timeline from first enquiry to admission.
8. Sign in as a Visakhapatnam-only counsellor: Kochi records are invisible (campus scope). Optionally, a second institute shows full isolation.

What the demo deliberately does **not** show: empty module menus (they stay `UNRELEASED`), dashboards with fake numbers, AI.

---

## 22. Recommended Implementation Sequence

| Slice | Objective | Depends on | Backend | Frontend | Database | Integrations | Tests | Complete when |
|---|---|---|---|---|---|---|---|---|
| **02-1 Courses + Leads** (MVP) | A counsellor manages enquiries against a real course catalogue | T01; L1, L2, L6, L7 locked | `courses`, `leads` modules (router → service → domain → repository); transition helper; activity; follow-ups; duplicate check; campus list helper; permissions + role templates | T02/T03/T06 templates; server-data pattern (TanStack Query, Zod, OpenAPI types); ACA-01/02/03, GROW-08/09, ADM-02; requirement map entries | migration 0009: courses, leads, follow-ups, activities, permissions + role clones; RLS, grants, composite FKs | none | unit (transitions, duplicates), API, cross-tenant and cross-campus per route, permission sync, UI states, axe Light/Dark, responsive | A seeded counsellor can run a lead from NEW to QUALIFIED with follow-ups. Restricted members see only their campus. All gates green |
| **02-2 Applications → Admission → Student** (MVP) | Complete admissions to an admitted student | 02-1; L3, L4, L5 locked | `applications`, `documents`, `students` modules; storage capability (S3 client); validation pipeline; review/admit commands; number sequence; create-or-link student | T05 wizard; ADM-05/06/07/08/09/10/11/12/13/14 | migration 0010: applications, documents, stored files, admissions, students, counters | object storage (SeaweedFS locally, S3 in production) | upload security (type/MIME/size/name, deny list), download authorization, cross-tenant on files, admit idempotency, audit | The §21 demo runs end to end on seed data |
| **02-C Onboarding enablers** (parallel track) | A real institute can be provisioned and staffed without API calls | T01 APIs | none (APIs exist) | ADMIN-05/06/07 (members, roles); PLAT-04/05/06 minimal (list, summary, create with owner invite; step-up per D6-5 / D7-4) | none | email (exists) | UI, permission states, step-up reuse | Platform admin provisions an institute; the owner invites counsellors and assigns roles and campuses |
| 02-3 Seed + demo hardening | Repeatable demo | 02-1, 02-2 | seed extension | — | — | — | seed tests | One command seeds the §21 demo |
| 02-4 Public enquiry (V1) | Website enquiries become leads | 02-1; L-public | `tenant_domains` (platform-issued subdomain); `/api/v1/public/enquiries`; rate limits; consent; **outbox + worker + queue library** (ack email) | hosted enquiry page (T18) | migration: tenant_domains, outbox | email via outbox | host spoofing, unknown host 404, abuse limits, cross-tenant | An enquiry on the hosted page appears as a NEW lead in the right tenant only |
| 02-5 Finance-lite (V1) | Fee, invoice, manual payment, receipt | 02-2 | `finance` module (fee per course, invoice on admission, payments, receipts, outstanding) | FIN-02/04/06 minimal, Student 360 Fees | finance tables | none | money arithmetic (decimal), audit, permissions | An admitted student has an invoice, a manual payment and a receipt |
| 02-6 Batches (V1) | Allocate admitted students | 02-2 (02-5 gate configurable) | `batches` module (capacity, dates, campus), allocation → ENROLLED | ACA-05/06/07; Student 360 Batch | batch tables | none | capacity races, campus scope | A student is allocated to a batch and becomes ENROLLED |
| 02-7 Communication (V1.5) | WhatsApp/email on admissions events | 02-4 outbox | provider adapters, templates, consent, delivery status | ADM-15, templates | messages, templates | WhatsApp provider | provider fakes, consent | Lead created and admission approved send approved templates |
| 02-8 Admissions dashboard (V1.5) | Operational KPIs | 02-1, 02-2 | aggregates | ADM-01 | — | — | — | Real counts, drill-downs |

---

## 23. Parallel vs Sequential Work

- **Sequential:** 02-1 → 02-2 (applications need leads, courses and the shared templates/helpers) → 02-5 → 02-6.
- **Parallel with 02-1/02-2:** 02-C onboarding enablers (UI only, existing APIs). Within 02-1, the backend modules and the frontend templates can proceed in parallel once the API schema is drafted (OpenAPI types).
- **Parallel after 02-1:** 02-4 public enquiry (needs leads only).
- **Deferred:** everything in §24.
- **Reuse, not rebuild:** auth, authorization, tenancy, audit, pagination, proxy, session provider, design system.
- **Would cause rework if built now:**
  - a generic workflow engine;
  - an event bus;
  - a notifications centre;
  - dashboards before data exists;
  - a separate Applicant entity;
  - finance before admission exists;
  - the website builder.

---

## 24. What NOT To Build Yet (top 10)

1. AI Admission Agent / RAG / agent runtime.
2. Workflow builder and automation engine (PRD §47).
3. WhatsApp, SMS and voice integrations.
4. Tenant website builder, custom domains and SEO pages (GROW-04/05/06, Phase 14).
5. Campaigns, content and social agents (GROW-01/02/03/11/12).
6. Full Finance (instalments, gateway, refunds, discounts, reconciliation).
7. Timetable, attendance, training, exams, certificates, placement, compliance.
8. Student Portal and applicant self-service accounts.
9. Platform billing, plans, subscriptions, usage metering, platform analytics and health dashboards (the rest of TASKS Phase 02).
10. Global search, notifications centre, import/export, bulk actions, lead scoring.

---

## 25. Claude Code Development Strategy

**Per slice:**
1. One short readiness check, only if a slice has an unlocked decision.
2. One implementation branch.
3. Implementation as one coherent slice: backend, migrations, API, UI, tests.
4. All gates (backend with PostgreSQL in CI; frontend; secrets and audit).
5. One PR, merged with a merge commit.
6. Next slice.

- **Lock only** the decisions in §28. Everything else (field lists, column types, component composition, copy) is an implementation detail Claude chooses within the specs and records in the slice's ADR or status entry. No separate decision branch.
- **Slice size:** 02-1 and 02-2 are each one PR. If 02-2 gets too large, split it at "documents and storage" vs "review, admission, student", not by layer.
- **Per slice, Claude must:** add cross-tenant and cross-campus tests for every new route; add permissions only by migration with role clones; replace `UNRELEASED` with the real permission in the requirement map; extend the seed; and update TASKS.md and DEVELOPMENT-STATUS.md honestly (D18 browser journeys are listed as run or not run).
- **Avoid:** splitting UI and backend into separate PRs; building screens without APIs; touching the marketing site; adding dependencies without the CLAUDE §74 check. Expected new dependencies are the S3 client, TanStack Query, Zod and an OpenAPI type generator; each needs that check.

---

## 26. Phase 02 Definition of Done (MVP = 02-1 + 02-2 + 02-C)

- [ ] The §21 demo runs end to end on seed data, in Light and Dark, at 390/768/1024/1440.
- [ ] A real institute can be provisioned, staffed (roles, campuses) and operated without API calls.
- [ ] Every new route: authorization by permission, tenant isolation (RLS + cross-tenant test), campus scope (cross-campus test), validation, audit for decisions, optimistic locking.
- [ ] Uploads: server-side validation pipeline, private object storage, authorized short-lived downloads, no client-supplied keys.
- [ ] No role-name gating; `UNRELEASED` replaced only for shipped pages.
- [ ] CI green, including PostgreSQL integration, gitleaks, CodeQL and dependency audit.
- [ ] TASKS.md re-sequenced (L1); DEVELOPMENT-STATUS.md updated; UI-SCREENS overlaps noted (§4).

---

## 27. Final Recommendation

Re-sequence TASKS.md as follows:

- **The next phase is the Admissions MVP**: Slice 02-1 (Courses + Leads), then 02-2 (Applications → Documents → Admission → Student).
- **A thin onboarding track runs in parallel**: tenant member/role screens and minimal platform provisioning screens, both on existing APIs.
- **After the MVP, in order:**
  1. public enquiry (with the outbox and worker);
  2. Finance-lite;
  3. Batches;
  4. Communication;
  5. Dashboards;
  6. AI.
- The rest of the Platform Control Plane (billing, plans, metering, health, analytics) and the RUN, COMPLY and AUTOMATE pillars follow the commercial order of PRD §72–76.

---

## 28. Decisions That Actually Need Locking

Each has a recommendation. Record the answers in TASKS.md (and an ADR for L4–L6) at the start of the implementation branch; no separate decision PR.

| ID | Decision | Recommendation | Blocks |
|---|---|---|---|
| **L1** | Sequencing | The next phase is the Admissions MVP (02-1, 02-2), with the minimal course catalogue pulled forward from Phase 05. The Platform Control Plane shrinks to the thin provisioning UI (02-C); the rest moves after the MVP. Update TASKS.md | 02-1 |
| **L2** | Person model | No separate Applicant entity. **Lead** (prospect) → **Application** (per course; holds the applicant's details as entered) → on admission, **Student** (the person, matched within the tenant by normalised identifiers and reused for later courses) + **Admission** (per application) | 02-1 (lead-to-application link), 02-2 |
| **L3** | Admission vs payment | Admission approval creates the Admission (number) and the Student. Payment gates **enrolment and batch allocation**, not admission. A setting to require payment first comes later. Deviates from the APP-FLOW §18 ordering, so it needs product sign-off | 02-2 |
| **L4** | Who submits applications | **Staff-assisted only** in the MVP. Public pages capture enquiries only. Applicant self-service waits for the student/public identity work | 02-2, 02-4 |
| **L5** | Documents and storage | Server-side upload through the API (validate before storing) to private object storage. Downloads via authorized short-lived URLs or streaming with `Content-Disposition: attachment`. INC-22 resolved: PDF, JPEG and PNG, **10 MB** per file (proposed). **Malware scanning deferred** with compensating controls (type/MIME sniffing, deny list, no inline rendering), as an explicit, recorded risk acceptance | 02-2 |
| **L6** | Campus semantics for admissions data | Courses: tenant-wide (NULL campus, `course.read` campus-scoped). Leads: campus nullable (NULL = institute triage pool visible to all `lead.read` holders), assigned on qualification. Applications, Admissions and Students: campus required. Lists use one helper mirroring `authorize()` | 02-1 |
| **L7** | Role templates and admission control | Add `ADMISSIONS_MANAGER` and `COUNSELLOR` system templates (closes INC-06 for admissions); verifier as a custom role. `admission.approve` without step-up in the MVP | 02-1 |
| *(later)* L8 | Public enquiry tenant resolution | Platform-issued subdomain as a verified `tenant_domains` row; settles INC-27 | 02-4 only |
| *(later)* L9 | Queue library for the outbox/worker | Chosen in 02-4 (D4) | 02-4 only |

---

## IF WE START DEVELOPMENT TOMORROW, WHAT EXACTLY SHOULD WE BUILD FIRST?

**FIRST BUILD:**
Slice 02-1, **Courses + Lead Management**, as the first half of the Admissions MVP. Slice 02-2 (Application → Documents → Admission → Student) follows immediately in the next PR.

**WHY:**
It is the GROW + ADMIT core every specification names as the commercial MVP (PRD §72, APP-FLOW §43, TASKS Phase 04). Courses are a hard dependency of applications. Leads are the daily work of an admissions office. It reuses all of T01 and needs no new infrastructure. It establishes the shared templates and helpers every later module reuses.

**FIRST USERS:**
Admissions manager, counsellor (and the institute owner/admin who sets up the team).

**FIRST END-TO-END FLOW:**
Manager creates courses → counsellor enters an enquiry (duplicate warning) → lead assigned to a campus and counsellor → status moves through the pipeline with recorded transitions → follow-ups and notes → lead qualified (ready to convert in 02-2).

**FIRST SCREENS:**
ACA-01 Courses, ACA-03 Create Course, ACA-02 Course Detail, GROW-08 Lead List, GROW-09 Lead Detail (Lead 360), ADM-02 Lead Pipeline. Plus the shared T02/T03/T06 templates.

**FIRST APIs:**
`GET/POST /courses`, `GET/PATCH /courses/{id}`, `GET/POST /leads`, `GET/PATCH /leads/{id}`, `POST /leads/{id}/transition`, `POST /leads/{id}/assign`, `GET/POST /leads/{id}/follow-ups`, `PATCH /follow-ups/{id}`, `GET/POST /leads/{id}/activity`.

**FIRST ENTITIES:**
Course, Lead, Follow-up, Activity (shared timeline); permissions `course.*`, `lead.*`; role templates `ADMISSIONS_MANAGER` and `COUNSELLOR`.

**DO NOT BUILD YET:**
AI, workflow builder, WhatsApp/SMS/voice, website builder and custom domains, campaigns and content, full finance, timetable/attendance/exams/certificates/placement/compliance, Student Portal and applicant self-service, platform billing/metering/analytics, global search, notifications centre, import/export, lead scoring.

**NEXT AFTER THAT:**
02-2 Applications → Documents → Verification → Admission → Student (with the storage capability), with the onboarding enablers (02-C) in parallel. Then the public enquiry page, Finance-lite and Batches.
