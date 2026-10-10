# Phase 02-5 Finance-lite Readiness

- **Status:** Implementation plan (2026-10-10) on `main` at `2ea72f6`. Decisions approved and recorded in [ADR-0022](../adr/0022-finance-lite.md). Documentation only: nothing is implemented, migrated or released.
- **Builds on:** [PHASE-02-MASTER-READINESS.md](PHASE-02-MASTER-READINESS.md) (§17, §22, L1, L3 and its 2026-10-10 addendum), [ADR-0021](../adr/0021-admissions-core.md), [ADR-0020](../adr/0020-courses-and-leads.md), [tenancy.md](tenancy.md), [authorization.md](authorization.md).
- **Verified against (read-only, at `2ea72f6`):**
  - backend: migration `0010_admissions_core`; `app/modules/students/{sequences,domain}.py`; `app/modules/applications/service.py` (`admit`); `app/core/{audit,activity,transitions,authz,ratelimit}`; `tests/cross_tenant_registry.py`; the import-linter contracts in `backend/pyproject.toml`;
  - frontend: `frontend/src/shells/experiences/tenant.ts` and the Student 360 page;
  - specifications: PRD §38, APP-FLOW §26, ARCHITECTURE (Finance tables, Phase 07), UI-SCREENS FIN-01…FIN-10, TASKS T06-01…T06-10.
- **Audience:** the Claude Code session that implements 02-5, and the reviewer of its PR.

---

## 1. Repository facts that shape the plan

- **Finance starts from scratch.** No money type, currency, `Decimal` or `Numeric` exists in the backend, and there is no idempotency-key mechanism.
- **No tenant settings to rely on.** The tenant has no currency or time-zone setting; campus time zones are not modelled (INC-40).
- **Numbering can be reused but needs widening.** `tenant_sequences` gives transactional, gap-free numbers, but a CHECK limits it to `APPLICATION`, `ADMISSION` and `STUDENT`, and the allocator lives in `app.modules.students`.
- **Admissions carry the billing context.** An Admission row holds `student_id`, `course_id`, `campus_id` and `admission_number`. Its only status is `ADMITTED`.
- **The navigation slot exists.** The Finance navigation group (Fee Structure, Invoices, Payments, Outstanding, Refunds, Reports) exists and is `UNRELEASED`.
- **Student 360 is ready for a Fees section.** It lists "Fees" as a later section with an intentional empty state.
- **The seed is thin for finance.** It has one admitted student in Konkan and one in Coromandel.

## 2. Scope

**Workflow:** fee structure (per course) → issue a fee invoice for an Admission → record an offline payment → confirm → receipt → outstanding balance → reverse a payment or cancel an invoice when needed.

| Capability | MVP | Note |
|---|---|---|
| Fee structures with fee-head lines; one active per course | In | Institute-wide, like courses |
| Fee invoice per Admission, lines copied at issue, adjustable at issue | In | Non-tax (ADR-0022 §2, §7) |
| Offline payments: cash, UPI, bank transfer (confirmed); cheque, DD (pending) | In | ADR-0022 §4 |
| Receipt per confirmed payment | In | FY numbering (ADR-0022 §3) |
| Outstanding and overdue list; summary strip | In | FIN-01 dashboard deferred (master §21: no invented numbers) |
| Student 360 Fees section | In | Replaces the placeholder |
| Payment reversal (separation of duties) and invoice cancellation | In | No deletion |
| Printable receipt and fee invoice (print stylesheet) | In | No PDF dependency |
| GST / tax invoices, tax lines, credit notes, e-invoicing | **Out** | ADR-0022 §2 |
| Refunds (FIN-09), discounts, scholarships, instalments | Out | Full Finance |
| Payment gateway, webhooks, reconciliation, accounting exports | Out | T06-08 |
| One payment across several invoices; advances or credit | Out | |
| Several live invoices per admission | Out | ADR-0022 §8 |
| Reminders (WhatsApp, email, SMS) | Out | 02-7 |
| Payment gate on enrolment and batch allocation (L3) | Out | 02-6 reads the balance |
| FIN-10 Reports, ANA-03, STU-07 Student Portal fees | Out | Later phases |

## 3. User journeys

- **J1 — Fee structure.** A finance manager creates a draft structure for a course (for example B.Sc. Nautical Science: Tuition, Hostel, Uniform, Medical) and activates it. Activation archives the previously active structure for that course.
- **J2 — Issue a fee invoice.** From Student 360 or Invoices, "Raise fee invoice" for an Admission. The lines are prefilled from the active structure and may be adjusted; an adjustment needs a reason. Set the due date and issue, which assigns `INV-FY2026-27-nnnnn`.
- **J3 — Record a payment.** Cash, UPI or bank transfer is confirmed on save: the balance drops and the receipt `RCT-FY2026-27-nnnnn` is issued. A cheque or DD is saved `PENDING`; it is confirmed after clearance (receipt, balance) or failed with a reason.
- **J4 — Reverse a payment.** A different member who holds `payment.reverse` reverses it with a reason. The balance is restored and the receipt is shown as cancelled.
- **J5 — Cancel a fee invoice.** Cancelling requires a reason and is allowed only when the invoice has **no `CONFIRMED` and no `PENDING` payment**. The server refuses it otherwise, with 422 `invalid_transition`, and the screen names the payments that must be resolved first:
  - **A `PENDING` cheque or DD:** a holder of `payment.record` resolves it. **Fail** it with a reason if it was not honoured, or **Confirm** it after clearance (which issues a receipt and reduces the balance) and then reverse it as for a confirmed payment.
  - **A `CONFIRMED` payment:** a member other than its recorder, holding `payment.reverse`, **reverses** it with a reason (ADR-0022 §9). The receipt stays and is shown as cancelled.
  - **After resolution:** once no payment is `PENDING` or `CONFIRMED`, the invoice can be cancelled. `FAILED` and `REVERSED` payments stay attached to the cancelled invoice as history. A replacement invoice gets a new number (ADR-0022 §8).
- **J6 — Outstanding.** Overdue fee invoices, filtered by campus, course and due date, with a summary strip.

## 4. Screens and routes

| ID | Route | Template | Actions | Filters | Permission |
|---|---|---|---|---|---|
| FIN-02 | `/app/finance/fee-structure` | T02 | New structure | course, status, search | `fee_structure.read` |
| FIN-03 | `/app/finance/fee-structure/[id]`, `/new`, `/[id]/edit` | T03 + FormLayout | Edit (draft), Activate, Archive | — | read; `fee_structure.manage` |
| FIN-04 | `/app/finance/invoices` | T02 | Raise fee invoice | status, campus, course, due range, overdue, search (invoice, admission, student number) | `invoice.read` |
| — | `/app/finance/invoices/new?admission=…` | T04 FormLayout | Issue (editable lines, adjustment reason, exact live total in paise) | — | `invoice.issue` |
| FIN-05 | `/app/finance/invoices/[id]` (+ print view) | T03 | Record payment (dialog), Cancel (`StatusTransitionDialog`) | — | read; `payment.record`; `invoice.cancel` |
| FIN-06 | `/app/finance/payments` | T02 | — | method, status, campus, received date | `invoice.read` |
| FIN-07 | `/app/finance/payments/[id]`, `/[id]/receipt` (print) | T03 | Confirm, Fail (pending), Reverse, Print | — | read; `payment.record`; `payment.reverse` |
| FIN-08 | `/app/finance/outstanding` | T02 (invoice list, balance > 0) + summary strip | — | campus, course, overdue | `invoice.read` |
| ADM-12 Fees | Student 360 section | Card + table | Raise fee invoice, Record payment | — | `invoice.read` (+ action permissions) |

**Navigation and shared behaviour:**

- **Navigation:** Fee Structure, Invoices, Payments and Outstanding are released in the requirement map. Refunds and Reports stay `UNRELEASED`.
- **States:** every screen has skeleton, empty, filtered-empty, error, AUTHZ-01 (permission denied) and RESOURCE-02 (not found), as in 02-1 and 02-2. The empty state explains that fee invoices are raised from an admitted student.
- **Amounts:** formatted with `Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' })` in tabular numerals and right-aligned. Status is always a text badge.
- **Labels:** every fee invoice view and print shows "Fee invoice — not a tax invoice".
- **Mobile:**
  - lists become cards (number, student, balance, status);
  - the payment dialog becomes a full-height sheet;
  - header actions stack at full width (02-1 D-3);
  - print views are single-column.
- **Theming:** Light, Dark and System use existing tokens only.

## 5. Entities

All carry `tenant_id` and `UNIQUE (tenant_id, id)`, use composite tenant foreign keys, are versioned where they can change, and are never deleted.

| Entity | Key fields | Mutability |
|---|---|---|
| `fee_structures` | `course_id`, name, `status` DRAFT/ACTIVE/ARCHIVED, `items` JSONB (fee head, `amount_minor`), `total_minor`, `currency`, version | Items change only in DRAFT (trigger); partial unique index: one ACTIVE per course |
| `invoices` | `number` (unique; allocated at issue), `admission_id`, `student_id`, `course_id`, `campus_id` (one composite FK to `admissions`), `fee_structure_id`, `fee_structure_version`, `structure_total_minor`, `total_minor`, `paid_minor`, `currency`, `due_date`, `adjusted`, `adjustment_reason`, `status`, `status_reason`, `issued_at`, `idempotency_key`, `request_hash`, version | Only `status`, `status_reason`, `paid_minor` and `version` change, under the row lock; CHECK `0 ≤ paid_minor ≤ total_minor` |
| `invoice_lines` | `invoice_id`, position, `fee_head`, `structure_amount_minor` (nullable), `amount_minor ≥ 0` | Insert-only (privileges) |
| `payments` | `invoice_id`, `student_id`, `campus_id`, `amount_minor > 0`, `currency`, `method`, `reference`, `received_on`, `recorded_by_membership_id`, `status` PENDING/CONFIRMED/FAILED/REVERSED, `status_reason`, `confirmed_at`, `idempotency_key`, `request_hash`, version | Only the status fields change |
| `receipts` | `number` (unique), `payment_id` (unique), copies of the amount, method, fee invoice number and student number, `issued_at` | Insert-only; "cancelled" is read from the payment's status |
| `finance_activities` | subject (`invoice_id`), kind, actor, details | Append-only; joins the Student 360 timeline |

**State transitions** (ADR-0022 §4, §5):

```text
Fee invoice  ISSUED → PARTIALLY_PAID → PAID       follows paid_minor
             ISSUED → CANCELLED                     reason; no CONFIRMED or PENDING payment
                                                    (fail or confirm-then-reverse each PENDING,
                                                    reverse each CONFIRMED first; see J5)
Payment      CASH / UPI / BANK_TRANSFER → CONFIRMED (on record)
             CHEQUE / DEMAND_DRAFT      → PENDING → CONFIRMED (clearance) | FAILED (reason)
             CONFIRMED → REVERSED                   reason; not by the recorder
Fee str.     DRAFT → ACTIVE → ARCHIVED; DRAFT → ARCHIVED
```

## 6. Permissions and roles

| Code | Scope | Owner / Admin | FINANCE_MANAGER | FINANCE_OFFICER | Admissions manager | Counsellor |
|---|---|---|---|---|---|---|
| `fee_structure.read` | campus (reads the institute catalogue) | ✓ | ✓ | ✓ | ✓ | ✓ |
| `fee_structure.manage` | tenant-wide (as `course.manage`) | ✓ | ✓ | — | — | — |
| `invoice.read` (includes payments, receipts) | campus | ✓ | ✓ | ✓ | ✓ | — |
| `invoice.issue` | campus | ✓ | ✓ | ✓ | — | — |
| `invoice.cancel` | campus | ✓ | ✓ | — | — | — |
| `payment.record` (includes confirm, fail) | campus | ✓ | ✓ | ✓ | — | — |
| `payment.reverse` | campus | ✓ | ✓ | — | — | — |

- **Existing grants for the new templates:** both finance templates also get `student.read` and `course.read`.
- **Checks:** every route requires exactly one permission, and services re-check the campus with `authorize()`.
- **Reversal:** the recorder cannot reverse (ADR-0022 §9), and there is no step-up (§10).

## 7. API (tenant realm, `/api/v1`, module `finance`)

| Method | Path | Permission |
|---|---|---|
| GET | `/fee-structures` | `fee_structure.read` |
| POST | `/fee-structures` | `fee_structure.manage` |
| GET | `/fee-structures/{id}` | `fee_structure.read` |
| PATCH | `/fee-structures/{id}` | `fee_structure.manage` |
| POST | `/fee-structures/{id}/status` | `fee_structure.manage` |
| GET | `/invoices` | `invoice.read` |
| POST | `/invoices` | `invoice.issue` |
| GET | `/invoices/{id}` | `invoice.read` |
| POST | `/invoices/{id}/cancel` | `invoice.cancel` |
| POST | `/invoices/{id}/payments` | `payment.record` |
| GET | `/payments` | `invoice.read` |
| GET | `/payments/{id}` | `invoice.read` |
| POST | `/payments/{id}/confirm` | `payment.record` |
| POST | `/payments/{id}/fail` | `payment.record` |
| POST | `/payments/{id}/reverse` | `payment.reverse` |
| GET | `/students/{id}/fees` | `invoice.read` |
| GET | `/finance/summary` | `invoice.read` |

Every route has an entry in the cross-tenant registry, with an explicit cross-tenant test.

**Idempotency and concurrency:**

- **Idempotency key:** the client creates a UUID once per form and reuses it on retry. The table holds `UNIQUE (tenant_id, idempotency_key)` and a `request_hash`.
  - The same key and payload return the original record (200).
  - A different payload returns 409.
  - Concurrent duplicates are settled by the unique constraint.
- **Invoice lock:** the invoice row is locked (`SELECT … FOR UPDATE`) for every payment change.
- **Overpayment:** refused with 422.
- **Stale edits:** the optimistic `version` check returns 409.
- **Gap-free numbers:** FY numbers are allocated in the same transaction (ADR-0022 §3).
- **Rate limit:** payment recording is rate-limited per member (`RateLimiter`).

**Audit (domain, in-transaction):** `fee_structure.created/updated/activated/archived`, `invoice.issued/cancelled`, `payment.recorded/confirmed/failed/reversed`.

- **Recorded:** IDs as targets, `amount_minor`, `currency`, `method`, the status from and to, `has_reason`; for issue, `structure_total_minor`, `adjusted` and the adjusted-line count.
- **Never recorded:** names, payment references (cheque or UTR numbers) or reason text.

## 8. Migration and tenant isolation

**Migration `0011_finance_lite`** (frozen constants, the 0010 pattern):

1. Create the tables of §5. Composite foreign keys go to `courses`, `campuses`, `students` and `admissions`.
2. Add `UNIQUE (tenant_id, id, student_id, campus_id, course_id)` on `admissions`, for the invoice's composite foreign key.
3. Widen the `tenant_sequences.name` CHECK with `INVOICE` and `RECEIPT`. For these names, `period` is the FY start year (ADR-0022 §3).
4. Add realm-agnostic tenant RLS on every new table.
5. Set privileges:
   - SELECT, INSERT and UPDATE for the application role, **never DELETE**;
   - SELECT and INSERT only on `invoice_lines`, `receipts` and `finance_activities`;
   - for `mti_readonly`: `fee_structures` only.
6. Add the trigger that freezes `fee_structures.items` outside DRAFT, and the partial unique indexes (one ACTIVE structure per course; one live invoice per admission).
7. Add the 7 permissions, the `FINANCE_MANAGER` and `FINANCE_OFFICER` templates cloned into every tenant, extended Owner/Admin clones, and the Admissions manager and Counsellor grants. The upgrade refuses a custom-role name clash. The downgrade is documented as losing data.

**Code outside the new module:**

- Move `next_number` and `SequenceName` to `app.core`, and add the FY period computation there. Admissions behaviour is unchanged.
- Add `app.modules.finance` to `BUSINESS_MODULES`.

**Seed (development only):**

- **Konkan:**
  - about six more admitted students across courses;
  - fee structures for the active courses, plus one draft and one archived;
  - fee invoices that are paid, partially paid, unpaid and overdue, cancelled and replaced, and adjusted;
  - one pending cheque, one failed DD and one reversed payment.
- **Coromandel:** one fee invoice and one payment (cross-tenant fixtures).

## 9. Tests

**Backend:**

- **Unit:**
  - money parsing and formatting;
  - the FY computation, including the boundary instants `2027-03-31T18:29:59Z` and `2027-03-31T18:30:00Z`, 1 January, and the FY2099-00 label;
  - the number format;
  - transition tables, balance and status derivation;
  - the adjustment detection;
  - the idempotency request hash.
- **API:** every route, covering success, validation, 409 (stale, idempotency mismatch), 422 (overpayment, invalid state, missing reason, missing reference) and 403/404 (permission and scope); separation of duties on reverse; cancel refused with a confirmed or pending payment.
- **Concurrency:**
  - two parallel payments exceeding the balance: one succeeds;
  - the same idempotency key in parallel: one payment;
  - parallel confirmations: unique, gap-free receipt numbers;
  - parallel issue for one admission: one invoice;
  - a rolled-back issue leaves no gap.
- **Invariant:** `paid_minor = Σ CONFIRMED amount_minor` after every operation; a pending payment changes neither the balance nor the receipts.
- **Security:**
  - the cross-tenant registry and meta-test;
  - cross-campus visibility on lists, details, Student 360 and the summary;
  - composite-FK rejection of another tenant's admission;
  - RLS without tenant context;
  - privileges (no DELETE; no UPDATE on insert-only tables);
  - the trigger freezing structure items;
  - audit metadata free of names, references and reason text.
- **Schema:** migration 0011 down/up/clash-refusal; `alembic check`; the permission drift and sync tests; the seed contract.

**Frontend (Vitest):**

- the paise parser (rejects `1.005`, negatives and malformed grouping);
- forms and their 409/422 mapping;
- the idempotency key reused on retry;
- dialogs and focus;
- `PermissionGate` on every action;
- list states and filters in the URL;
- the Student 360 Fees section;
- the requirement map;
- the non-tax label;
- axe in Light and Dark;
- no amounts or references in the console or storage.

## 10. Acceptance criteria

1. On seed data, a finance officer issues a fee invoice for an admitted student, records a partial cash payment and a UPI payment, and gets a receipt for each, numbered `RCT-FY…`. The balance and status are correct throughout.
2. A cheque is `PENDING`: no receipt and no balance change until it is confirmed. Failing it requires a reason and issues no receipt.
3. A finance manager, not the recorder, reverses a payment with a reason. The balance is restored, the receipt is shown as cancelled, and nothing is deleted. The recorder's own attempt is refused.
4. An adjusted fee invoice shows the structure and issued amounts, with the reason; dropped structure lines appear at zero. Cancellation is refused while a payment is `PENDING` or `CONFIRMED`, and succeeds once each is failed or reversed. A cancelled invoice stays in history, and its replacement has a new number. A second live invoice for the same admission is refused.
5. Every amount is integer paise in INR. No float is used anywhere.
6. Campus-restricted members see only their campuses; tenant A sees nothing of tenant B.
7. All gates are green: the backend with `REQUIRE_DATABASE_TESTS=1`, frontend, lint, types, build, CI and CodeQL. The D18 Chromium journeys are recorded as run or **NOT RUN**, never as passed without running.
8. TASKS.md, DEVELOPMENT-STATUS.md and ADR-0022 are updated honestly. Production use stays conditional on ADR-0022 §2 and §3.

## 11. Implementation sequence (one branch `feat/phase-02-5-finance-lite` from current `main`; one PR; merge commit)

1. `refactor:` move the sequence allocator to `app.core`; add the FY period (no admissions behaviour change)
2. `feat:` migration 0011 (tables, RLS, privileges, triggers, indexes, the admissions unique constraint, the sequence CHECK, permissions and role templates); money and domain rules
3. `feat:` the fee structure API
4. `feat:` fee invoices, payments, receipts and the summary API: idempotency, locking, audit, activity, rate limit
5. `test:` cross-tenant registry entries, concurrency and invariant tests
6. `feat(frontend):` money helpers, the finance API client, the requirement-map release
7. `feat(frontend):` FIN-02/03, FIN-04/05 with the issue form, FIN-06/07 with the receipt print view, FIN-08 with the summary strip, Student 360 Fees
8. `feat:` the development seed extension
9. `docs:` DEVELOPMENT-STATUS.md, TASKS.md and ADR-0022 implementation notes, with the verification actually run

## 12. Risks and open items

- **Production conditions (do not block implementation):**
  - the tenant's tax treatment (ADR-0022 §2, INC-48);
  - the receipt FY date basis, confirmation versus `received_on` (ADR-0022 §3, INC-49).
- **Overdue uses the IST date.** Campus time zones are still not modelled (INC-40).
- **JSONB fee-structure items** are a first for this codebase. They are validated in the service and frozen by a trigger.
- **Single-user institutes** cannot reverse a payment without a second finance member (ADR-0022 §9).
- **The slice is large:** about 17 routes and 8 screens, similar to 02-2.

## 13. Verification gaps carried from the post-merge verification (2026-10-10)

- There is no in-repository Chromium/Playwright harness (D18: out-of-repository in T01; in-repository Playwright in Phase 16).
- The local `api` and `frontend` images were built on 2026-09-26 and 2026-09-29. They predate T01-04 and do not represent `main`.
- The real-S3 storage test is not run in CI (no `TEST_S3_*`). It last passed locally at `4367542`.
- The PostgreSQL integration tests ran and passed in CI on `2ea72f6` (`REQUIRE_DATABASE_TESTS=1`), but were skipped in the local post-merge run.

**Proposed separate task, V-02 Runtime and browser verification** (not part of 02-5; needs its own approval):

- an approved rebuild and migration of the development stack only;
- a decision on pulling a minimal Playwright harness forward from Phase 16;
- journeys for 02-1, 02-2 and 02-5 at 390/768/1024/1440 in Light and Dark with axe;
- a CI step for the S3 test against a SeaweedFS service.
