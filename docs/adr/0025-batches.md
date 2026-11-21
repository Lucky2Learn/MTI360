# ADR-0025 — Batches: Allocation, the Payment Gate and Database-Enforced Seats

- **Status:** Accepted (business decisions approved by the user in the Phase 02-6 plan and directive, 2026-11-20). Implemented on `feat/platform-tenant-management` (uncommitted); not browser-verified.
- **Date:** 2026-11-20
- **Task:** Phase 02-6 Batches (V1), T05-03 (ACA-05, ACA-06, ACA-07)
- **Related:** [ADR-0004](0004-tenant-isolation.md), [ADR-0013](0013-audit-events.md), [ADR-0016](0016-authorization-rbac.md), [ADR-0020](0020-courses-and-leads.md) §8 (activity), [ADR-0021](0021-admissions-core.md), [ADR-0022](0022-finance-lite.md) (L3: payment gates enrolment in 02-6)

## Context

An admitted student must be placed in a batch (one intake of one course at one campus) to be enrolled. Seats are limited and several staff may allocate at once. Under L3 admission does not wait for payment; payment gates enrolment here.

## Decisions (approved by the user)

1. **Batch:** course, campus, code (unique per institute), name, intake label, dates, capacity 1–500, status `OPEN | CLOSED | CANCELLED`, optimistic `version`. Course must be `ACTIVE`; course and campus never change; new batches are `OPEN`; `CLOSED` reopens; `CANCELLED` only without active allocations and is final; capacity never below active allocations.
2. **Allocation** of an `ADMITTED` admission of an active student, same course and campus, `OPEN` batch with a free seat → admission `ENROLLED`. One active allocation per admission. **Transfer** to another open batch of the same course keeps `ENROLLED`; **withdrawal** (reason required) returns `ADMITTED`. History is never deleted.
3. **Payment gate — decision B:** a normal allocation needs the admission's live fee invoice to be `PAID`. Otherwise an allocator (`batch.allocate`) may override with a reason; the override records the invoice state, the outstanding amount, the user and the time, and is audited. A missing or cancelled invoice is never paid. No institute settings framework (configurability is Phase 03).
4. **Permissions** `batch.read`, `batch.manage`, `batch.allocate` (all campus-scoped). Owner, Administrator and Admissions manager: all three. Counsellor, Finance manager and Finance officer: `batch.read`.

## Implementation decisions

- **Migration `0014`:** `batches`, `batch_allocations`, `batch_activities` (append-only); `admissions.status` accepts `ENROLLED` (no backfill). Realm-agnostic tenant RLS; no DELETE for the runtime role; the read-only role reads `batches` only.
- **Composite keys** bind an allocation's `(admission, student, campus, course)` to one admission (the 0011 key) and `(batch, course, campus)` to one batch, so the database rejects cross-course, cross-campus and cross-tenant allocations. A partial unique index allows one `ACTIVE` allocation per admission.
- **Seats are counted by the database.** Trigger `batch_allocations_count` (SECURITY INVOKER) increments `batches.allocated_count` on an active insert only while the batch is `OPEN` (SQLSTATE `MT014` otherwise) and decrements when an allocation ends; `CHECK (allocated_count <= capacity)` rejects over-filling, and an ended allocation is immutable (`MT015`). The service also locks rows (allocation → admission → batches by ID, deadlock-free) and checks every rule first, for clear errors; the database is the backstop if application checks are bypassed.
- **Payment basis** recorded per allocation: `PAID`, `OVERRIDE` (with reason, invoice state and outstanding amount, by CHECK) or `TRANSFER`.
- **Errors:** 404 for a batch or allocation outside the caller's tenant or campuses; 422 `*_not_available` for an admission or target batch named in a body (the same answer as an unknown ID); 409 for a stale version, a taken code or an ended allocation; 422 with detail codes for business rules (`payment_required`, `batch_full`, `batch_not_open`, `already_allocated`, …).
- **Student 360:** the timeline shows `ALLOCATED`, `TRANSFERRED_IN` and `WITHDRAWN` batch activity to `batch.read` holders; each admission carries its current batch; allocation history is read from `GET /batch-allocations?student_id=` (no student-specific route, like fees).
- **Audit** (`domain`): `batch.created`, `batch.updated`, `batch.status_changed`, `batch.student_allocated`, `batch.payment_overridden`, `batch.student_transferred`, `batch.student_withdrawn`. Metadata never includes names or the free-text reasons.

## Consequences

- The detail page reads at most 100 active and 100 ended allocations; a note appears when a batch has more (capacity allows 500). Paged allocation lists on ACA-06 are later work.
- The payment gate is fixed (decision B) until Phase 03 adds institute settings.
