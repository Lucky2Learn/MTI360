# ADR-0020 — Courses and Leads (Phase 02-1)

- **Status:** Accepted (Phase 02-1)
- **Date:** 2026-10-08
- **Task:** Phase 02-1 Courses + Lead Management
- **Related:** [PHASE-02-MASTER-READINESS.md](../architecture/PHASE-02-MASTER-READINESS.md) (locked decisions L1–L7), [PHASE-02-1-COURSES-LEADS-READINESS.md](../architecture/PHASE-02-1-COURSES-LEADS-READINESS.md) (the implementation blueprint, cited below as "blueprint §n"), [ADR-0004](0004-tenant-isolation.md), [ADR-0011](0011-rbac-model.md), [ADR-0013](0013-audit-events.md), [ADR-0014](0014-tenancy-core.md), [ADR-0016](0016-authorization-rbac.md), [ADR-0019](0019-tenant-administration.md)

## Context

The Phase 02 master readiness review locked L1–L7: the Admissions MVP comes next, a minimal course catalogue is pulled forward from Phase 05, there is no separate Applicant entity, and leads may have no campus. The 02-1 blueprint turned those into contracts for two business modules, `courses` and `leads`. It left eleven implementation choices (Y1–Y11) to be recorded here, and reported six repository discrepancies (V1–V6).

## Decision

### 1. Course catalogue (blueprint §4–§6)

- **Institute-wide.** `courses` has **no `campus_id`**. A later `course_campus_offerings` table (or batches) can say where a course runs, without changing `courses`.
- Fields: `code`, `name`, `category` (`PRE_SEA`, `POST_SEA`, `OTHER`; **Y11** fixed list), `status`, optional `duration_value` + `duration_unit` (both or neither), `eligibility_summary`, `description`, timestamps, `version`.
- `code` follows the campus-code rules (INC-41): `^[A-Z0-9][A-Z0-9-]*$`, at most 32 characters, upper-cased on input, unique per tenant, **immutable**.
- Lifecycle: `DRAFT → ACTIVE`, `DRAFT → ARCHIVED`, `ACTIVE → ARCHIVED`, `ARCHIVED → ACTIVE`. No deletion. Only `ACTIVE` courses can be chosen for a new lead or a changed course of interest; existing references are kept.

### 2. Course authorization uses the T01 semantics unchanged

- `course.read` is **campus-scoped** and `course.manage` is **tenant-scoped** (D-B1).
- A course is an authorization resource whose `campus_id` is always `None`. `authorize()` step 8 admits a campus-scoped permission on a resource with no campus, so a campus-restricted member reads the whole catalogue. `authorize()` step 6 refuses a tenant-scoped permission without all-campus access, so only all-campus members manage it.
- No new authorization mechanism. Tests prove both directions.

### 3. Lead model (blueprint §7, §13–§14)

- One tenant; optional campus (**NULL = institute pool**, L6); optional single owner (`owner_membership_id`); one optional interested course; source from a fixed list.
- Name plus at least one of mobile or email (database CHECK and service rule).
- Optional `date_of_birth`, `city`, `highest_qualification`.
- 02-2 needs no lead migration: every prefill field exists, and `APPLICATION` and `ADMITTED` are already in the status CHECK.

### 4. Lead statuses (Y2; V4, INC-44)

- The **APP-FLOW §10** vocabulary, a superset of PRD §27: `NEW`, `CONTACTED`, `QUALIFIED`, `COUNSELLING`, `INTERESTED` (open); `APPLICATION`, `ADMITTED` (progressed, **system only, set by 02-2**); `NOT_ELIGIBLE`, `LOST`, `DEFERRED`, `DUPLICATE` (closed).
- The transition table lives in `app/modules/leads/domain.py`:
  - open → another open status;
  - open → closed: `NOT_ELIGIBLE`, `LOST` and `DEFERRED` need a reason; `DUPLICATE` needs a different, visible, non-duplicate target lead;
  - closed → open ("reopen") needs a reason;
  - `APPLICATION`, `ADMITTED` and same-status moves are refused (`422 invalid_transition`).
- `mark_application_started()` is the 02-2 entry point. It is a system transition to `APPLICATION` that refuses closed leads. 02-1 tests it but does not call it from any route.

### 5. Duplicate detection: warning only (blueprint §8, §24; Y3)

- No uniqueness constraint on contact details.
- Keys are service-maintained columns:
  - `email_normalized`: trimmed and lower-cased;
  - `mobile_key`: the last 10 digits of the digits-only mobile, or all of them when there are fewer.
- `POST /leads/duplicate-check` uses POST, so contact details never appear in a URL. It searches only leads the caller may read (tenant through RLS and the ORM filter; campus through the shared predicate, §7). It excludes `DUPLICATE` leads and returns at most five candidates.
- Nothing about invisible matches is disclosed, not even a count.

### 6. Assignment is a work queue, not a boundary (Y1)

- `lead.assign` sets owner and campus together. The caller must be able to see both the old and the new campus.
- An eligible owner is an `ACTIVE` membership whose effective permissions (`membership_access()`) include `lead.update` and whose campus scope covers the lead's campus.
- A creator without `lead.assign` may only self-assign (`owner: "me"`).
- Edit rights come from `lead.update` plus campus visibility, **not from ownership**. T01 has no ownership-scoped permission, and adding one would be a new authorization concept.

### 7. Campus visibility predicate (blueprint §19)

- `app.core.authz.campus_visibility(column, context)` is the single SQL form of `authorize()` step 8:
  - no predicate for all-campus members;
  - `campus_id IS NULL OR campus_id IN (:campus_ids)` otherwise.
- Every lead list, the duplicate check and the assignee query use it. A unit test checks it against `authorize()` over every combination.
- Campus scope is not in RLS: tenant isolation is RLS; campus scope is application-enforced (D-B1, as for campuses).

### 8. Follow-ups and activity (Y4, Y5, Y10; V6)

- **Follow-ups:** a dedicated `lead_follow_ups` table (`OPEN → DONE | CANCELLED`). Overdue and "next follow-up" are derived, never stored. There are no reminders, scheduler or notifications.
- **Activity:** a **per-entity** append-only `lead_activities` table (V6). A polymorphic table cannot carry the composite tenant foreign keys every T01 table uses. A shared code-level helper, `app.core.activity.record_activity()`, and the frontend `ActivityFeed` are reused by 02-2.
- The runtime role has SELECT and INSERT only on `lead_activities`. Notes are `NOTE` activities and are immutable.
- Follow-ups and notes are **activity only, not audited**.

### 9. Audit (blueprint §25)

Seven `domain` events:
- `course.created`, `course.updated`, `course.status_changed`;
- `lead.created`, `lead.updated`, `lead.status_changed`, `lead.assigned`.

Metadata carries codes, statuses, field names, booleans and counts only. It never carries names, mobiles, emails, reason text or note text; a test scans it.

### 10. Permissions, roles and migration `0009` (blueprint §15–§18)

- **Permissions:** six new codes:
  - `course.read` (campus);
  - `course.manage` (tenant);
  - `lead.read`, `lead.create`, `lead.update`, `lead.assign` (campus).
- **Roles:** two new system templates, `ADMISSIONS_MANAGER` (all six) and `COUNSELLOR` (`course.read`, `lead.read`, `lead.create`, `lead.update`). `INSTITUTE_OWNER` and `ADMIN` gain the six through their existing template rules.
- **Migration `0009`:**
  - creates the four tables with realm-agnostic tenant RLS, composite foreign keys and no DELETE privilege;
  - inserts the permissions;
  - clones the two new roles into every existing tenant;
  - adds the six permissions to the existing Owner and Admin clones.
- New tenants receive the new roles through `clone_system_roles()`.
- **Readonly role (Y8):** `mti_readonly` may read `courses` only, never the lead tables.
- **Downgrade:** a development operation that loses data. It removes the new roles' assignments and the permissions it added, then drops the tables. The system-role protection trigger is suspended for that statement only, as the table owner.

### 11. Cross-tenant route registry (V3)

- `app/api/coverage.py` proves permission coverage only. 02-1 adds `tests/security/cross_tenant_registry.py`: every route of the `courses` and `leads` modules maps to the named cross-tenant test that exercises it.
- A meta-test fails when a route of those modules is missing from the registry, or when a named test does not exist.
- T01 routes are recorded as covered by their existing suites. This implements tenancy.md §8 incrementally.

### 12. Frontend (Y6, Y7, Y9; V5)

- **Leads route:** canonical at `/app/admissions/leads`. `?view=board` is ADM-02.
  - GROW › Leads stays `UNRELEASED`.
  - The hard-coded "12 new enquiries" badge is removed rather than replaced by a fabricated count.
- **Board:** "Move to…" menus that call the transition endpoint. No drag-and-drop and no optimistic moves.
- **Data access:**
  - reads happen in server components through a server-only `tenantApiRead()` helper that forwards the tenant cookie only;
  - mutations go through `TenantSessionProvider.request` and are followed by `router.refresh()`;
  - list state lives in URL parameters, which hold IDs and enums only, plus the search box term.
- **Dependencies (Y9):** TanStack Query and Zod are not added, because no 02-1 screen needs client caching or schema-shared forms. OpenAPI type generation is **not** adopted in 02-1; contracts are hand-typed as in T01-09A (§13).

### 13. Deviation recorded

Y9 proposed OpenAPI-generated types after a CLAUDE §74 review. That review is deferred: adding a generator, its lockfile entries and a CI drift check would roughly double the dependency and CI surface of this slice. Hand-typed contracts, covered by component tests against fixtures shaped like the API, carry the same risk T01-09A accepted. 02-2 or a dedicated tooling task should revisit it.

## Consequences

- 02-2 builds Applications on these tables, helpers and templates without a lead migration.
- Ownership-scoped visibility ("my leads only"), configurable categories and sources, drag-and-drop, merge, import and export remain open enhancements.
- Each later business module adds its own `*_activities` table and registers its routes in the cross-tenant registry.
