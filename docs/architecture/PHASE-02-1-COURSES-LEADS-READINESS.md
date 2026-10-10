# Phase 02-1 Courses + Lead Management Readiness

- **Status:** Implementation blueprint (2026-10-08) on `main` at `9009db5`. Documentation only: no code, migration, manifest or runtime change.
- **Builds on:** [PHASE-02-MASTER-READINESS.md](PHASE-02-MASTER-READINESS.md) (approved decisions L1–L7), ADR-0004, ADR-0011, ADR-0013, ADR-0014, ADR-0016, ADR-0019, [authorization.md](authorization.md), [tenancy.md](tenancy.md), [backend-foundation.md](backend-foundation.md), [repository-structure.md](repository-structure.md).
- **Verified against:** `backend/app/modules/{institute,identity,access,tenants,audit}`, `backend/app/core/{authz,audit,pagination,tenancy,db}`, migrations 0001–0008, `backend/tests/**`, `database/seeds/dev.json`, `frontend/src/{lib,shells,design-system,app}`, PRD §26–§31, APP-FLOW §3, §8–§10, §15, §20, §36, §42, UI-SCREENS §16–§18, TASKS Phase 04/05, DESIGN-SYSTEM templates.
- **Audience:** the Claude Code session that implements 02-1, and the reviewer of its PR.

---

## 1. Executive Summary

02-1 delivers **one coherent slice**:

- an institute-wide **course catalogue** (create, edit, activate, archive);
- **lead management**: manual entry with a private duplicate warning; assignment to a counsellor and campus; a server-authoritative pipeline (list and board); follow-ups; notes; and a lead activity timeline;
- for admissions managers and counsellors, on the existing T01 security model.

It adds:

| Area | What |
|---|---|
| Migration | One migration (`0009`): `courses`, `leads`, `lead_follow_ups`, `lead_activities`, six permissions, and two system role templates cloned into every tenant |
| Backend | Two modules, `courses` and `leads` |
| Frontend | Five routes, built on two new page templates (data list, detail) |

It ends at "lead ready to apply". The **APPLICATION** and **ADMITTED** lead statuses are reserved now and set only by 02-2.

**Verdict: READY FOR IMPLEMENTATION — NO BLOCKING DECISIONS.** The open points are implementation choices within approved decisions (§33). Six repository discrepancies are reported in §2. None blocks, but three must be corrected in the 02-1 PR.

---

## 2. Repository Verification

| # | Finding | Evidence | Consequence for 02-1 |
|---|---|---|---|
| V1 | **TASKS.md is not yet re-sequenced (L1).** Phase 02 is still "Platform Control Plane", and Courses are still in Phase 05 | `TASKS.md` Phase 02/04/05 | The 02-1 PR updates TASKS.md (docs commit) |
| V2 | **The master readiness report is untracked** | `git status`: `?? docs/architecture/PHASE-02-MASTER-READINESS.md` | Commit it (with this report) in the 02-1 PR's docs commit |
| V3 | **The cross-tenant route meta-test does not exist.** tenancy.md §8 specifies one, and the master report (§3, §25) said it exists. The implemented `tests/security/test_route_coverage.py` (`app/api/coverage.py`) enforces **permission or exemption coverage only**, not cross-tenant test cases | `app/api/coverage.py` docstring; `tests/security/test_route_coverage.py` | 02-1 adds explicit cross-tenant and cross-campus API tests for every new route, and introduces the meta-test registry for business modules (§27). The master report's wording is superseded here |
| V4 | **The lead status vocabulary differs across specs.** PRD §27: `NEW, CONTACTED, QUALIFIED, COUNSELLING, APPLICATION, ADMITTED` + `LOST, DEFERRED, NOT_ELIGIBLE`. APP-FLOW §10 adds `INTERESTED` and `DUPLICATE`. UI-SCREENS ADM-02 shows `New → Contacted → Counselling → Application → Review → Approved → Enrolled → Lost`, which mixes in application and enrolment stages | PRD §27, APP-FLOW §10, UI-SCREENS ADM-02 | Use APP-FLOW §10 (the functional workflow reference, APP-FLOW §45; a superset of PRD). Record a new INC entry. Application stages belong to 02-2 (§9) |
| V5 | **Leads appear twice in navigation** (GROW › Leads and ADMISSIONS › Leads), as in APP-FLOW §3. Navigation hrefs must be unique (`experience-routes.test.tsx`). **There is no "Pipeline" page** in the navigation, although ADM-02 (Lead Pipeline) exists in UI-SCREENS. The Admissions group carries a hard-coded demo badge ("12 new enquiries") | `frontend/src/shells/experiences/tenant.ts` | Canonical route `/app/admissions/leads`; GROW › Leads stays `UNRELEASED` (the marketing view of leads comes with GROW); ADM-02 is the **board view** of the Leads route; remove the demo badge |
| V6 | **The master report proposed a shared, polymorphic Activity table.** A polymorphic table cannot carry the composite tenant foreign keys that every T01 tenant table uses (`UNIQUE (tenant_id, id)` targets) | migrations 0003–0008 conventions | Refinement: a per-entity `lead_activities` table with real composite foreign keys, plus a shared **code-level** activity helper and UI timeline (§12). 02-2 adds `application_activities` the same way |

Also verified as the master report described:

- 15 tenant permissions, 2 system roles (`INSTITUTE_OWNER` = everything; `ADMIN` = everything except `role.delete`);
- `authorize()` allows a `CAMPUS`-scoped permission on a resource whose `campus_id` is NULL;
- no object-storage client and no queue (neither is needed by 02-1);
- TanStack Query, Zod and the OpenAPI type generator are not installed;
- only `AuthenticationTemplate` exists among the page templates.

---

## 3. T01 Capabilities Reused

| Capability | Status | Where | 02-1 use |
|---|---|---|---|
| Tenant context, realm guard, `RequestContext` (tenant, principal, permissions, `all_campuses`, `campus_ids`) | AVAILABLE | `app/api/realms.py`, `app/core/context.py` | Mount on the tenant `AUTHENTICATED` router |
| Campus context (scope ALL/SELECTED, `membership_campuses.removed_at`) | AVAILABLE | `identity` models, migration 0008 | Visibility and assignment eligibility |
| Authentication, sessions, CSRF | AVAILABLE | T01-04/09A | Unchanged |
| `authorize(context, permission, resource)` (D-B1; 404 outside scope) | AVAILABLE | `app/core/authz/engine.py` | Resource dataclasses for course and lead, as `CampusResource` does |
| `require_permission` route dependency plus route coverage test | AVAILABLE | `app/core/authz/dependencies.py`, `app/api/coverage.py` | Exactly one permission per route |
| Effective permissions of **another** membership | AVAILABLE | `access.service.membership_access()` | Assignee eligibility (§10) |
| Permission registry, migration-only sync (D-B4), system role templates (D-B2), drift tests | AVAILABLE | `app/modules/access`, `tests/integration/test_permission_sync.py` | Six permissions and two templates (§15–§16) |
| Tenant-scoped repository, ORM tenant filter, RLS | AVAILABLE | `app/core/tenancy` | Every new repository subclasses `TenantScopedRepository` |
| Optimistic locking (`VersionedMixin` → `StaleDataError` → 409) plus explicit `version` checks | AVAILABLE | `app/core/db/base.py`, campus service | Course, lead and follow-up mutations |
| Pagination (`limit` 1–100, `offset` ≤ 10 000), sort allow-list, typed filters, `ListEnvelope` | AVAILABLE | `app/core/pagination.py`, `app/core/schemas.py` | All lists |
| `ILIKE` search with `escape_like` | AVAILABLE | `identity/members_repository.py` | Lead and course search (move to `core` if reused twice; it is) |
| Audit: `write_audit_event` in the mutation transaction, category **`domain`** (exists, unused so far), redacted, bounded metadata | AVAILABLE | `app/core/audit` | Business audit events (§25) |
| Error envelope, request IDs, 422 field details | AVAILABLE | `app/core/errors.py` | Field codes per §17 |
| Frontend API proxy (tenant cookie only), `apiRequest`, `ApiError` | AVAILABLE | `frontend/src/lib/api` | Unchanged |
| Server-side tenant API read for pages | PARTIAL | `lib/session/server.ts` reads `/session` only | Generalise into a server-only `tenantApiRead()` helper (tenant cookie only, the same forwarding rules) |
| `TenantSessionProvider.request` (T01-05 §11 error matrix), `can()`, `PermissionGate`, requirement map | AVAILABLE | `frontend/src/lib/session`, `lib/authz` | All mutations; navigation entries for Courses and Leads |
| Design-system primitives: DataTable (sorting, `mobileLayout="cards"`), FilterBar (mobile drawer), Pagination, Search, Tabs, Drawer, Dialog/AlertDialog, Combobox, DatePicker/TimePicker, Badge, Timeline, EmptyState/ErrorState, Skeleton, Card, Input, Select, Textarea, Radio, Toast | AVAILABLE | `frontend/src/design-system/components` | Composed into templates; no new primitives |
| Page templates T02 Data List, T03 Detail, T04 Form, T06 Kanban | MISSING | only `AuthenticationTemplate` | Build T02 and T03 (plus a minimal form layout); the board is a feature view, not a template (§22) |
| Server-state library / form schema library / OpenAPI types | MISSING | repository-structure.md §2 names TanStack Query, Zod, generated types | §33 Y9–Y10 |
| Test helpers: `Harness`, `sign_in`, `send`, `data`, tenant-admin support | AVAILABLE | `backend/tests/*_support.py` | Add `courses_leads_support.py` |
| Dev seed (institutes, campuses, members; generated passwords, `.example` emails) | AVAILABLE | `backend/app/seed.py`, `database/seeds/dev.json` | Extend (§26) |

---

## 4. Course Domain

The catalogue exists so that leads can express interest and 02-2 applications can select a course (PRD §31, APP-FLOW §16, §20).

| Field | Tier | Why |
|---|---|---|
| `code` | **MUST** | Short unique identifier staff use daily (for example `GPR`, `STCW-BST`). Same format and immutability as campus codes (`^[A-Z0-9][A-Z0-9-]*$`, ≤ 32, unique per tenant, immutable after creation; INC-41 precedent) |
| `name` | **MUST** | Display name (PRD §31 "course name"), ≤ 200 |
| `category` | **MUST** | PRD §31 and APP-FLOW §20 make Pre-Sea / Post-Sea the defining maritime split; counsellors and future fee rules depend on it. Enum `PRE_SEA`, `POST_SEA`, `OTHER` (configurable categories are deferred: PRD §31 "should be configurable") |
| `status` | **MUST** | Lifecycle (§5); only `ACTIVE` courses are selectable |
| `duration_value` + `duration_unit` | SHOULD | PRD §31 and APP-FLOW §20 "duration"; counsellors quote it. Unit enum `DAYS`, `WEEKS`, `MONTHS`, `YEARS`; both null or both set |
| `eligibility_summary` | SHOULD | PRD §31 "eligibility", APP-FLOW §20; free text ≤ 2000 used by counsellors now and by the public site and AI later. Structured eligibility rules are deferred |
| `description` | SHOULD | Short text ≤ 2000 for the detail page and future public pages |
| Fees | DEFER | Finance-lite (V1) |
| Capacity | DEFER | Belongs to batches (PRD §32) |
| Syllabus, modules, assessments, certification, regulatory information | DEFER | ACA-04 Curriculum (Phase 05) |
| Campus offerings | DEFER | §6 |
| Display order, images, slug | DEFER | Public website (Slice 4+) |
| DG Shipping approval reference | DEFER | Regulatory data is not in any current screen spec |

---

## 5. Course Lifecycle

APP-FLOW §20 ends in "Publish". There is no hard delete: the runtime roles have no DELETE, the T01 convention.

```text
DRAFT ──activate──► ACTIVE ──archive──► ARCHIVED
  │                    ▲                    │
  └──────archive───────┼────reactivate──────┘
```

| Transition | Who | Rules |
|---|---|---|
| create → `DRAFT` | `course.manage` | Code unique per tenant (409 on a race) |
| `DRAFT → ACTIVE` | `course.manage` | Name and category present |
| `ACTIVE → ARCHIVED` | `course.manage` | Allowed even when referenced: history must survive |
| `ARCHIVED → ACTIVE` | `course.manage` | Reactivate |
| `DRAFT → ARCHIVED` | `course.manage` | Discard a draft without deleting it |

- **Concurrency:** every edit and transition sends `version`; a stale version → `409 CONFLICT`.
- **Audit:** `course.created`, `course.updated` (changed field names), `course.status_changed` (from, to). Category `domain`.
- **References:**
  - a lead may be **created** with, or **changed** to, an `ACTIVE` course only (`422 course_not_active`);
  - existing references to a `DRAFT` or `ARCHIVED` course are kept and shown with a status badge;
  - 02-2 applications follow the same rule.

---

## 6. Course Campus Semantics

The specifications make courses an **institute catalogue**:
- PRD §31 "course master";
- APP-FLOW §20 "Course Master";
- PRD §12 lists courses as campus-*aware*, through batches, classrooms and simulators.

The campus a student attends is chosen per application (L6: applications require a campus) and, later, per batch.

| Question | Answer |
|---|---|
| Tenant-wide or campus-specific? | **Tenant-wide** (A). No `campus_id` column |
| Who creates, edits and transitions? | `course.manage`, **tenant-scoped**: requires all-campus access (D-B1). Campus-restricted staff cannot manage the institute catalogue |
| Visible to campus users? | Yes. `course.read` is **campus-scoped**, and a course has no campus, so `authorize()` admits campus-restricted holders |
| Multiple campuses later? | Later, a `course_campus_offerings` table (or batches) can express where a course runs, without changing `courses` |
| Effect on 02-2 | An application selects a course and a campus independently. "Is this course offered at this campus?" validation comes with offerings or batches, not in 02-2 |

---

## 7. Lead Domain

Derived from PRD §26–§27, APP-FLOW §8–§10 and §15, and UI-SCREENS GROW-08/09.

| Field | Tier | Why / rule |
|---|---|---|
| `full_name` | **MUST** | PRD "name"; ≤ 200, whitespace-collapsed |
| `mobile` | **MUST** (one of mobile or email) | PRD "mobile"; ≤ 32 as entered (digits, spaces, `+`, `-`, parentheses); derived `mobile_key` (§8) |
| `email` | **MUST** (one of mobile or email) | PRD "email"; ≤ 254, syntactically valid; derived `email_normalized` (lower-case, trimmed) |
| `source` | **MUST** | PRD §26 and APP-FLOW §9 source list. Fixed enum: `WEBSITE`, `WHATSAPP`, `PHONE`, `WALK_IN`, `INSTAGRAM`, `FACEBOOK`, `YOUTUBE`, `GOOGLE`, `REFERRAL`, `EDUCATION_PORTAL`, `OTHER` (GROW-07 Lead Sources configuration is P1) |
| `interested_course_id` | **MUST** (nullable) | PRD "interested course"; `ACTIVE` courses only (§14) |
| `campus_id` | **MUST** (nullable) | L6: NULL = institute pool |
| `owner_membership_id` | **MUST** (nullable) | PRD "counsellor"; one owner (§10) |
| `status`, `status_reason`, `status_changed_at` | **MUST** | APP-FLOW §10 "every state transition must be recorded"; a reason is required for closing states |
| `duplicate_of_lead_id` | **MUST** (nullable) | Required when the status is `DUPLICATE` (APP-FLOW §10) |
| `created_by_membership_id` | **MUST** | "Created by" on the detail page; composite foreign key |
| `date_of_birth` | SHOULD | PRD lists it; Pre-Sea counselling checks age eligibility; 02-2 carries it over |
| `city` | SHOULD | PRD "location"; free text ≤ 120 |
| `highest_qualification` | SHOULD | PRD "education"; free text ≤ 200 (for example "12th PCM, 68%") |
| Next follow-up | **derived**, not stored | Computed from open follow-ups (§11), avoiding version churn on the lead |
| Notes | separate | `lead_activities` rows of kind `NOTE` (§12) |
| `campaign`, lead score, communication history, UTM, referral details, alternate phone, guardian, consent | DEFER | Campaigns, scoring and communication are later slices; consent comes with public capture (Slice 4) |
| Priority | DEFER | Not in PRD, APP-FLOW or UI-SCREENS |

---

## 8. Duplicate Detection

APP-FLOW §9 puts "Duplicate Check" after lead creation, and PRD §27 lists "duplicate detection". Real cases include repeat enquiries, shared family phones, several courses per person, and the same person arriving from several campaigns. So:

- **Warning only. No uniqueness constraint.** Creation always succeeds when the user continues.
- **Match keys:**
  - `email_normalized`: lower-cased, trimmed, exact match;
  - `mobile_key`: the **last 10 digits** of the digits-only mobile (or all digits if fewer), matching the same number with or without `+91` or `0`. A false positive only produces a warning, which is acceptable for a warning. A library-based E.164 normalisation can replace it later without a schema change.
- **Scope:**
  - **within the trusted tenant only** (RLS plus the ORM filter);
  - **only leads the caller may read**: the campus rule of §10. Matches in campuses the caller cannot see are **not disclosed in any form** (no count, no "exists elsewhere"), so the check cannot become an existence oracle;
  - closed leads are included (marked with their status); leads already marked `DUPLICATE` are excluded.
- **API:** `POST /api/v1/leads/duplicate-check` (POST, so mobile numbers and emails never appear in URLs or access logs), body `{mobile?, email?, exclude_lead_id?}`. It returns up to **5** candidates: `id`, `full_name`, `status`, course name, campus name, owner display name, `created_at`, `matched_on` (`mobile` / `email`). Permission `lead.read`.
- **On create:** the client runs the check when contact fields change. The server does **not** block. If the user continues, the lead's `CREATED` activity records `possible_duplicates: n` (a count of visible candidates, no identifiers of other people).
- **Resolution:** a manager or counsellor marks the newer lead `DUPLICATE` with `duplicate_of_lead_id` (§9). Merging is deferred.

---

## 9. Lead Lifecycle

Statuses (APP-FLOW §10; PRD §27 subset; V4):

| Status | Meaning | Set by | Kind |
|---|---|---|---|
| `NEW` | Created, not yet contacted | system on create | open |
| `CONTACTED` | First contact made | `lead.update` | open |
| `QUALIFIED` | Meets basic criteria, genuine intent | `lead.update` | open |
| `COUNSELLING` | In counselling | `lead.update` | open |
| `INTERESTED` | Wants to apply: **"ready to apply"** | `lead.update` | open |
| `APPLICATION` | An application exists | **system only, 02-2** | progressed |
| `ADMITTED` | Admitted | **system only, 02-2** | progressed |
| `NOT_ELIGIBLE` | Does not meet eligibility | `lead.update`, reason required | closed |
| `LOST` | Not proceeding | `lead.update`, reason required | closed |
| `DEFERRED` | Later intake | `lead.update`, reason required | closed |
| `DUPLICATE` | Same enquiry as another lead | `lead.update`, `duplicate_of_lead_id` required (a different, visible lead; not itself `DUPLICATE`) | closed |

**Transition rules** (one table in `leads/domain.py`, unit-tested):
- **open → any other open status** (forward or back; counsellors correct mistakes);
- **open → any closed status**: `NOT_ELIGIBLE`, `LOST` and `DEFERRED` require a reason (≤ 500); `DUPLICATE` requires the target lead (reason optional);
- **closed → any open status** ("reopen"; reason required);
- **`APPLICATION` and `ADMITTED` are never accepted from the API in 02-1** (`422 invalid_transition`). 02-2 sets them through a service method, not the transition endpoint;
- same-status "transitions" → `422 invalid_transition`.

Every transition:
- requires `version` (409 when stale);
- writes a `STATUS_CHANGED` activity (from, to, reason);
- writes a `lead.status_changed` audit event (`domain`; metadata `from`, `to`, `has_reason`, never the reason text, which may contain personal data);
- sets `status_changed_at`.

**Board:** a visualisation of open statuses with **click/keyboard "Move to…"** that calls the same endpoint. Drag-and-drop is **not** in 02-1 (§22).

---

## 10. Lead Assignment

| Rule | Decision |
|---|---|
| Owners per lead | **0 or 1** (`owner_membership_id`). Multiple owners are deferred |
| Unassigned | Allowed (website pool, walk-ins before triage) |
| Who assigns | `lead.assign`: Admissions Manager, Owner, Admin. Counsellors do **not** reassign |
| Create with owner | `owner: "me"` is allowed to any `lead.create` holder (a counsellor logging a walk-in); any other owner requires `lead.assign` |
| Eligible owner | An `ACTIVE` membership of the tenant, whose effective permissions (`membership_access()`) include `lead.update`, and whose campus scope covers the lead's campus (ALL, or SELECTED including it with `removed_at` NULL). A NULL-campus lead may be owned by any eligible member. Otherwise `422 owner_not_eligible` (same response whether the member exists or not) |
| Campus assignment | Through `POST /leads/{id}/assign` (owner and/or campus). The caller must have access to **both** the old and the new campus (a NULL campus is always accessible). Moving a lead to a campus its current owner cannot access → `422 owner_not_eligible` unless the owner changes in the same request |
| Visibility (read) | All-campus members see every lead. Restricted members see leads with `campus_id IS NULL` (institute pool, L6) **or** a campus in their scope. Detail outside scope → **404** (D-B1) |
| Edit rights | Any `lead.update` holder who can see the lead. **Ownership is a work-queue attribute, not an authorization boundary** in 02-1. T01 has no ownership-scoped permissions, and adding one would be a new authorization concept (§33 Y1) |
| Owner deactivated or removed from campus | The lead keeps the owner (history). The list shows the owner as inactive and managers reassign. No automatic reassignment |
| Assignee picker | `GET /leads/assignees?campus_id=` (`lead.assign`) returns only eligible members (membership ID, display name). It avoids granting `member.read` to managers just to assign |

---

## 11. Follow-ups

APP-FLOW §9 ("Create Follow-up Task"), §15 ("Schedule Follow-up"); PRD §27 "next follow-up", "follow-up reminders". 02-1 needs **lightweight scheduled tasks**, not a reminder engine.

- **Separate entity `lead_follow_ups`**: several can be open at once ("call Monday, visit Thursday"), each with its own completion and outcome.
- **Fields:**
  - `due_at` (timestamptz, date and time; the UI defaults the time to 10:00 local);
  - `kind`: `CALL`, `WHATSAPP`, `EMAIL`, `MEETING`, `VISIT`, `OTHER`. These are labels only; no messages are sent;
  - `note` (what to do, ≤ 1000);
  - `assignee_membership_id` (defaults to the lead owner, else the creator; eligibility as in §10);
  - `status`: `OPEN` → `DONE` (`outcome` ≤ 1000, optional) or `CANCELLED`;
  - `completed_at`, `completed_by_membership_id`, `created_by_membership_id`, `version`.
- **Overdue** is derived (`OPEN` and `due_at < now`), not stored.
- **Next follow-up** for lists is the minimum `due_at` of the lead's `OPEN` follow-ups, computed in the list query.
- **Permissions:** `lead.update` on the parent lead (campus rule), with no separate permission.
- **Activity** on schedule, complete and cancel. **No audit** (operational, not sensitive).
- **Not in 02-1:**
  - notifications or reminders (Communication slice);
  - recurrence;
  - a global task inbox: ADM-03 Counselling Queue (P1) is a filtered list; 02-1 provides the Leads `follow_up=overdue|today` filter instead.

---

## 12. Notes and Activity

| Concern | Store | Content |
|---|---|---|
| **User-visible timeline** | `lead_activities` (append-only: SELECT, INSERT only) | `CREATED`, `UPDATED` (changed **field names** only, no old or new personal values), `STATUS_CHANGED` (from, to, reason), `ASSIGNED` (owner/campus from → to as IDs, rendered as names), `FOLLOW_UP_SCHEDULED`, `FOLLOW_UP_COMPLETED`, `FOLLOW_UP_CANCELLED`, `NOTE` (body ≤ 4000) |
| **Notes** | `lead_activities` with kind `NOTE` | Immutable in 02-1 (no edit or delete): an auditable record. Personal-data erasure is a later, platform-wide concern |
| **System audit** | `audit_events`, category `domain` | Creation, status changes, assignment, profile updates (field names), course lifecycle (§25). **Never** names, mobiles, emails, note or reason text |

- Audit is for compliance and security and is readable with `audit.read`; the timeline is for the counsellor's work and readable with `lead.read`. They are deliberately separate: ADR-0013 audit is not a business activity store, and counsellors do not receive `audit.read`.
- **Shared, without a polymorphic table** (V6): a backend helper `record_activity(table, subject_id, kind, details, body)` and the frontend `ActivityFeed` view are reused by 02-2 (`application_activities`, the Student 360 timeline as a union read).

---

## 13. Lead → Application Boundary

- **02-1 does not convert.** There is no Application, no person record and no "Convert" button.
- **"Ready to apply" = `INTERESTED`** (or any open status). The lead detail page shows **"Start application — available with Applications (02-2)"** only as roadmap knowledge. Do **not** render a disabled button in 02-1.
- **What 02-2 needs from the lead, all present after 02-1:**
  - `id` (applications reference `(tenant_id, lead_id)`);
  - `full_name`, `mobile`, `email`, `date_of_birth`, `city`, `highest_qualification` (prefill);
  - `interested_course_id` (preselected course);
  - `campus_id` (preselected campus; required in the application per L6, chosen if NULL);
  - `owner_membership_id` (default application owner).
- **02-2 sets the lead to `APPLICATION`** through a lead-service method (`mark_application_started`, system transition plus activity) in the same transaction as application creation, and later to **`ADMITTED`**. These values are in the 02-1 CHECK constraint already, so 02-2 needs no lead migration.
- No redesign of Lead is needed for 02-2.

---

## 14. Course ↔ Lead Relationship

- **One interested course per lead** (`interested_course_id`, nullable). PRD §27 "interested course" is singular, and a 02-2 application is per course.
- Alternatives ("also asked about DNS") go in a note.
- A second application for another course in 02-2 references the same lead; it doesn't need multi-course interest.
- Multi-course preferences and ranking: **deferred** (no source requires them).

---

## 15. Permissions

The smallest coherent set. These are six new tenant-realm codes, declared in the modules' `permissions.py`, inserted by migration 0009 with role clones (D-B4), and never used as string literals outside `permissions.py`.

| Code | Action / resource | Scope (D-B1) | Covers |
|---|---|---|---|
| `course.read` | Read the catalogue | **campus** (courses have no campus → visible to restricted staff) | list, detail, course options in forms |
| `course.manage` | Create, edit, activate, archive | **tenant** (all-campus access required) | institute catalogue |
| `lead.read` | Read leads, follow-ups, activity; duplicate check | campus | NULL campus = pool |
| `lead.create` | Create leads (self-assign with `owner: "me"`) | campus | |
| `lead.update` | Edit profile and interested course; status transitions; follow-ups; notes | campus | |
| `lead.assign` | Assign owner and campus; assignee list | campus | |

No separate status, follow-up or note permissions: no persona needs them split, and the T01 catalogue favours coarse `resource.action` codes. They can be split later without data changes.

---

## 16. Role Matrix

| Permission | INSTITUTE_OWNER | ADMIN | **ADMISSIONS_MANAGER** (new) | **COUNSELLOR** (new) |
|---|---|---|---|---|
| `course.read` | ✓ (template "everything") | ✓ | ✓ | ✓ |
| `course.manage` | ✓ | ✓ | ✓ (effective only with ALL campus scope) | — |
| `lead.read` | ✓ | ✓ | ✓ | ✓ |
| `lead.create` | ✓ | ✓ | ✓ | ✓ |
| `lead.update` | ✓ | ✓ | ✓ | ✓ |
| `lead.assign` | ✓ | ✓ | ✓ | — |
| existing admin permissions | as today | as today | — | — |

- Template codes: `ADMISSIONS_MANAGER` ("Admissions manager"), `COUNSELLOR` ("Counsellor").
- Following authorization.md "Adding a permission", migration 0009:
  1. inserts the six `permissions` rows;
  2. inserts the two new system roles for **every existing tenant** (`is_system = true`, in the system realm inside the migration);
  3. inserts their `role_permissions`;
  4. adds the six permissions to every tenant's existing `INSTITUTE_OWNER` and `ADMIN` clones.
- New tenants receive all four via `clone_system_roles()`, which is template-driven.
- The drift test (`test_permission_sync.py`) proves code = database.
- No other roles are added and Owner/Admin are not redesigned.

---

## 17. API Contract

**Conventions:**
- tenant realm, `AUTHENTICATED` router, `require_permission` on every route, plus resource `authorize()` in services;
- CSRF on unsafe methods; `RequestModel` rejects unknown fields, so **any `tenant_id` in a body is a 422**;
- `Envelope` / `ListEnvelope`; offset pagination (D13);
- `404` for missing, other-tenant or out-of-scope resources (no distinction); `409 CONFLICT` for a stale `version`; `422 VALIDATION_ERROR` with field codes.

### Courses (module `courses`)

| Method & route | Permission | Request | Response | Notes / errors | Audit |
|---|---|---|---|---|---|
| `GET /api/v1/courses` | `course.read` | `q` (name/code, ≤ 200), `status` (multi), `category`, `limit`, `offset`, `sort` ∈ {`name`, `code`, `updated_at`} (default `name`) | `ListEnvelope[CourseOut]` | no campus filter (tenant-wide) | — |
| `POST /api/v1/courses` | `course.manage` | `{code, name, category, description?, duration_value?, duration_unit?, eligibility_summary?}` | `201 Envelope[CourseOut]` (`DRAFT`) | `409` code taken; `422` code format, duration pair | `course.created` (code) |
| `GET /api/v1/courses/{id}` | `course.read` | — | `CourseOut` | `404` | — |
| `PATCH /api/v1/courses/{id}` | `course.manage` | `{name?, category?, description?, duration_value?, duration_unit?, eligibility_summary?, version}` (code immutable) | `CourseOut` | `409` stale | `course.updated` (`changed_fields`) |
| `POST /api/v1/courses/{id}/status` | `course.manage` | `{status: ACTIVE│ARCHIVED, version}` | `CourseOut` | `422 invalid_transition` | `course.status_changed` (from, to) |

`CourseOut`: `id, code, name, category, status, description, duration_value, duration_unit, eligibility_summary, created_at, updated_at, version`.

### Leads (module `leads`)

| Method & route | Permission | Request | Response | Notes / errors | Audit / activity |
|---|---|---|---|---|---|
| `GET /api/v1/leads` | `lead.read` | `q` (name, email, mobile digits), `status` (multi), `owner` (`me` / `unassigned` / membership UUID), `campus` (UUID / `none`), `course` (UUID), `source` (multi), `follow_up` (`overdue` / `today` / `upcoming` / `none`), `created_from`, `created_to`, `limit`, `offset`, `sort` ∈ {`created_at`, `updated_at`, `full_name`, `next_follow_up_at`} (default `-created_at`) | `ListEnvelope[LeadListItem]` | campus rule applied in the query (§19) | — |
| `POST /api/v1/leads/duplicate-check` | `lead.read` | `{mobile?, email?, exclude_lead_id?}` (≥ 1 contact) | `{candidates: DuplicateCandidate[≤5]}` | visible leads only (§8) | — |
| `POST /api/v1/leads` | `lead.create` | `{full_name, mobile?, email?, source, interested_course_id?, campus_id?, owner?: "me"│UUID│null, date_of_birth?, city?, highest_qualification?}` | `201 LeadOut` (`NEW`) | `422`: `contact_required`, `course_not_active`, `campus_not_available` (outside scope or unknown: same), `owner_not_eligible`; `403` if `owner` is another member without `lead.assign` | `lead.created` (`source`, `has_course`, `has_campus`, `has_owner`); `CREATED` activity (`possible_duplicates`) |
| `GET /api/v1/leads/{id}` | `lead.read` | — | `LeadOut` | `404` | — |
| `PATCH /api/v1/leads/{id}` | `lead.update` | `{full_name?, mobile?, email?, source?, interested_course_id?, date_of_birth?, city?, highest_qualification?, version}` | `LeadOut` | campus and owner **not** here; `course_not_active` (unless unchanged) | `lead.updated` (`changed_fields`); `UPDATED` activity (field names) |
| `POST /api/v1/leads/{id}/transition` | `lead.update` | `{to_status, reason?, duplicate_of_lead_id?, version}` | `LeadOut` | `422`: `invalid_transition`, `reason_required`, `duplicate_target_invalid` (same response if not visible) | `lead.status_changed`; `STATUS_CHANGED` activity |
| `POST /api/v1/leads/{id}/assign` | `lead.assign` | `{owner_membership_id: UUID│null, campus_id: UUID│null, version}` (both always sent; the full assignment) | `LeadOut` | `422`: `owner_not_eligible`, `campus_not_available` | `lead.assigned` (`owner_changed`, `campus_changed`); `ASSIGNED` activity |
| `GET /api/v1/leads/assignees` | `lead.assign` | `campus_id?` (`none` = pool) | `{items: [{membership_id, display_name}]}` | eligible members only (§10), name-sorted, ≤ 200 | — |
| `GET /api/v1/leads/{id}/follow-ups` | `lead.read` | `status?` | `{items: FollowUpOut[]}` (`due_at` asc) | parent lead authorized first | — |
| `POST /api/v1/leads/{id}/follow-ups` | `lead.update` | `{due_at, kind, note?, assignee_membership_id?}` | `201 FollowUpOut` | `due_at` within −1 day…+1 year; assignee eligibility | `FOLLOW_UP_SCHEDULED` |
| `PATCH /api/v1/lead-follow-ups/{id}` | `lead.update` | `{due_at?, kind?, note?, assignee_membership_id?, version}` (`OPEN` only) | `FollowUpOut` | `422 follow_up_closed`; `404` via parent lead | `FOLLOW_UP_SCHEDULED` (rescheduled) |
| `POST /api/v1/lead-follow-ups/{id}/complete` | `lead.update` | `{outcome?, version}` | `FollowUpOut` | `422 follow_up_closed` | `FOLLOW_UP_COMPLETED` |
| `POST /api/v1/lead-follow-ups/{id}/cancel` | `lead.update` | `{version}` | `FollowUpOut` | | `FOLLOW_UP_CANCELLED` |
| `GET /api/v1/leads/{id}/activity` | `lead.read` | `limit`, `offset` (newest first) | `ListEnvelope[ActivityOut]` | actor display names resolved server-side | — |
| `POST /api/v1/leads/{id}/notes` | `lead.update` | `{body}` (1–4000) | `201 ActivityOut` | | `NOTE` activity |

- `LeadOut`: `id, full_name, mobile, email, date_of_birth, city, highest_qualification, source, status, status_reason, status_changed_at, interested_course {id, code, name, status}│null, campus {id, code, name}│null, owner {membership_id, display_name, active}│null, duplicate_of {id, full_name}│null` (null when not visible), plus `next_follow_up_at, overdue_follow_ups, created_by {display_name}, created_at, updated_at, version`.
- `LeadListItem`: `id, full_name, mobile, email, status, source, interested_course {code, name}│null, campus {code}│null, owner {display_name}│null, next_follow_up_at, overdue_follow_ups, created_at, version`.
- **No generic APIs.** The board reuses `GET /leads?status=…`. No platform route is added; platform sessions cannot reach tenant routes (realm guard).

---

## 18. Database Model

One migration, **`0009_courses_leads`** (revises `0008`).
- Conventions: frozen value lists (never import app enums), deterministic names (`NAMING_CONVENTION`), `ON DELETE RESTRICT`, composite foreign keys `(tenant_id, x_id) → parent(tenant_id, id)`, `UNIQUE (tenant_id, id)` on every table, timestamps from the database, UUIDv7 application IDs.
- It also carries the permissions, roles and clones (§16).
- The downgrade drops the tables and removes the permissions, role clones and role assignments it added. **Membership assignments to the new roles block the downgrade unless removed**: the downgrade deletes `membership_roles` for the new roles first, as a documented data-losing development operation, the same posture as 0008's downgrade.

### `courses`
| Column | Type | Rules |
|---|---|---|
| `id` | uuid PK | |
| `tenant_id` | uuid NOT NULL → `tenants(id)` | RLS key |
| `code` | varchar(32) NOT NULL | CHECK `^[A-Z0-9][A-Z0-9-]*$`; `UNIQUE (tenant_id, code)` |
| `name` | varchar(200) NOT NULL | |
| `category` | varchar(16) NOT NULL | CHECK in (`PRE_SEA`, `POST_SEA`, `OTHER`) |
| `status` | varchar(16) NOT NULL DEFAULT `'DRAFT'` | CHECK in (`DRAFT`, `ACTIVE`, `ARCHIVED`) |
| `description`, `eligibility_summary` | text NULL | CHECK `char_length ≤ 2000` |
| `duration_value` | integer NULL | CHECK `> 0 AND ≤ 1000` |
| `duration_unit` | varchar(8) NULL | CHECK in (`DAYS`, `WEEKS`, `MONTHS`, `YEARS`); CHECK both null or both set |
| `created_at`, `updated_at`, `version` | | mixins |

Constraints and indexes: `UNIQUE (tenant_id, id)`; index `(tenant_id, status, name)`.

### `leads`
| Column | Type | Rules |
|---|---|---|
| `id`, `tenant_id` | | as above |
| `full_name` | varchar(200) NOT NULL | |
| `mobile` | varchar(32) NULL | |
| `mobile_key` | varchar(16) NULL | service-maintained (§8) |
| `email` | varchar(254) NULL | |
| `email_normalized` | varchar(254) NULL | service-maintained |
| — | CHECK `mobile IS NOT NULL OR email IS NOT NULL` | |
| `date_of_birth` | date NULL | |
| `city` | varchar(120) NULL | |
| `highest_qualification` | varchar(200) NULL | |
| `source` | varchar(24) NOT NULL | CHECK in (§7 list) |
| `interested_course_id` | uuid NULL | FK `(tenant_id, interested_course_id)` → `courses(tenant_id, id)` |
| `campus_id` | uuid NULL | FK `(tenant_id, campus_id)` → `campuses(tenant_id, id)` |
| `owner_membership_id` | uuid NULL | FK `(tenant_id, owner_membership_id)` → `tenant_memberships(tenant_id, id)` |
| `status` | varchar(16) NOT NULL DEFAULT `'NEW'` | CHECK in the 11 statuses of §9 |
| `status_reason` | varchar(500) NULL | CHECK reason NOT NULL when status ∈ {`NOT_ELIGIBLE`, `LOST`, `DEFERRED`} |
| `status_changed_at` | timestamptz NOT NULL DEFAULT now() | |
| `duplicate_of_lead_id` | uuid NULL | FK `(tenant_id, duplicate_of_lead_id)` → `leads(tenant_id, id)`; CHECK `<> id`; CHECK (`status = 'DUPLICATE'`) = (`duplicate_of_lead_id IS NOT NULL`) |
| `created_by_membership_id` | uuid NOT NULL | FK → `tenant_memberships(tenant_id, id)` |
| timestamps, `version` | | |

Indexes:
- `UNIQUE (tenant_id, id)`;
- `(tenant_id, status, created_at DESC)`;
- `(tenant_id, owner_membership_id, status)`;
- `(tenant_id, campus_id, status)`;
- partial `(tenant_id, mobile_key) WHERE mobile_key IS NOT NULL`;
- partial `(tenant_id, email_normalized) WHERE email_normalized IS NOT NULL`;
- `(tenant_id, interested_course_id)`.

No uniqueness on contacts (§8). Name search: `ILIKE` within the tenant. A `pg_trgm` index is deferred until volumes require it.

### `lead_follow_ups`
| Column | Type | Rules |
|---|---|---|
| `id`, `tenant_id` | | |
| `lead_id` | uuid NOT NULL | FK `(tenant_id, lead_id)` → `leads` |
| `assignee_membership_id` | uuid NOT NULL | FK → `tenant_memberships` |
| `due_at` | timestamptz NOT NULL | |
| `kind` | varchar(16) NOT NULL | CHECK (§11) |
| `note`, `outcome` | varchar(1000) NULL | |
| `status` | varchar(16) NOT NULL DEFAULT `'OPEN'` | CHECK in (`OPEN`, `DONE`, `CANCELLED`) |
| `completed_at` | timestamptz NULL | CHECK (`status <> 'OPEN'`) = (`completed_at IS NOT NULL`) |
| `completed_by_membership_id` | uuid NULL | FK → `tenant_memberships` |
| `created_by_membership_id` | uuid NOT NULL | FK → `tenant_memberships` |
| timestamps, `version` | | |

Indexes: `UNIQUE (tenant_id, id)`; `(tenant_id, lead_id, status, due_at)`; `(tenant_id, assignee_membership_id, status, due_at)`.

### `lead_activities` (append-only)
| Column | Type | Rules |
|---|---|---|
| `id`, `tenant_id` | | |
| `lead_id` | uuid NOT NULL | FK `(tenant_id, lead_id)` → `leads` |
| `kind` | varchar(32) NOT NULL | CHECK (§12 list) |
| `actor_membership_id` | uuid NULL | FK → `tenant_memberships`; NULL = system (02-2 transitions) |
| `details` | jsonb NOT NULL DEFAULT `'{}'` | code-chosen keys: statuses, IDs, field names, counts |
| `body` | text NULL | CHECK `char_length ≤ 4000`; NOTE only |
| `created_at` | timestamptz NOT NULL DEFAULT now() | no `updated_at` or `version` |

Index: `(tenant_id, lead_id, created_at DESC)`.

**Grants:**
- `courses`, `leads`, `lead_follow_ups`: `mti_app` SELECT, INSERT, UPDATE (**no DELETE**);
- `lead_activities`: `mti_app` SELECT, INSERT only;
- `mti_readonly`: SELECT on `courses` only. **No grant on lead tables** (personal data). The future analytics/SQL agent adds reviewed access then.

---

## 19. RLS / Tenant Isolation

Every new table follows the **realm-agnostic tenant pattern** of `campuses` (migration 0003), with `TRUSTED_TENANT = nullif(current_setting('app.tenant_id', true), '')::uuid`:

| Table | SELECT | INSERT | UPDATE | DELETE |
|---|---|---|---|---|
| `courses` | `tenant_id = TRUSTED_TENANT` (app); readonly: same | `WITH CHECK tenant_id = TRUSTED_TENANT` | `USING` + `WITH CHECK` same | no privilege |
| `leads` | same (app only) | same | same | no privilege |
| `lead_follow_ups` | same | same | same | no privilege |
| `lead_activities` | same | same | **no privilege** | no privilege |

Without a tenant context nothing matches (system context is used only by the migration for role clones). **Campus scope is not in RLS.** It is application-enforced by `authorize()` per resource and by one shared list predicate (D-B1, as for campuses):

```text
restricted member:  campus_id IS NULL OR campus_id = ANY(:campus_ids)
all-campus member:  no campus predicate
follow-ups / activity: authorized through the parent lead
```

This predicate lives in **one helper** (`core/tenancy` or `core/authz`: `campus_visibility(column, context)`), used by every list, the duplicate check and the assignee query, with unit tests that it matches `authorize()`.

**Mental checks:**

| Check | Holds because |
|---|---|
| Tenant A cannot see Tenant B leads or courses | RLS `tenant_id = trusted tenant` + ORM filter + composite foreign keys; `GET /leads/{B-id}` → 404 |
| Campus A cannot modify Campus B resources | `lead.update` is campus-scoped → `authorize()` → 404; assignment checks both old and new campus |
| An institute-wide lead stays visible per L6 | NULL campus passes the predicate and `authorize()` for every `lead.read` holder |
| A platform user gains no tenant access | The realm guard rejects platform sessions on tenant routes; no support session exists yet (INC-38) |
| A body cannot set the tenant | Unknown-field rejection; the tenant comes only from the session |
| A cross-tenant link is impossible | Composite foreign keys reject course, campus, membership or lead IDs of another tenant at the database |

---

## 20. Frontend Routes

Navigation-derived (`/app/<group>/<page>`; slugs from `tenant.ts`) plus explicit nested route files, the pattern of `/app/account/security`. Every page uses `requireReadyTenantSession` and a requirement check.

| Route | Screen | Requirement |
|---|---|---|
| `/app/academics/courses` | ACA-01 Courses (list) | `course.read` (nav item gains it) |
| `/app/academics/courses/new` | ACA-03 Create Course | `course.manage` |
| `/app/academics/courses/[courseId]` | ACA-02 Course Detail | `course.read` |
| `/app/academics/courses/[courseId]/edit` | ACA-03 (edit mode) | `course.manage` |
| `/app/admissions/leads` | GROW-08 Lead List (`?view=list`, default) **and** ADM-02 Lead Pipeline (`?view=board`) | `lead.read` (nav item gains it) |
| `/app/admissions/leads/new` | Lead create (GROW-08 primary action) | `lead.create` |
| `/app/admissions/leads/[leadId]` | GROW-09 Lead Detail (Lead 360) | `lead.read` |
| `/app/admissions/leads/[leadId]/edit` | Lead edit | `lead.update` |

- **Create and edit** use **dedicated pages** (a shared form component per entity): they are long forms with a duplicate check, they work on mobile, and Back/bookmark behave predictably.
- **Status change, assignment, follow-up and note** use **Dialogs** on the detail page (and the board's "Move to…").
- GROW › Leads, Admissions › Counselling, Applications, Documents and Students stay `UNRELEASED`. The Admissions demo badge is removed (V5).
- Detail and edit routes are not navigation items; breadcrumbs come from the parent list.

---

## 21. Screen Contracts

Common to all screens:
- shell, page header and breadcrumbs;
- Light/Dark/System and the 390/768/1024/1440 tiers;
- server-rendered reads, then the client provider for mutations, then `router.refresh()`;
- toast on success;
- `ErrorState` with reference on a failed load;
- AUTHZ-01 at the same URL when the requirement is unmet, RESOURCE-02 for 404;
- one h1; labelled fields; focus to the first invalid field; no server message text displayed;
- personal data never in titles, URLs or logs.

| ID / route | Persona | Data | Actions (permission) | Loading / empty / error | Validation & feedback | Responsive & a11y |
|---|---|---|---|---|---|---|
| **ACA-01** `/courses` | Manager, counsellor | Code, name, category, status badge, duration; search, status and category filters; pagination | "New course" (`course.manage`, PermissionGate) | Table skeleton. Empty: "No courses yet". Managers see "Create your first course"; others see "Courses appear here once your institute adds them". Filtered-empty variant | — | Desktop table; mobile `cards`; filters in the FilterBar drawer |
| **ACA-03** `/courses/new`, `/[id]/edit` | Manager | Form: code (create only), name, category (Radio/Select), duration (number + unit), eligibility, description | Save (`course.manage`) | Submit pending | Client: required, formats, the duration pair. Server 409 "code already used" on the code field; 409 stale on edit → "changed by someone else, reload" | Single column on mobile, two columns from tablet (DESIGN-SYSTEM §28) |
| **ACA-02** `/courses/[id]` | All | Header (name, code, status badge); details; "Leads interested" count (P1, optional) | Edit, Activate, Archive, Reactivate (`course.manage`; AlertDialog for archive: "Leads and applications keep this course; it can't be chosen for new ones") | Detail skeleton; 404 → RESOURCE-02 | Transition 422/409 Alert | Actions collapse into a menu on mobile |
| **GROW-08 / ADM-02** `/admissions/leads` | Counsellor, manager | **List:** name, contact (mobile/email), course, campus, owner, status, next follow-up (overdue badge), created. **Board:** columns NEW … INTERESTED with counts and cards (name, course, owner, next follow-up) | "New lead" (`lead.create`); view toggle (Tabs: List / Board); quick filters "My leads", "Unassigned", "Follow-ups due"; per-row and per-card menu: Open, Move to… (`lead.update`), Assign… (`lead.assign`) | Skeleton per view; empty: "No leads yet — add your first enquiry" (with `lead.create`); filtered-empty | Move/assign via Dialogs (§22); 409 → toast "This lead changed — refreshed" plus a refresh | List: mobile cards. Board: horizontal column scroll on tablet+; **on mobile the board shows a status selector (one column at a time)**, per UI-SCREENS ADM-02 |
| **Lead form** `/leads/new`, `/[id]/edit` | Counsellor, manager | Full name; mobile; email; source; interested course (Combobox of ACTIVE courses); campus (Select of the caller's campuses + "Institute-wide"; create only); owner on create ("Me" / "Unassigned"; any member only with `lead.assign`); DOB, city, qualification (optional section) | Save (`lead.create` / `lead.update`) | Pending | "Enter a mobile number or an email"; email format; DOB in the past; **duplicate panel** (§24); field 422s mapped by code | Mobile single column; contact fields first |
| **GROW-09** `/admissions/leads/[id]` | Counsellor, manager | Header (name, status badge, source); contact block; course; campus; owner; created by/at; **Follow-ups** panel (open first, overdue marked); **Activity** feed (notes, transitions, assignments) with "Add note" | Edit (`lead.update`); Change status (`lead.update`); Assign (`lead.assign`); Schedule, complete, cancel follow-up (`lead.update`); Add note (`lead.update`); Back to list | Section skeletons; activity "No activity yet" (never actually empty: CREATED exists); 404 | Status Dialog: target status Select (allowed targets only, from the server rule mirror), reason (required for closing), duplicate target (searchable visible leads). Toast on success | Desktop: main column (details, activity) + side column (status, owner, follow-ups). Mobile: Tabs (Overview / Follow-ups / Activity); sticky primary "Change status" |

- **Audit and trace:** each mutation's response is reflected in the activity feed after refresh.
- **Access denied for an action:** the T01-05 RESOURCE-01 feedback. Hidden buttons are UX only.

---

## 22. Kanban Design

- **Board = a view of `GET /leads?status=<s>&limit=25&sort=-updated_at`** per open status, fetched server-side in parallel (5 requests), with each column's `total`. "Show more" pages a column with `offset`. **No new endpoint and no generic Kanban framework**; a feature component `LeadBoard` is built from `Card`, `Badge` and `DropdownMenu`.
- **Moving a card:** the card's menu "Move to…" lists the server-allowed targets (the client mirror of the §9 table, a UX hint only) and opens the same **Status Dialog** as the detail page (reason when closing). It calls `POST /leads/{id}/transition` with the card's `version`, then refreshes the board.
  - `409` → toast and refresh;
  - `422` → message;
  - `404` → card removed after refresh.
  - The client never moves a card before the server answers (**no optimistic mutation**).
- **Drag-and-drop: not in 02-1.**
  - The menu path is fully keyboard and screen-reader accessible and works on touch.
  - Accessible drag-and-drop (React Aria DnD on a collection) can be added later as a pure enhancement that calls the same endpoint and dialog.
  - Nothing in UI-SCREENS ADM-02 requires drag.
- **Closed statuses** are not columns. They are reachable via the list's status filter.
- **`APPLICATION` and `ADMITTED` columns** appear read-only in 02-2.

---

## 23. Search / Filter / Pagination

All lists use the T01 conventions: `limit`/`offset` (25 default, 100 maximum), `sort` allow-lists, typed filters (an unknown value is a 422), and URL search params on the frontend (bookmarkable; no personal data in params, only IDs and enums).

| List | Search `q` | Filters (MVP) | Sort | Not in MVP |
|---|---|---|---|---|
| Courses | name, code (`ILIKE`, escaped) | `status` (multi), `category` | `name`, `code`, `updated_at` | campus (n/a) |
| Leads | name (`ILIKE`), email (prefix on `email_normalized`), mobile (digits contained in `mobile_key`) | `status` (multi; default all open), `owner` (`me` / `unassigned` / ID), `campus` (ID / `none`; options limited to the caller's campuses), `course`, `source` (multi), `follow_up` (`overdue` / `today` / `upcoming` / `none`), `created_from` / `created_to` | `created_at`, `updated_at`, `full_name`, `next_follow_up_at` | saved views, export, bulk actions, full-text search |

**Leads search caution:** `q` is sent in the query string. Searching by mobile or email therefore puts personal data in a URL. **Mitigation:** the frontend sends the search term only from the search box, never persists it, and the proxy and API logs never record query strings (the T01-09A proxy logs path only; verify the API access-log configuration, as uvicorn's access log is disabled in the dev script). Acceptable for MVP list search; no other personal data travels in URLs.

---

## 24. Duplicate Warning UX

1. On the lead form, after mobile or email loses focus (debounced 400 ms) and before submit, the client calls `POST /leads/duplicate-check` (with `exclude_lead_id` when editing).
2. If candidates exist, a **non-blocking `Alert tone="warning"`** appears below the contact fields:
   - heading "Possible duplicate lead";
   - for each candidate (at most 5): name, course, status badge, campus, owner, created date, and a "Matched on mobile/email" chip;
   - per candidate, "Open lead" opens in a new tab (keeps the form);
   - the alert is focusable and announced (`role="status"`).
3. **Submit stays enabled.** Submitting with candidates shown first asks once in an `AlertDialog`: "Create anyway?", with "Open existing lead" and "Create lead" (Cancel focused). Then it creates.
4. The warning never shows leads the user cannot read; there is no "N more in other campuses" (§8).
5. Network or permission failure of the check → no warning, and creation proceeds. It is a convenience, not a gate.

---

## 25. Audit Model

| Event (category `domain`) | Target | Metadata (no personal values) |
|---|---|---|
| `course.created` | course | `code` |
| `course.updated` | course | `changed_fields` |
| `course.status_changed` | course | `from`, `to` |
| `lead.created` | lead | `source`, `has_course`, `has_campus`, `has_owner` |
| `lead.updated` | lead | `changed_fields` |
| `lead.status_changed` | lead | `from`, `to`, `has_reason` |
| `lead.assigned` | lead | `owner_changed`, `campus_changed` |

- Not audited: follow-ups and notes. They go to the activity timeline only; they are operational, not sensitive administration or compliance events. The audit categories stay meaningful.
- Not audited: list or detail reads. Personal-data access auditing is a `data_access` concern for exports and support sessions, which are later.
- Audit rows are written in the mutation transaction (`write_audit_event`). The actor is the principal; the tenant is the trusted tenant.
- Tenant audit readers (`audit.read`) see these as tenant-realm events (D8-2 filter).
- **User-visible timeline** = `lead_activities` (§12), never `audit_events`.

---

## 26. Seed / Demo Data

Extend `database/seeds/dev.json` and `app/seed.py` (development only; same rules: `.example` emails, generated passwords never stored or printed, sign-in via reset link):

- **Konkan Maritime Training Institute** (MUM, RTN):
  - add members `admissions@…` (`ADMISSIONS_MANAGER`, ALL), `counsellor.mumbai@…` (`COUNSELLOR`, SELECTED MUM) and `counsellor.ratnagiri@…` (`COUNSELLOR`, SELECTED RTN);
  - courses: `GPR` GP Rating (Pre-Sea, 6 months, ACTIVE), `DNS` Diploma in Nautical Science (Pre-Sea, 1 year, ACTIVE), `STCW-BST` STCW Basic Safety Training (Post-Sea, 5 days, ACTIVE), `AFF` Advanced Fire Fighting (Post-Sea, DRAFT), `CCMC` Crowd and Crisis Management (Post-Sea, ARCHIVED);
  - ~14 leads across all open statuses plus one each of LOST, DEFERRED and DUPLICATE (linked); 3 institute-wide (NULL campus) and the rest split MUM/RTN; several unassigned; a pair sharing a mobile number (to show the warning); follow-ups overdue, today and upcoming; 2–3 notes.
- **Coromandel Nautical Academy:** 2 courses and 3 leads, to demonstrate tenant isolation.
- **Fake contact data:** names realistic (CLAUDE §61); mobiles from an obviously fictitious range (for example `+91 90000 10xxx`); emails `@example.com`-style. Seeded values must pass the repository's gitleaks scan; check with the local scan before committing.

---

## 27. Test Strategy

**Backend (pytest; integration tests on PostgreSQL in CI):**
- **Domain:**
  - course and lead transition tables (every pair);
  - reason and duplicate-target rules;
  - normalisation (`mobile_key`, `email_normalized`);
  - duration pair;
  - code format.
- **Permissions:**
  - each route requires its permission (route coverage);
  - `course.manage` denied to a SELECTED-scope holder (tenant scope);
  - a counsellor cannot assign, cannot set another owner on create, and cannot manage courses.
- **Tenant isolation** (per route): A's session → B's course, lead or follow-up ID on GET, PATCH and every command → 404; A's lists, duplicate check and assignees contain zero B rows; a body `tenant_id` → 422; composite foreign keys reject cross-tenant course, campus, membership and lead IDs (schema test).
- **Campus isolation:**
  - restricted counsellor: sees pool and own-campus leads only; other-campus detail → 404; cannot create in, or assign to, an unavailable campus (`422 campus_not_available`, identical for unknown and inaccessible);
  - duplicate check hides other-campus matches;
  - the shared predicate equals `authorize()` (property-style test over the combinations).
- **RLS** (schema tests): policies exist; no DELETE privilege; activities have no UPDATE; readonly has no access to lead tables.
- **Duplicates:** warning-only (create succeeds); match by email and by mobile variants; candidate limit; DUPLICATE leads excluded.
- **Concurrency:** stale `version` → 409 on PATCH, transition, assign and follow-up complete; two concurrent creates with the same course code → one 409.
- **Assignment:** eligibility (inactive member, member without `lead.update`, member outside the campus → `owner_not_eligible`); moving campus with an ineligible owner.
- **Follow-ups:** schedule, reschedule, complete, cancel; closed is immutable; derived next or overdue values in the list.
- **Notes and activity:** append-only; actor names; ordering; no update path.
- **Audit:** exactly the §25 events with metadata **free of names, mobiles, emails and reason/note text** (assert by scanning metadata values).
- **Permission sync:** the drift test passes; existing tenants have the new roles and the Owner/Admin clones gained the six permissions (migration test on a database seeded at 0008, then upgraded).
- **Migration:** upgrade, downgrade, upgrade (existing harness); `alembic check` clean.
- **Business-route cross-tenant registry (V3):** add a registry of business routes → test IDs, plus a meta-test that fails if a route under the new modules lacks a cross-tenant case. T01 routes are recorded as covered by their existing suites. This implements tenancy.md §8 incrementally.

**Frontend (Vitest + Testing Library + axe):**
- Route guards: no session → session-ended; missing permission → AUTHZ-01; 404 → RESOURCE-02.
- PermissionGate on every action.
- Lists: filters → URL params; empty, filtered-empty, error and skeleton states.
- Create and edit forms: validation, 409 and 422 mapping, no server message shown.
- Board: columns, Move to… dialog, 409 refresh, no optimistic move, mobile single-column selector.
- Duplicate warning: shown, open-existing, create-anyway confirmation, failure → silent.
- Detail: follow-ups and notes flows; activity rendering.
- Accessibility (axe Light/Dark; dialogs; focus management; keyboard-only move).
- Data handling: no personal data in console or storage; only IDs and enums in URL params apart from `q`; the server fetch helper forwards only the tenant cookie.
- Requirement map entries; the demo badge removed.

**Integration (API level):** course → lead interest (ACTIVE only; archived course kept on an existing lead); lead → transitions → assignment → follow-up → note → activity timeline in order; the "ready to apply" state (INTERESTED) carries all 02-2 prefill fields.

**D18 Chromium journeys:** run if the environment allows; otherwise recorded as **NOT RUN** (the T01 limitation), not as passed.

---

## 28. Reusable Components

Only components with demonstrated reuse in 02-1 and 02-2:

| Component | Layer | Reuse |
|---|---|---|
| **T02 Data List template** (`PageHeader` + `FilterBar` + `DataTable` + `Pagination` + URL list-state hook `useListParams`) | `design-system/templates` | courses, leads; then applications, students, documents (02-2) |
| **T03 Detail template** (header with status and actions, main/side columns, mobile Tabs) | `design-system/templates` | course, lead; then application, student |
| **Form page layout** (T04 subset: sections, two-column grid from tablet, sticky actions on mobile) | `design-system/templates` | course and lead forms; application wizard steps (02-2) |
| `tenantApiRead()` (server-only, tenant cookie only) | `lib/api` | every page |
| `ActivityFeed` (activity rows → `Timeline`) | `features/activity` | lead; application and Student 360 (02-2) |
| `StatusTransitionDialog` (target, reason, extra fields) | `features/shared` | leads; applications and documents (02-2) |
| `MemberPicker` (assignee Combobox fed by a feature endpoint) | `features/shared` | lead owner and follow-up assignee; application owner (02-2) |
| Status → Badge tone maps | per feature | no new component (Badge exists) |
| `escape_like`, `campus_visibility()`, `record_activity()`, transition-table helper | backend `core` | courses, leads; then 02-2 modules |

**Not built:** a generic Kanban, a generic entity framework, a FollowUpPanel or NotesPanel as design-system components (feature-level only until reused), a new ConfirmDialog (AlertDialog exists), or a FormField (Field and Input exist).

---

## 29. Explicit Deferrals

| Not in 02-1 | Why |
|---|---|
| Public enquiry website / hosted form | Slice 4: needs `tenant_domains`, public realm routes, abuse controls, consent |
| Tenant website builder, tenant domains | Phase 14 (ADR-0003/0004) |
| WhatsApp, email campaigns, SMS, voice, notifications/reminders | Communication slice; needs the outbox, worker and queue (D4) and consent |
| Workflow builder, automation | Phase 10; events are recorded as activities and audit now |
| Lead scoring, campaigns, UTM, import (GROW-10), export, bulk actions, merge | P1/P2; no source requires them for the flow |
| Application, documents, admission, student, conversion action | 02-2 |
| Finance, payment gateway | V1 Finance-lite |
| Batches, course offerings per campus, curriculum | V1 / Phase 05 |
| Student portal, applicant self-service | L4; separate realm |
| AI agent | after communication and operational data (master §20) |
| Advanced analytics, Admissions dashboard (ADM-01) | P1 after 02-2 |
| Platform billing and the remaining platform screens | Post-MVP (L1) |
| Drag-and-drop on the board; ownership-scoped "my leads only" visibility | Enhancements; not required by the specs |

---

## 30. Implementation Sequence

**One branch, one PR, coherent commits** (the user's established commit-plan style):

| Commit | Content |
|---|---|
| **A — docs** | Commit `PHASE-02-MASTER-READINESS.md` and this report (V2). **ADR-0020** "Courses and leads" (records §4–§19, Y-decisions, V3–V6). TASKS.md re-sequenced (L1, V1). New spec-inconsistency entries: lead statuses (V4), lead navigation (V5) |
| **B — backend foundation** | Shared helpers (`escape_like` → core, `campus_visibility`, transition table, `record_activity`). Permissions and role templates in code. Models. **Migration 0009** (tables, RLS, grants, permissions, role clones). Schema, RLS, grant and permission-sync tests. Business cross-tenant registry and meta-test |
| **C — courses + leads API** | `courses` module (router → service → domain → repository); `leads` module (leads, duplicate check, transitions, assignment, assignees, follow-ups, notes, activity). API, isolation, campus, concurrency and audit tests |
| **D — frontend foundation** | `tenantApiRead()`, T02/T03/form templates, `useListParams`, `ActivityFeed`, `StatusTransitionDialog`, `MemberPicker`, requirement-map entries (`course.read`, `lead.read`), demo badge removal, API types (§33 Y9) |
| **E — frontend screens** | ACA-01/02/03, Leads list and board, lead form with duplicate warning, Lead detail with follow-ups and notes; tests and axe |
| **F — seed + status** | Seed extension; DEVELOPMENT-STATUS.md; TASKS.md status; demo walkthrough notes |

Backend B–C and frontend D can overlap once the API schemas from §17 are fixed. E depends on C. Run the full gate (backend with PostgreSQL in CI, frontend, gitleaks, audit) before the PR.

---

## 31. Branch Strategy

- One branch: **`feat/phase-02-1-courses-leads`**, from current `main`.
- One PR, merged with a **merge commit** (never squash).
- No decision branch and no per-entity branches.
- The docs commit (A) travels in the same PR.

---

## 32. Definition of Done

02-1 is complete when, on seed data and on a freshly provisioned tenant, a member can:

1. sign in and see **Courses** and **Leads** in navigation according to their permissions;
2. as Admissions Manager (ALL scope), create, edit, activate, archive and reactivate courses; a counsellor sees the catalogue read-only; a restricted manager cannot manage courses;
3. see the **Leads** list and board, filtered by status, owner, campus, course, source and follow-up state, with pagination;
4. create a lead (contact required, ACTIVE course only, campus within scope or institute-wide, self-assign) and see the **duplicate warning** for a matching visible lead, with "Open lead" and "Create anyway";
5. **assign** owner and campus (manager), with eligibility enforced;
6. **move** a lead through the §9 pipeline from the detail page or the board, with reasons for closing states and duplicate linking, never setting APPLICATION or ADMITTED;
7. **add notes**, and **schedule, complete and cancel follow-ups**, with overdue indication;
8. view the lead's **history** (activity timeline);
9. see **only** their tenant's data and, when campus-restricted, only pool and own-campus leads (404 otherwise);
10. find the §25 audit events, with no personal values in metadata;
11. pass backend (unit, API, PostgreSQL integration, RLS, migration up/down/up, permission sync, cross-tenant registry) and frontend (unit, component, axe Light/Dark) tests;
12. pass ruff, mypy, import-linter, prettier, eslint, tsc and next build; gitleaks and dependency audit clean; CI green; TASKS.md, DEVELOPMENT-STATUS.md and ADR-0020 updated; D18 run or recorded as not run.

**"Ready for 02-2" means:**
- leads carry every prefill field of §13;
- `APPLICATION` and `ADMITTED` exist in the status constraint with a system-only service path stubbed and tested (`mark_application_started` refuses closed leads);
- composite-key targets `UNIQUE (tenant_id, id)` exist on leads and courses;
- the T02/T03/form templates, `ActivityFeed`, `StatusTransitionDialog`, `MemberPicker`, `campus_visibility()` and `record_activity()` are reusable without change.

---

## 33. Decisions Actually Requiring Confirmation

### GREEN (determined by specifications or approved decisions)
- **G1** Courses are tenant-wide, with campus chosen per application (L6, PRD §31, APP-FLOW §20).
- **G2** Leads may be institute-wide; NULL campus = pool visible to `lead.read` holders (L6 + `authorize()` engine semantics).
- **G3** Two role templates, Admissions Manager and Counsellor; Owner and Admin unchanged (L7).
- **G4** No Applicant record; the lead carries the prefill data and 02-2 creates Application, then Student + Admission (L2).
- **G5** Duplicate detection is a warning, not a constraint (PRD §27 "detection", APP-FLOW §9 order).
- **G6** Every transition recorded (APP-FLOW §10), version-checked (T01 locking).
- **G7** Permissions added by migration with role clones (D-B4); campus or tenant scope semantics (D-B1).
- **G8** No platform access to tenant routes (ADR-0005 realm guard; support sessions are Phase 02 platform work).

### YELLOW (implementation choices Claude makes and records in ADR-0020)
- **Y1** Edit rights by campus scope, not by ownership (no ownership-scoped permission in T01).
- **Y2** Lead statuses = APP-FLOW §10 set; APPLICATION/ADMITTED system-only; closed states require a reason; reopen allowed (V4).
- **Y3** `mobile_key` = last 10 digits heuristic (warning-only use).
- **Y4** Per-entity activity tables plus shared helpers (V6), instead of a polymorphic table.
- **Y5** Next follow-up computed, not stored.
- **Y6** Board: click/keyboard "Move to…", no drag-and-drop in 02-1.
- **Y7** Leads canonical under Admissions; GROW › Leads remains `UNRELEASED`; ADM-02 = board view (V5).
- **Y8** No `mti_readonly` grant on lead tables.
- **Y9** Frontend reads in server components; mutations via `TenantSessionProvider.request` + `router.refresh()`; URL params for list state. **TanStack Query and Zod are introduced only when a screen needs client caching or schema-shared forms** (none in 02-1; CLAUDE §64/§74). API types: adopt **OpenAPI-generated types** now (repository-structure.md §2) via a dev-only generator and a CI drift check, after the CLAUDE §74 review. If that review fails, hand-typed contracts as in T01-09A.
- **Y10** Follow-ups and notes are activity-only (not audited); profile edits are audited by field names.
- **Y11** Course categories fixed (`PRE_SEA`, `POST_SEA`, `OTHER`); configurable categories later.

### RED (blocking product, security or architecture decisions)
**None.**

**READY FOR IMPLEMENTATION — NO BLOCKING DECISIONS**

---

## 34. Final Implementation Recommendation

Start `feat/phase-02-1-courses-leads` from `main`. Implement commits A–F of §30 in one PR, against the contracts of §15–§24, with the security tests of §27 as the merge gate:

- migration `0009`;
- modules `courses` and `leads`;
- six permissions and two role templates;
- routes `/app/academics/courses*` and `/app/admissions/leads*` (list + board), on new T02/T03 templates.

The first commit also fixes the repository discrepancies V1–V3: re-sequence TASKS.md, commit the master report, and add the business cross-tenant test registry.

When the Definition of Done (§32) holds, 02-2 (Applications → Documents → Admission → Student) builds directly on these leads, courses, templates and helpers without changing them.
