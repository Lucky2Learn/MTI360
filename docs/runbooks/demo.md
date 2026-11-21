# Admissions demo (Phase 02-3)

How to load and run the ~10-minute admissions demo described in [PHASE-02-MASTER-READINESS.md §21](../architecture/PHASE-02-MASTER-READINESS.md). The demo uses the development seed (`database/seeds/dev.json`). Konkan Maritime Training Institute plays the role of the "Coastal" institute in §21: Mumbai stands in for Kochi and Ratnagiri for Visakhapatnam.

Development only. The seed refuses to run unless `APP_ENV=development`.

## 1. Load the demo

Prerequisites: `pnpm infra:up` (PostgreSQL, Redis, object storage, Mailpit) and `pnpm db:migrate`.

```bash
pnpm db:seed                 # first copy, on a database without the seed
pnpm db:seed --tag demo2     # another, independent copy (any 1-16 lowercase letters or digits)
```

- **One command.** `pnpm db:seed` runs `python -m app.cli seed` in `backend/`. It prints the institutes and accounts it created, never a password.
- **Repeatable without a reset.** A database that already holds the seed refuses a second untagged run. `--tag demo2` loads the same demo again as new institutes and accounts:
  - institutes are named `Konkan Maritime Training Institute (demo2)`;
  - accounts are named `principal.demo2@konkan-maritime.example`.
  Earlier copies, and any other tenant, are not changed. A tag that was already used is refused. Each copy is an ordinary institute, isolated from the others by the usual tenant boundary. The `system.seed.applied` audit event records the tag.
- **No reset command.** Nothing in the seed deletes data. To start from an empty database, use `pnpm infra:reset`, which deletes every local volume.

## 2. Sign in

Every seeded password is random and never shown. For each account you need, request a reset link from the sign-in page and open it in Mailpit (http://127.0.0.1:18025). Add `.TAG` before the `@` for a tagged copy.

| Account | Person | Role | Campuses |
|---|---|---|---|
| `principal@konkan-maritime.example` | Capt. Anil Deshpande | Institute owner | All |
| `admissions@konkan-maritime.example` | Farah Shaikh | Admissions manager | All |
| `counsellor.mumbai@konkan-maritime.example` | Rohit Naik | Counsellor | Mumbai |
| `counsellor.ratnagiri@konkan-maritime.example` | Priya Joshi | Counsellor | Ratnagiri |
| `director@coromandel-nautical.example` | Capt. Meenakshi Raghavan | Owner, Coromandel Nautical Academy | All |

The seed also creates an administrator, a Ratnagiri-only administrator, a finance manager and a Mumbai finance officer for the Finance-lite screens.

## 3. Walkthrough (§21)

| Step | Who | What to show | Seeded records |
|---|---|---|---|
| 1 | Farah (admissions manager) | **Courses**: GP Rating, Diploma in Nautical Science, STCW Basic Safety Training (active), with a draft and an archived course | `GPR`, `DNS`, `STCW-BST`, `AFF` (draft), `CCMC` (archived) |
| 2 | Rohit (Mumbai counsellor) | New walk-in lead with mobile `+91 90000 10199` → the **duplicate warning** names Imran Shaikh; assign it to Mumbai | Imran Shaikh (NEW) and his recorded duplicate |
| 3 | Rohit | **Pipeline**: move a lead to CONTACTED, then QUALIFIED, with status actions (the 02-1 board has no drag-and-drop). The timeline records each move. Schedule a follow-up | Leads in every status; follow-ups overdue, due within hours and due in the next days (relative to the seed run) |
| 4 | Priya (Ratnagiri counsellor) | **Convert to applicant**: run the wizard from personal details to the declaration, save a draft, resume it and submit | Ananya Iyer (QUALIFIED, DNS, Ratnagiri, no application yet) |
| 5 | Farah | **Documents**: reject the medical certificate ("Medical certificate expired"), re-upload it, then verify it | Riya D'Souza's submitted DNS application, with its medical certificate under review |
| 6 | Farah; then Rohit | **Admission approval**: approve, and an admission number is generated. A counsellor sees no approve button, and the API refuses the request | Sameer Khan's approved GP Rating application (or the one approved in step 5) |
| 7 | Farah | **Student 360**: profile, admission, course, documents, fees and the timeline from enquiry to admission | Admitted students, for example Sandeep Patil (STCW-BST, a walk-in) |
| 8 | Priya; then Capt. Meenakshi | **Campus scope**: Mumbai leads and applications are invisible to Priya. **Tenant isolation**: Coromandel sees none of Konkan's records | Leads and applications on both campuses; Coromandel Nautical Academy |

Leave out: empty module menus (they stay unreleased), dashboards with sample numbers, and AI.

## 4. What is checked automatically

- `backend/tests/unit/test_dev_seed_contract.py` checks that the committed fixture still supports every step above. It also checks that a tag moves every member reference to the tagged accounts, and that invalid tags are refused.
- `backend/tests/integration/test_dev_seed.py` checks the following against PostgreSQL:
  - the seed creates working institutes;
  - a second, tagged copy loads next to an earlier one without changing it;
  - a used tag is refused;
  - the copies are isolated from each other.
- Not automated: running the walkthrough in a browser.

## 5. Verify on a disposable database (never the development database)

The seed was verified on 2026-10-31 against a separate database on the same local PostgreSQL server. The development database, its volume and the shared configuration were left untouched.

1. Create `mti360_seed_verification`. Use the statements of `database/init/02-test-database.sh`, with that name in place of `${POSTGRES_DB}_test`: owner `mti_owner`, `CONNECT` and `TEMPORARY` for `mti_app`, `CONNECT` for `mti_readonly`, and the same default privileges. Run them with `docker compose exec postgres psql …`.
2. In the shell, export `APP_ENV=development` and the three database URLs (`DATABASE_URL`, `MIGRATIONS_DATABASE_URL`, `READONLY_DATABASE_URL`) pointing at `mti360_seed_verification`. Also export `S3_BUCKET=mti360-seed-verification` (create that bucket first) and, if you start an API, `REDIS_URL=…/2`. Process variables override `backend/.env`. Before writing anything, check that the resolved settings name only the disposable database and bucket.
3. Run `pnpm db:migrate`, `pnpm db:seed` and `pnpm db:seed --tag demo2`. Then run the same tag again, `pnpm db:seed` untagged, and invalid tags (`Demo-2`, `../x`, 17 characters).

Results on 2026-10-31:

| Run | Result |
|---|---|
| `pnpm db:seed` | Konkan (2 campuses, 8 members, 6 system roles, 5 courses, 17 leads, 11 applications, 30 documents, 7 students, 7 fee invoices, 6 payments, 4 receipts) and Coromandel (1 campus, 2 members, 2 courses, 3 leads, 1 application, 1 student, 1 invoice, 1 payment, 1 receipt); 9 accounts; no password printed |
| `pnpm db:seed --tag demo2` | `Konkan … (demo2)` and `Coromandel … (demo2)` with the same contents and 9 new `.demo2@` accounts; every table count doubled; the first copy unchanged; `system.seed.applied` records `tag = demo2` |
| `--tag demo2` again, then untagged | Refused (exit 2); every count unchanged |
| `--tag Demo-2`, `../x`, 17 characters | Refused (exit 2) before connecting; nothing written |
| API isolation (21 checks, an API process on the disposable database; sign-in through password reset and Mailpit) | All passed: the two Konkan copies share no lead, application or student; another copy's lead, application and student are 404 for the demo2 owner, its Mumbai counsellor and its Coromandel owner; the original owner gets 404 for a demo2 lead; the demo2 Mumbai counsellor sees no Ratnagiri lead (a Ratnagiri lead is 404); demo2 Coromandel sees only its own 3 leads |

The disposable database and bucket are kept for inspection. Drop them when they are no longer needed: `DROP DATABASE mti360_seed_verification`, and empty and delete the bucket. That is a destructive step, so do it on purpose.

## 6. Business workflow coverage

What a demo can show today, all on seeded data. ✔ means built and passing automated tests; none is browser-verified.

| Operation | Screens | Status |
|---|---|---|
| Institute sign-in | `/login`, `/forgot-password`, `/reset-password`, `/select-institute`, `/select-campus` | ✔ (T01-09A) |
| Campus administration | `/app/administration/campuses` (ADMIN-03/04); users, roles and campus access `/app/administration/users`, `/roles` (ADMIN-05/06/07, roles read-only) | ✔, but **02-C, not yet merged** |
| Course configuration | `/app/academics/courses` (list, detail, new, edit, status) | ✔ (02-1) |
| Lead management | `/app/admissions/leads` (list and board, detail, new, edit; duplicate check; assign; status transitions; follow-ups; notes) | ✔ (02-1). **The board has no drag-and-drop**: status actions instead |
| Application processing | `/app/admissions/applications` (wizard new/edit, submit, review), `/app/admissions/documents` (upload, verify, reject, download) | ✔ (02-2) |
| Student conversion | Admission approval (`admit`, with student match), `/app/admissions/students` and Student 360 | ✔ (02-2) |
| Finance | `/app/finance/fee-structure`, `/invoices` (with print), `/payments` (with receipt), `/outstanding` | ✔ (02-5, merged; its CI and D18 journeys are not recorded) |
| Batches and enrolment | `/app/academics/batches` (ACA-05 list, ACA-07 new/edit, ACA-06 detail: allocate with payment gate and override, transfer, withdraw, close/reopen/cancel); Student 360 Batch | ✔ (02-6, uncommitted; browser-verified 2026-11-20, §8) |
| Dashboards and reporting | Only Finance **Outstanding** (backed by `/finance/summary`) | **Missing:** the executive dashboard (DASH-01, `/app`) and the admissions dashboard (ADM-01, slice 02-8) are `UNRELEASED` placeholders. Leave them out of the demo |

Not available: public enquiry capture (02-4), messaging (02-7), AI. Batches and enrolment (02-6) are seeded (§8) and need a database migrated to `0014`.

## 7. Manual browser checklist (pending)

Not yet performed. Use a seeded copy on a development database. For a demo against the disposable database, run `pnpm dev` with the variables of §5 exported in that shell. Sign in through "Forgot password" and Mailpit.

**Widths and themes:** do every row at 390, 768, 1024 and 1440 px (browser DevTools device toolbar), in Light, then Dark (user menu → Appearance), and once in System with the OS theme switched.

| # | Check | As | Pass when |
|---|---|---|---|
| B1 | Sign in, pick the institute, land in the app | Farah | No error; the shell and navigation load; the mobile drawer opens and closes at 390 |
| B2 | Navigate Courses, Leads, Applications, Documents, Students, Finance, Administration | Farah, then Capt. Anil | Each page loads with data (a skeleton first, never a blank page); no horizontal page scroll at any width; tables scroll or turn into cards at 390 |
| B3 | Courses: open GP Rating; edit and save it, then change it back | Farah | Saved; validation messages readable in both themes |
| B4 | Leads: create a walk-in with `+91 90000 10199` | Rohit | The duplicate warning names Imran Shaikh; the lead is saved on Mumbai |
| B5 | Move a lead to CONTACTED, then QUALIFIED; add a follow-up | Rohit | The timeline shows both moves and the follow-up |
| B6 | Convert Ananya Iyer: wizard to draft, resume, submit | Priya | The application is SUBMITTED; the wizard is usable at 390 |
| B7 | Riya D'Souza's application: reject the medical certificate ("Medical certificate expired"), upload a PDF, verify it | Farah | Statuses change; the reason is shown |
| B8 | Approve Sameer Khan's application, then admit it | Farah | An admission number is shown; the student is created or matched |
| B9 | Open that application as a counsellor | Rohit | No approve or admit button; the URL alone does not allow it (the API refuses) |
| B10 | Student 360 for the new student | Farah | Profile, admission, course, documents and timeline |
| B11 | Finance: issue a fee invoice for the new student, record a cash payment, open the receipt and print views | Meera (finance manager) | Totals and the outstanding amount update; the print view fits A4 |
| B12 | Campus scope: list leads and applications | Priya | No Mumbai records; opening a Mumbai lead's URL shows the not-found or denied page |
| B13 | Tenant isolation: list leads; open a Konkan lead's URL | Capt. Meenakshi (Coromandel) | Only Coromandel data; the Konkan URL shows not-found |
| B14 | Administration: campuses list and edit; users with campus access; owner keeps all campuses | Capt. Anil | ADMIN-03 … 07 behave as in ADR-0023 |
| B15 | Keyboard only through B4 and B6; visible focus in both themes | Any | Every control reachable; dialogs trap focus and close with Esc |

Record the date, the browser, and any failure with its width, theme and screenshot in DEVELOPMENT-STATUS.md §9A (02-3).

## 8. Batches and enrolment (Phase 02-6)

Needs a database at migration `0014`. The seed adds, per institute (`batches`, `allocations` in `database/seeds/dev.json`; `app/seed_batches.py`):

| Batch | Course · campus | State | Students |
|---|---|---|---|
| `STCW-BST-MUM-2612` | STCW-BST · Mumbai | OPEN, 1 of 20 | Sandeep Patil — fees paid (no override) |
| `DNS-MUM-2026-A` | DNS · Mumbai | OPEN, **full** (2 of 2) | Rohan Salvi — override, part paid (₹3,26,500.00 outstanding); Aniket Thakur — override, no fee invoice |
| `GPR-RTN-2026-B` | GPR · Ratnagiri | **CLOSED** (classes started), 1 of 30 | Akash Shetye — override, invoice unpaid |
| `GPR-MUM-2027-A` → `GPR-MUM-2027-B` | GPR · Mumbai | OPEN | Yash Parab — override, then **transferred** to the evening batch |
| `GME-CHE-2027-A` (Coromandel) | GME · Chennai | OPEN, 1 of 40 | Coromandel's admitted student — override, part paid |

Siddharth Kadam (DNS, Ratnagiri; invoice issued, unpaid) and Mohammed Kazi (STCW-BST, Ratnagiri; demand draft failed) stay unallocated for a live demo: create a DNS Ratnagiri batch, allocate Siddharth (the dialog asks for an override reason), transfer him, withdraw him, and show his Student 360.

Repeatable like every seed section: an untagged rerun is refused; `--tag` loads an independent copy; earlier copies are never changed. Dates are relative to the seed run (IST).

### Verification on the disposable database (2026-11-20)

`mti360_seed_verification` migrated `0013 → 0014` (the development database stays at `0011`); `seed --tag batches1` loaded; reruns (`--tag batches1`, untagged) refused with exit 2 and no count changed; the earlier untagged and `demo2` copies unchanged (admission, invoice and batch counts and `updated_at`). Invariants: every batch's seat count equals its active allocations; every `ENROLLED` admission has exactly one active allocation.

Browser: headless Chromium 1243 (Playwright, outside the repository), frontend `next dev :3200` → API `:8200` → the disposable database, Redis db 2, Mailpit; sign-in through password reset. Evidence (81 screenshots, `results.json`, the Playwright script) is kept outside the repository in `D:\workspace\mti360-verification-evidence\2026-11-20-phase-02-6\`.

| Check | Result |
|---|---|
| ACA-07 create (validation, upper-cased code), edit (course, campus, code read-only), capacity below allocations refused | Pass |
| Allocation with payment override (gate shown, reason required, override and outstanding amount in the row); page updates without reload | Pass |
| Full capacity: Allocate disabled with "This batch is full"; the API answers 422 `batch_full` | Pass |
| Close and reopen | Pass |
| Transfer (only other open batches of the same course and campus offered; history keeps "Transferred out") | Pass |
| Withdrawal (reason required; seat freed; admission back to Admitted) | Pass |
| Student 360 batch history (current/ended allocations, override details, batch timeline entries) | Pass |
| Audit: `batch.created`, `.updated`, `.status_changed`, `.student_allocated`, `.payment_overridden`, `.student_transferred`, `.student_withdrawn` — codes, statuses and amounts only | Pass |
| ACA-05, ACA-06, ACA-07 and Student 360 at 390, 768, 1024, 1440 × Light, Dark, System (OS dark and OS light): 64 cells, status 200, theme applied, no page-content overflow, heading present, no console errors | Pass (after the fixes below) |
| Touch targets on ACA-06 at 390 (≥ 40 px) | Pass (after the fix below) |
| Mumbai counsellor and Mumbai finance officer: Mumbai batches only, no actions; Ratnagiri batch → Page not found; `/new` and `/edit` → access denied | Pass |
| Ratnagiri-only administrator: Ratnagiri batches only; Mumbai batch → Page not found | Pass |
| Coromandel owner: own batch only; Konkan batch and Konkan student → Page not found | Pass |

Defects found and fixed: a hydration error on ACA-05/ACA-06 (block elements inside the mobile card's `<p>`); stretched payment badges; 32 px Transfer/Withdraw buttons at 390. Fixed in the release-readiness review (2026-11-20): the shell header overflow at 768 and 1024 px, the truncated mobile payment badge (now "Fee override"), the empty Actions column for read-only roles, and a 39 px overflow from the ACA-06 summary seat label at 1024. The `/login` "404" is the browser's `/favicon.ico` request (no icon asset), not a routing fault. Open, outside 02-6: 02-5 fee badges truncate on Student 360 at 1024.

