# Specification Inconsistencies

- **Status:** Open register (created in T00-01, 2026-09-26)
- **Rule:** inconsistencies are **recorded here, not silently resolved** (CLAUDE.md §2, §88). Each entry is closed only by an explicit documentation task or ADR, and the closing change is noted in the entry.

| Status legend | Meaning |
|---|---|
| `OPEN` | Not resolved; specifications disagree |
| `DECIDED-BY-ADR` | An ADR sets the engineering direction; the older specification text still needs a documentation update |
| `CLOSED` | Specifications updated and consistent |

---

## INC-01 — Screen count

- **Status:** `OPEN`
- **Where:** UI-SCREENS.md §29, DEVELOPMENT-STATUS.md §27, TASKS.md §2, CLAUDE.md §24, PRD.md §96
- **Issue:** Documents state **~222** screens (Platform 53, Tenant ~153, Student 10, Public 6). UI-SCREENS.md actually contains **205** headed screen entries (Platform 53, Tenant 136, Student 10, Public 6).
- **Impact:** Planning and progress metrics.
- **Proposed resolution:** Either add the missing tenant screen specifications or correct the stated totals.

## INC-02 — Superseded phase list in ARCHITECTURE.md

- **Status:** `OPEN` (annotated in T00-01)
- **Where:** ARCHITECTURE.md §60 vs TASKS.md §4, PRD.md §77, CLAUDE.md §81, DEVELOPMENT-STATUS.md §7
- **Issue:** ARCHITECTURE.md §60 lists 13 older phases (Phase 01 Foundation, 03 CRM, 05 Communication, 06 AI Admission, 07 Finance, 08 Academics, …). The other documents use Phases 00–17 in a different order.
- **Current handling:** ARCHITECTURE.md §60 carries a note that TASKS.md is authoritative. The old list is retained.
- **Proposed resolution:** Replace §60's list with a pointer to TASKS.md.

## INC-03 — "Public Website" meaning

- **Status:** `DECIDED-BY-ADR` ([ADR-0003](../adr/0003-marketing-vs-tenant-public-website.md)); specification text still inconsistent
- **Where:** PRD.md §10.4, §60; CLAUDE.md §4.4; UI-SCREENS.md PUB-01…06; TASKS.md Phase 14 (objective and T14-03/T14-05/T14-06); DEVELOPMENT-STATUS.md §22
- **Issue:** PRD/CLAUDE and PUB-01 ("Courses", "Institute credibility") describe a **tenant institute** website. PUB-02 Features, PUB-04 Pricing, PUB-05 Request Demo and the Phase 14 objective ("Create the MTI 360 marketing and acquisition experience") describe **MTI 360's own** marketing site.
- **Direction:** Phase 14 / PUB-* = Tenant Public Website. MTI 360 marketing website = separate Marketing Website Track (`MKT-*`).
- **Proposed resolution:** Rewrite the PUB-* screen list and the Phase 14 objective/tasks for the tenant public website (e.g. institute home, courses, course detail, eligibility & fees, admissions/enquiry, contact) — a **product-scope decision** requiring approval.

## INC-04 — Marketing website status not recorded

- **Status:** `CLOSED` in T00-01
- **Where:** DEVELOPMENT-STATUS.md
- **Issue:** The existing root landing page was not recorded anywhere in the status tracker.
- **Resolution:** Recorded as PROTO-01 (Prototype: YES, Production Ready: NO) in DEVELOPMENT-STATUS.md §47.

## INC-05 — API path conventions

- **Status:** `DECIDED-BY-ADR` ([ADR-0006](../adr/0006-api-prefixes.md))
- **Where:** ARCHITECTURE.md §35 (`/api/v1/*`) vs PLATFORM-ADMIN.md §91 (`/platform/api/*`, `/api/tenant/*`)
- **Direction:** `/api/v1/platform/*`, `/api/v1/*` (tenant), `/api/v1/student/*`, `/api/v1/public/*`, `/api/v1/webhooks/*`.
- **Proposed resolution:** Update PLATFORM-ADMIN.md §91 examples.

## INC-06 — Tenant role names

- **Status:** `OPEN` — must be resolved before Phase 01 role seeding (T01-08)
- **Where:** CLAUDE.md §11 vs PRD.md §85
- **Issue:** CLAUDE.md lists Tenant Admin, Admissions Manager, Counsellor, Faculty, Finance User, Compliance User, Placement User, Communication User, AI Manager, Analyst. PRD.md lists INSTITUTE_OWNER, DIRECTOR, PRINCIPAL, ADMIN, ADMISSION_MANAGER, COUNSELLOR, ACCOUNTS, FACULTY, COMPLIANCE, PLACEMENT, MARKETING, **STUDENT**. PRD includes STUDENT as a tenant role although the Student Portal is a separate experience and realm (ADR-0005).
- **Proposed resolution:** Agree one canonical system-role template list; model students as a separate realm rather than a staff role.

## INC-07 — Subscription plan names

- **Status:** `OPEN`
- **Where:** PRD.md §71 (Starter / Growth / Professional / Enterprise) vs PLATFORM-ADMIN.md §40 (Starter / Professional / Business / Enterprise)
- **Proposed resolution:** Commercial decision; plans are data, so this blocks seeding only, not architecture.

## INC-08 — Identity model and session mechanism

- **Status:** `DECIDED-BY-ADR` ([ADR-0005](../adr/0005-identity-and-session-realms.md))
- **Where:** ARCHITECTURE.md §10 ("Session / JWT"), §32 (`users`, `tenant_users`); PLATFORM-ADMIN.md §15 (separate platform login)
- **Issue:** Whether platform administrators share the `users` table, and whether sessions or JWTs are used, was unspecified.
- **Direction:** Separate `platform_users`; opaque server-side sessions. ARCHITECTURE.md §10 carries a T00-01 note.
- **Proposed resolution:** Update ARCHITECTURE.md §32 identity table list when Phase 01 models are designed.

## INC-09 — Status vocabularies

- **Status:** `OPEN`
- **Where:** CLAUDE.md §83 (Specification Ready, Design Ready, Prototype, Implemented, Tested, Verified, Production Ready) vs TASKS.md §5 / DEVELOPMENT-STATUS.md §4 (NOT_STARTED, IN_PROGRESS, BLOCKED, READY_FOR_REVIEW, COMPLETED, DEFERRED)
- **Proposed resolution:** Define how the two vocabularies map (task status vs maturity level), or adopt one.

## INC-10 — T00-01 Definition of Done

- **Status:** `CLOSED` in T00-01
- **Where:** TASKS.md T00-01
- **Issue:** "Repository builds successfully" cannot apply before any buildable project exists.
- **Resolution:** TASKS.md T00-01 amended: criterion not applicable; transfers to T00-02.

## INC-11 — Document priority order

- **Status:** `OPEN`
- **Where:** CLAUDE.md §2 vs MASTER-CLAUDE-DESIGN-PROMPT.md §2
- **Issue:** CLAUDE.md is the engineering constitution with security as highest priority. MASTER-CLAUDE-DESIGN-PROMPT.md lists CLAUDE.md **last** in its interpretation order.
- **Proposed resolution:** Clarify that the design prompt's order applies to design interpretation only, and that security and engineering rules in CLAUDE.md always prevail.

## INC-12 — Typography

- **Status:** `OPEN` (affects the marketing website only)
- **Where:** DESIGN-SYSTEM.md §17 (Inter preferred, Plus Jakarta Sans alternative) vs the marketing website (Plus Jakarta Sans + JetBrains Mono)
- **Issue:** JetBrains Mono is not in the design system. The application must follow DESIGN-SYSTEM.md; the marketing site is not changed by T00-01.
- **Proposed resolution:** Decide whether a monospace family is added to the design system (e.g. for identifiers and code) during T00-06.

## INC-13 — Responsive verification widths

- **Status:** `OPEN` (minor)
- **Where:** DESIGN-SYSTEM.md §21 (four tiers: 390–767, 768–1023, 1024–1439, 1440+) vs TASKS.md T00-09 (verify 390, 640, 768, 1024, 1280, 1440+)
- **Issue:** Compatible (TASKS adds intermediate widths) but not stated explicitly.
- **Proposed resolution:** State in DESIGN-SYSTEM.md that 640 and 1280 are intermediate verification widths, not breakpoints.

## INC-14 — "ACRS" reference

- **Status:** `OPEN`
- **Where:** ARCHITECTURE.md §73
- **Issue:** "ACRS" is named as another product reusing the agent platform but is undefined in every other document.
- **Proposed resolution:** Define it or remove the reference; does not affect MTI 360 implementation.

## INC-15 — "Billing" overloaded

- **Status:** `DECIDED-BY-ADR` (naming in [repository-structure.md](repository-structure.md#3-backend-architecture))
- **Where:** PLATFORM-ADMIN.md (PLAT-13 Billing & Invoices), UI-SCREENS.md ADMIN-11 Billing, FIN-* screens, PRD.md §38 Finance
- **Issue:** "Billing" refers both to MTI 360 billing its tenants (SaaS billing) and to institutes charging students (fees).
- **Direction:** Backend module `billing` = SaaS billing; module `finance` = student fees.
- **Proposed resolution:** Use "Subscription billing" and "Student fees / Finance" consistently in screen names.

## INC-16 — README listed as a source document but empty

- **Status:** `CLOSED` in T00-01
- **Where:** README.md (previously a 3-byte UTF-8 BOM)
- **Resolution:** README.md rewritten in T00-01.
