# ADR-0022 — Finance-lite: Fee Structures, Fee Invoices, Offline Payments and Receipts (Phase 02-5)

- **Status:** Accepted (decisions approved 2026-10-10; not implemented)
- **Date:** 2026-10-10
- **Task:** Phase 02-5 Finance-lite (V1)
- **Related:** [PHASE-02-5-FINANCE-LITE-READINESS.md](../architecture/PHASE-02-5-FINANCE-LITE-READINESS.md) (the implementation plan), [PHASE-02-MASTER-READINESS.md](../architecture/PHASE-02-MASTER-READINESS.md) (§17 Finance dependency, §22 slice table, L1, L3; dated addendum), [ADR-0021](0021-admissions-core.md) (admissions, students, `tenant_sequences`), [ADR-0020](0020-courses-and-leads.md), [ADR-0004](0004-tenant-isolation.md), [ADR-0013](0013-audit-events.md), [ADR-0016](0016-authorization-rbac.md), INC-15, INC-48, INC-49

## Context

Phases 02-1 and 02-2 are merged to `main` (PR #32, merge commit `2ea72f6`): an institute can take an enquiry through to an admitted student. The master readiness review placed **Finance-lite** after the Admissions MVP as slice **02-5** (§17: a fee per course, an invoice raised on admission, a manually recorded payment and a receipt, an outstanding balance; no gateway, instalments, refunds, discounts, scholarships or reconciliation). Under L3, admission does not wait for payment; payment will gate enrolment and batch allocation in 02-6.

The Finance-lite readiness review (2026-10-10, recorded in [PHASE-02-5-FINANCE-LITE-READINESS.md](../architecture/PHASE-02-5-FINANCE-LITE-READINESS.md)) inspected the repository at `2ea72f6`:

- no money type, currency or idempotency-key mechanism exists;
- the tenant has no currency or time-zone setting;
- `tenant_sequences` gives transactional, gap-free numbers per tenant, sequence and calendar year (UTC). It is limited by a CHECK to `APPLICATION`, `ADMISSION` and `STUDENT`, and its allocator lives in `app.modules.students`.

The review raised decisions S1 and F1–F8. They were approved on 2026-10-10 as recorded below.

## Decision

### 1. Phase identifier and delivery order (S1)

- The slice keeps the identifier **02-5 — Finance-lite**. No phase or slice identifier is renumbered.
- **Delivery order change:** 02-5 is delivered **ahead of** 02-3 (Seed + demo hardening) and 02-4 (Public enquiry), which were sequenced before it by L1 (TASKS.md, master §22). The remaining slices (02-C, 02-3, 02-4, 02-6) keep their relative order and dependencies; 02-6 Batches still follows 02-5 (master §23).
- **Why it is safe:** 02-5 depends only on 02-2 (master §22). Neither 02-3 nor 02-4 provides anything Finance-lite needs: Finance-lite extends the development seed itself, and it needs neither the outbox nor public capture.

### 2. Non-tax fee invoices (F1)

- MVP invoices are **non-tax fee invoices**. They are **not GST tax invoices**.
- **Excluded:** GST or any other tax calculation, tax lines, GSTIN, SAC/HSN codes, place of supply, tax-invoice numbering rules, credit or debit notes, and e-invoicing.
- **Wording:** every invoice screen and print view carries the label "Fee invoice — not a tax invoice". Screens and code use "fee invoice" wherever a tax invoice could be inferred (INC-48).
- **Production condition:** before the first production tenant uses Finance-lite, the tax treatment of that tenant's fees must be confirmed by an appropriately qualified person. This ADR makes no legal or tax conclusion. If tax invoices are required, a later ADR adds them; Finance-lite must not be presented as GST-compliant.

### 3. Financial-year numbering (F2)

Invoice and receipt numbers follow the **Indian financial year (FY), 1 April – 31 March**. Applications, admissions and students keep ADR-0021 §7 (calendar year, UTC) unchanged (INC-49).

- **Reference instant:** the database transaction timestamp `now()` of the transaction that makes the document final:
  - a fee invoice: its issue;
  - a receipt: the confirmation of its payment.

  The document's stored `issued_at` / `confirmed_at` uses the same `now()`, so the label and the stored date always agree.
- **Time zone:** India Standard Time, `Asia/Kolkata`: UTC+05:30, no daylight saving. Finance-lite is INR-only (§6), so its FY is India's. UTC is not used for this boundary: it would put 00:00–05:29 IST on 1 April into the previous year.
- **Algorithm:**

  ```text
  d     = (now() AT TIME ZONE 'Asia/Kolkata')::date
  start = year(d)       if month(d) >= 4
          year(d) - 1   otherwise
  label = 'FY' || start || '-' || lpad(((start + 1) % 100)::text, 2, '0')
  ```

  Examples: FY2026-27 covers 2026-04-01 00:00:00 IST to 2027-03-31 23:59:59.999999 IST. `2027-03-31T18:29:59Z` is FY2026-27; `2027-03-31T18:30:00Z` (00:00 IST, 1 April) is FY2027-28.
- **Storage:** `tenant_sequences` rows with `name` `INVOICE` or `RECEIPT` and `period` = `start`, the FY's starting calendar year. The existing CHECK `period BETWEEN 2000 AND 9999` holds. The meaning of `period` depends on `name`: calendar year (UTC) for `APPLICATION`, `ADMISSION` and `STUDENT`; FY start year (IST) for `INVOICE` and `RECEIPT`.
- **Format:** `INV-FY2026-27-00001` and `RCT-FY2026-27-00001`. The prefix, then the full FY label, then the counter: five digits, widening past 99 999 and never wrapping. 19 characters, within the 32-character number columns.
- **Series:** the counter starts at 1 each FY, per tenant and per sequence (one series per tenant, not per campus; per-campus series are deferred, as in ADR-0021 §7).
- **Gap-free allocation (unchanged mechanism):** one `INSERT … ON CONFLICT DO UPDATE … RETURNING` in the caller's transaction. The row lock serialises concurrent callers, and a rolled-back transaction rolls the increment back.
  - Numbers are allocated **only** when a document becomes final: an invoice at issue, a receipt at confirmation.
  - Numbers are never reused or deleted. A cancelled invoice and the receipt of a reversed payment keep their numbers, so each series stays continuous.
- **Receipt date basis:** a receipt's FY is that of its **confirmation**, not of the `received_on` date the user enters. For example, a cheque received on 30 March and cleared on 2 April gets a receipt in the new FY, and its `received_on` stays 30 March. This must be confirmed for production together with §2 (INC-49).
- **Allocator location:** the allocator moves to `app.core` so that `finance` does not import `students`. Admissions behaviour is unchanged.

### 4. Payment states; cheque and demand draft (F3)

- Methods: `CASH`, `UPI`, `BANK_TRANSFER`, `CHEQUE`, `DEMAND_DRAFT`.
  - A reference is required for every method except `CASH`.
  - A gateway or card method is not in the MVP: no client-side or provider success is ever trusted (T06-08).
- **`CASH`, `UPI`, `BANK_TRANSFER`:** created `CONFIRMED`. The recording staff member attests that the money was received.
- **`CHEQUE`, `DEMAND_DRAFT`:** created **`PENDING`**. A pending payment does **not** reduce the balance and has **no receipt**.
  - `PENDING → CONFIRMED` after clearance. Only this transition issues the receipt and reduces the balance.
  - `PENDING → FAILED` if the cheque or DD is not honoured. **A reason is required.** No receipt is issued and the balance is unchanged.
- **`CONFIRMED → REVERSED`**, with a reason (§9), restores the balance. The receipt stays, displayed as cancelled. This also covers a cheque that bounces after it was confirmed.
- `FAILED` and `REVERSED` are final. Nothing is deleted.
- Only `CONFIRMED` payments count toward `paid_minor`. The invariant `paid_minor = Σ amount_minor of CONFIRMED payments` is enforced under the invoice row lock and tested.

### 5. Invoice states

- `ISSUED → PARTIALLY_PAID → PAID` follows `paid_minor`; it is never set by hand. A reversal moves the status back down.
- `ISSUED → CANCELLED` requires a reason and no `CONFIRMED` payment. A `PENDING` payment must be resolved (confirmed or failed) first.
- There are no draft invoices. Issue is one command, which is what makes invoice lines insert-only.

### 6. Currency and amounts (F4)

- **INR only.** Every money row stores `currency CHAR(3)` fixed to `'INR'` by a CHECK. The column exists so that widening later needs no data rewrite.
- **Amounts are integer paise** (minor units) in `BIGINT` columns named `*_minor`. No floating-point type is used anywhere.
- **API:** integers in minor units, in both directions.
- **Frontend:** a tested pure function converts typed input (for example `1,25,000.50`) to paise by string handling and refuses more than two decimal places.
- **Totals and balances:** the server computes every total and balance and never accepts one from the client.
- **Constraints:** `amount_minor > 0` for payments, `≥ 0` for invoice lines, and `0 ≤ paid_minor ≤ total_minor` on invoices. Overpayment is refused (no advances or credit in the MVP).

### 7. Adjustments at issue (F5)

- Raising a fee invoice prefills the lines of the course's active fee structure. Line amounts may be adjusted, and lines added, before issue. There are no discount or scholarship entities.
- **What is recorded:**
  - **Invoice:** `fee_structure_id`, `fee_structure_version`, `structure_total_minor` and `total_minor`.
  - **Each line:** `structure_amount_minor` (the structure's value; `NULL` for an added line) and `amount_minor` (the issued value). A structure line left out is kept as a line with `amount_minor = 0`, so the original stays visible.
  - **Adjustment reason (implementation rule derived from this decision):** an invoice whose lines differ from the structure is `adjusted` and requires an `adjustment_reason` (up to 500 characters).
- **Activity and audit:**
  - The `ISSUED` activity records each line's structure and issued amounts.
  - The `invoice.issued` audit event records `total_minor`, `structure_total_minor`, `adjusted` and the number of adjusted lines. It never records the reason text (ADR-0013 metadata rule).
- Lines are insert-only, so an issued invoice cannot be changed. A correction is a cancellation (§8) and a new invoice.

### 8. One live invoice per admission (F6)

- **One live invoice per Admission:** a partial unique index on `(tenant_id, admission_id) WHERE status <> 'CANCELLED'`. Concurrent issues for one admission yield one invoice.
- A cancelled invoice stays in history with its number. Its replacement receives a **new** invoice number (§3).
- Each fee invoice links to **both** the Admission (the billing context: course, campus, admission number) and the Student. One composite foreign key, `(tenant_id, admission_id, student_id, campus_id, course_id) → admissions`, makes the copies impossible to contradict.
- Visibility follows the invoice's campus, which is the admission's campus.

### 9. Reversal: separation of duties (F7)

- The member who recorded a payment **cannot reverse it**. The service refuses with 403 (permission denied) when `recorded_by_membership_id` equals the caller's membership.
- **Unaffected by the rule:**
  - confirming or failing a pending payment, which any holder of `payment.record` in scope may do, including the recorder;
  - reversal by any other holder of `payment.reverse` in scope, including after the recorder has left.
- **Consequence:** an institute with a single finance user cannot reverse that user's payments without a second member who holds `payment.reverse`.

### 10. No step-up for reversal (F8)

- The MVP adds **no** step-up (fresh MFA) requirement to `payment.reverse`, `invoice.cancel` or any finance permission. Tenant MFA is not mandatory, so a step-up would lock out members who have not enrolled.
- **Mandatory on every finance mutation:**
  - the route permission;
  - the service-level campus authorization (`authorize()`);
  - a reason where required (cancel, fail, reverse, adjustment);
  - the optimistic `version` check (409 when stale);
  - the in-transaction domain audit event.
- Step-up for reversal and refunds is revisited with full Finance (master §17).

### 11. Scope carried from the readiness review (unchanged)

The following are as set out in [PHASE-02-5-FINANCE-LITE-READINESS.md](../architecture/PHASE-02-5-FINANCE-LITE-READINESS.md):

- the MVP scope and deferred items;
- the entities, permissions (7 codes; templates `FINANCE_MANAGER`, `FINANCE_OFFICER`) and the 17-route API;
- tenant RLS, composite tenant foreign keys and no DELETE privilege; `invoice_lines`, `receipts` and `finance_activities` insert-only;
- idempotency keys with a request hash, the invoice row lock;
- migration `0011_finance_lite`, the seed extension, the tests and the acceptance criteria.

## Consequences

- An institute can bill an admitted student, record offline payments, issue receipts and follow up outstanding fees, with an immutable, auditable history.
- Financial-year numbering adds a second meaning to `tenant_sequences.period`, documented above and in INC-49.
- **Not production-ready until confirmed:** Finance-lite may be implemented and released for development, review and demonstration, but its production use requires confirmation of:
  - the tenant's tax treatment (§2);
  - the receipt FY date basis (§3).
- Refunds, discounts, scholarships, instalments, the payment gateway, reconciliation, accounting exports, tax invoices and reminders remain deferred to full Finance (Phase 06 tasks) and Communication (02-7).

## Alternatives considered

- **Calendar-year numbering (ADR-0021 convention):** consistent with admissions, but not what institutes' accounts teams use for fee receipts. Rejected (F2).
- **FY boundary in UTC:** reuses the existing clock expression, but misplaces the first 5½ hours of 1 April IST. Rejected.
- **`NUMERIC(14,2)` amounts with decimal strings in the API:** exact as well, but needs `Decimal` handling throughout and string parsing in the browser. Integer paise are simpler and JavaScript-safe. Rejected.
- **Cash, UPI and bank transfer only:** simpler, but cheques and demand drafts are common for institute fees, and treating them as paid on receipt would overstate collections. Rejected (F3).
- **Several live invoices per admission:** needed for hostel or exam fees billed separately, but it opens double billing. Deferred (F6).
- **Step-up for reversal:** stronger, but would block institutes whose staff have not enrolled MFA. Deferred (F8).
