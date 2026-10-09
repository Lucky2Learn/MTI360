# ADR-0021 — Admissions Core: Applications, Documents, Admission and Students (Phase 02-2)

- **Status:** Accepted (Phase 02-2)
- **Date:** 2026-10-09
- **Task:** Phase 02-2 Applications → Documents → Admission → Student
- **Related:** [PHASE-02-MASTER-READINESS.md](../architecture/PHASE-02-MASTER-READINESS.md) (locked decisions L2–L7, §10–§14, §19), [ADR-0020](0020-courses-and-leads.md) (courses, leads and the shared helpers this slice reuses), [ADR-0004](0004-tenant-isolation.md), [ADR-0013](0013-audit-events.md), [ADR-0016](0016-authorization-rbac.md), [security.md](../architecture/security.md)

## Context

Phase 02-1 delivered the course catalogue and lead management. The master readiness review locked the rest of the Admissions MVP: no separate Applicant entity (L2), admission approval creates the Admission and the Student without a payment gate (L3), staff-assisted applications only (L4), private document storage with PDF/JPEG/PNG up to 10 MB and malware scanning deferred under compensating controls (L5), a required campus on applications, admissions and students (L6), and `admission.approve` without step-up (L7). The 02-2 readiness assessment (2026-10-09, reported in the implementation session; no separate document) turned these into a scope and eleven implementation choices (Y1–Y11), recorded here. Phase 02-2 is implemented on the same branch as 02-1 (`feat/phase-02-1-courses-leads`), after a re-verified 02-1 baseline at `ab02e7d`.

## Decision

### 1. Modules and boundaries

- `applications` — the application (the applicant's details as entered, per course), its lifecycle, review and the admit command; `application_activities`.
- `documents` — `stored_files` (object-storage metadata) and `application_documents`, the upload validation pipeline, download and verification.
- `students` — `students`, `admissions` and the per-tenant number sequences.
- `app/integrations/storage` — the `ObjectStorage` protocol, the S3 adapter (boto3) and an in-memory fake for tests.
- The lead module gains two system transitions (§10). No other 02-1 behaviour changes.

### 2. Person model (L2)

- **No Applicant entity.** An application holds the applicant's details as entered. A **Student** is created or linked only when an admission is approved, and is the person across courses (a Post-Sea student returns for refreshers).
- **Y6 — explicit linking.** The approver sees the students they may read whose mobile key or normalised email matches the application, and must choose **"link to this student"** or **"create a new student"**. The server never links automatically, so two people who share a family phone are never merged. A student outside the approver's campuses is not offered (and not disclosed); a duplicate person across campuses is an accepted MVP limitation.

### 3. Application (APP-FLOW §16; Y1, Y2, Y11)

- Created from a lead (`lead_id`, the lead's details prefilled server-side for fields the request leaves out) or directly, by a holder of `application.create`.
- **Y1:** course and campus are chosen at creation (prefilled from the lead) and are required; both can change only while the application is `DRAFT` or `CORRECTION_REQUIRED`. Only `ACTIVE` courses can be chosen; the campus must be one of the caller's (unknown and inaccessible campuses are the same 422).
- One open application per lead and course: a second one for the same lead and course is refused unless the earlier one was rejected or found not eligible.
- **Y11:** the owner is the lead's owner (when the lead has one), otherwise the creator. Reassignment is deferred.
- Sections (APP-FLOW §16): personal (name, date of birth), contact (mobile and/or email, address, city, state, postal code), education (highest qualification, details), maritime identifiers (INDoS and CDC numbers, optional), eligibility notes, and a **declaration** that staff confirm on the applicant's behalf (who and when are recorded). Submission requires name, date of birth, a contact, the highest qualification and the declaration.
- A human reference `APP-<year>-<nnnnn>` from the tenant sequence (§7).

### 4. Application statuses (Y2; INC-47)

```text
DRAFT ──submit──► SUBMITTED ──► UNDER_REVIEW ──► APPROVED ──admit──► ADMITTED
  ▲                   │               │
  └──resubmit── CORRECTION_REQUIRED ◄─┤ (reason)
                      REJECTED ◄──────┤ (reason)
                      NOT_ELIGIBLE ◄──┘ (reason)
```

- `submit` (`application.update`): `DRAFT` or `CORRECTION_REQUIRED` → `SUBMITTED`; current documents still `UPLOADED` enter verification (`UNDER_REVIEW`).
- `review` (`application.review`): from `SUBMITTED` → `UNDER_REVIEW`, `APPROVED`, `CORRECTION_REQUIRED`, `REJECTED` or `NOT_ELIGIBLE`; from `UNDER_REVIEW` → the same except itself. Closing and correction decisions need a reason. **`APPROVED` is refused while any current document is not `VERIFIED`** (Y4: no per-course checklist, so zero documents is allowed).
- `admit` (`admission.approve`): `APPROVED` → `ADMITTED` (§6).
- `REJECTED`, `NOT_ELIGIBLE` and `ADMITTED` are final. There is no withdrawal status (not in any specification).
- `DOCUMENT_VERIFICATION` and `ELIGIBLE` (APP-FLOW §16) are **reserved** in the status CHECK and not used: verification is tracked per document, and eligibility is part of the review decision. Recorded as INC-47.

### 5. Documents (PRD §39; L5; Y3, Y4, Y8)

- **Y4:** document types are a fixed list: `PASSPORT`, `CDC`, `INDOS`, `MARKSHEET_10`, `MARKSHEET_12`, `MEDICAL_CERTIFICATE`, `PHOTO`, `ID_PROOF`, `OTHER`. No per-course checklist (deferred).
- **Y3:** statuses `UPLOADED` (on a draft or an application returned for correction) → `UNDER_REVIEW` (on submission, or immediately when uploaded to a submitted application) → `VERIFIED` or `REJECTED` (reason required; `document.verify`).
- **Replacement, never deletion:** a re-upload is a new row that names the document it replaces; the old row is marked replaced and stays in the history. A `VERIFIED` document cannot be replaced. Uploads are accepted while the application is `DRAFT`, `SUBMITTED`, `UNDER_REVIEW` or `CORRECTION_REQUIRED`.
- **Y8:** downloads are always attachments; there is no inline preview.

### 6. Admission and student (L3, L6)

- `admit` creates one **Admission** per application (`UNIQUE (tenant_id, application_id)`, so a repeated or concurrent admit cannot create two), with an `ADM-<year>-<nnnnn>` number, the course and campus of the application, and the approver.
- It creates a **Student** (`STU-<year>-<nnnnn>`, home campus = the admission's campus, details copied from the application) or links the chosen existing student (§2).
- It moves the application to `ADMITTED` and the lead (if any) to `ADMITTED` (§10), and records activity and audit, in one transaction.
- No payment, fee plan, batch or enrolment (L3). Admission status is `ADMITTED` only; `ENROLLED` and `CANCELLED` come with later slices.
- **Student visibility (L6, MVP):** by **home campus**. Visibility through later admissions at other campuses is P1.

### 7. Numbers (Y5)

- One row per tenant, sequence (`APPLICATION`, `ADMISSION`, `STUDENT`) and year in `tenant_sequences`, incremented with `INSERT … ON CONFLICT DO UPDATE … RETURNING` in the caller's transaction. Concurrent callers serialise on the row lock; a rolled-back transaction rolls the increment back, so numbers have no gaps.
- Format `<PREFIX>-<YYYY>-<nnnnn>` (five digits, wider when exceeded), the year taken from the database clock in UTC (campus time zones are not modelled: INC-40). Per-campus and configurable formats are deferred.

### 8. Storage and document security (L5; ARCHITECTURE §7, §49; PRD §66)

- **Upload through the API only** (`multipart/form-data`, one file). The pipeline, in order:
  1. the request body is read in chunks and refused with **413 as soon as it exceeds** 10 MiB plus 64 KiB of form overhead, whatever `Content-Length` says;
  2. the file part must be 1 byte to **10 MiB**;
  3. the file name is sanitised (path components, control characters and unsafe characters removed; at most 120 characters) and kept for display only;
  4. the extension must be `.pdf`, `.jpg`/`.jpeg` or `.png`; the declared MIME type must be `application/pdf`, `image/jpeg` or `image/png`; and the **leading bytes (magic number)** must agree with both;
  5. a PDF is refused when it is encrypted or contains active content (`/JavaScript`, `/JS`, `/Launch`, `/EmbeddedFile`, `/RichMedia`, `/XFA`, `/SubmitForm`, `/ImportData`, `/GoToE`), also inside Flate-compressed streams (bounded decompression) and with `#xx`-escaped names;
  6. the object key is generated by the server: `tenants/<tenant_id>/files/<file_id>`. A database CHECK ties the key to the row's tenant and ID; the client never supplies a key, path or bucket;
  7. the bytes are stored in the private bucket, then the `stored_files` row (name, type, size, SHA-256, uploader) and the document row are written.
- **Download** (`document.read`) authorizes the document through its application's campus, then streams the bytes through the API with `Content-Disposition: attachment`, the stored content type, `X-Content-Type-Options: nosniff`, `Content-Security-Policy: default-src 'none'; sandbox` and `Cache-Control: no-store`. There are no presigned or public URLs; object storage is never reachable from the browser.
- **Failure handling:** a storage error is a 503 and nothing is written to the database. When the database work fails after the object was stored, the object is deleted (best effort). A failure of the commit itself can leave an orphan object (private, unreferenced, under the tenant prefix); a reconciliation job is deferred.
- **Rate limit:** 30 uploads per member per 10 minutes (Redis; fail closed).
- **Malware scanning is deferred (L5) — explicit risk acceptance.** Compensating controls: the type allow-list with magic-number agreement; PDF active-content and encryption refusal; the size limit; generated keys in a private bucket; attachment-only downloads with `nosniff` and a sandbox CSP; authorization on every download; tenant prefixes and RLS on metadata; audit of uploads and decisions. Residual risk: a malicious file of an allowed type (for example an exploit against a PDF or image viewer on a staff workstation) is stored and can be downloaded by authorized staff. Revisit before onboarding the first production tenant; the `ObjectStorage` boundary is where a scanner (for example a ClamAV sidecar or a provider service) plugs in.
- Images are not re-encoded (that would need an imaging library); PDFs are not sanitised, only refused when active content is detected. Both are recorded residual risks.
- Production object storage must use an `https` endpoint (already enforced by settings) and bucket-level encryption at rest (an infrastructure requirement, not enforced by code).

### 9. Dependencies (CLAUDE §74; Y9)

- `boto3` (S3 client; with botocore, s3transfer, jmespath, python-dateutil, six, urllib3) and `python-multipart` (the parser Starlette uses for form data). Both resolved under the 7-day cooldown, `pip-audit` clean. boto3 is synchronous: calls run in a worker thread. It has no type information: mypy ignores its imports only, and the adapter is typed by the `ObjectStorage` protocol.
- Still no TanStack Query, Zod or OpenAPI type generator (ADR-0020 §13 D-1 applies unchanged).

### 10. Lead integration (02-1 compatibility)

- `mark_application_started()` records a new lead activity `APPLICATION_STARTED` (application ID and number) for every application started from a lead. It moves an open lead to `APPLICATION`; a lead already in `APPLICATION` or `ADMITTED` (a second application, for another course) keeps its status; a closed lead is refused (reopen it first).
- `mark_admitted()` moves an `APPLICATION` lead to `ADMITTED` when one of its applications is admitted; an `ADMITTED` lead is unchanged.
- Migration `0010` widens the `lead_activities.kind` CHECK by `APPLICATION_STARTED`. Nothing else about leads changes.

### 11. Permissions and roles (master §13; L7)

| Code | Scope | Admissions manager | Counsellor |
|---|---|---|---|
| `application.read` | campus | ✓ | ✓ |
| `application.create` | campus | ✓ | ✓ |
| `application.update` | campus | ✓ | ✓ |
| `application.review` | campus | ✓ | — |
| `document.read` | campus | ✓ | ✓ |
| `document.upload` | campus | ✓ | ✓ |
| `document.verify` | campus | ✓ | — |
| `admission.approve` | campus | ✓ | — |
| `student.read` | campus | ✓ | ✓ |

- Owner and Admin clones gain all nine (their templates are "everything" / "everything but `role.delete`"). A document verifier is a custom role (T01-08).
- `admission.approve` has no step-up (L7). Every route requires exactly one permission; resource checks use `authorize()` with the application's (or the student's home) campus.
- The Student 360 timeline shows lead activity only to holders of `lead.read` and application activity only to holders of `application.read`.

### 12. Activity and audit

- `application_activities` (append-only, like `lead_activities`): `CREATED`, `UPDATED` (field names), `SUBMITTED`, `STATUS_CHANGED` (from, to, reason), `DOCUMENT_UPLOADED`, `DOCUMENT_VERIFIED`, `DOCUMENT_REJECTED` (type, reason), `ADMITTED` (admission and student numbers, whether the student was created or linked).
- The Student 360 timeline is a read-time union of the source leads' and the applications' activity (no student activity table).
- `domain` audit events: `application.created`, `application.updated` (changed field names), `application.submitted`, `application.status_changed` (from, to, has_reason), `document.uploaded` (type, content type, size), `document.verified`, `document.rejected` (type, has_reason), `admission.approved` (student created or linked), `student.created`. Metadata never contains names, contact details, identifiers, file names, reasons or file contents.

### 13. Database (migration `0010_admissions_core`)

- Tables `tenant_sequences`, `stored_files`, `applications`, `application_documents`, `application_activities`, `students`, `admissions`; the 0009 conventions: `UNIQUE (tenant_id, id)`, composite tenant foreign keys, realm-agnostic tenant RLS, no DELETE privilege; `stored_files` and `application_activities` are SELECT/INSERT only; **no `mti_readonly` grant** on any of them (personal data and documents).
- The nine permissions, the Owner/Admin and Admissions-manager/Counsellor grants, and updated descriptions of the two 02-1 templates (the protection triggers are suspended for that one statement, as the owner).

### 14. Frontend

- Routes: `/app/admissions/applications` (ADM-05), `/applications/new` (ADM-07 start: lead, course, campus), `/applications/[id]/edit` (ADM-07 wizard: personal, contact, education, declaration, review and submit; resumable), `/applications/[id]` (ADM-06 with ADM-08 review, ADM-09 document actions and ADM-10 admission as dialogs), `/app/admissions/documents` (ADM-09 queue), `/app/admissions/students` (ADM-11) and `/students/[id]` (ADM-12 with ADM-13 admissions and ADM-14 documents as sections; modules that do not exist yet show intentional empty states).
- A **T05 Wizard** template joins T02/T03 and the form layout.
- The API client sends `FormData` without a JSON content type. The same-origin proxy caps request bodies at 11 MiB (413 before forwarding) and passes `Content-Disposition`, `Content-Length` and `Content-Security-Policy` through for downloads (Y10).

## Consequences

- An institute can run its admissions desk end to end: enquiry → application → documents → review → admission → student.
- Finance-lite, batches, enrolment, applicant self-service, communication and AI build on these records without changing them.
- The deferred malware scan, the orphan-object reconciliation, cross-campus student visibility and per-course document checklists are open, recorded items.

## Alternatives considered

- **Presigned download URLs:** fewer bytes through the API, but the URL is a bearer credential, needs storage reachable from browsers and CORS, and bypasses per-request authorization. Rejected for the MVP.
- **A raw-body upload without multipart:** avoids `python-multipart`, but the file name and type would travel in headers or the URL (personal data in URLs). Rejected.
- **Automatic student matching:** rejected (§2): a shared family phone would merge two people.
- **An Applicant entity:** rejected by L2.
