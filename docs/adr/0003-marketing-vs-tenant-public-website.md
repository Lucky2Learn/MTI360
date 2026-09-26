# ADR-0003 — MTI 360 Marketing Website vs Tenant Public Website

- **Status:** Accepted
- **Date:** 2026-09-26
- **Task:** T00-01
- **Related:** CLAUDE.md §4.4; PRD.md §10.4, §60; UI-SCREENS.md PUB-01…06; TASKS.md Phase 14; [spec-inconsistencies.md](../architecture/spec-inconsistencies.md)

## Context

The specifications use "Public Website" for two different things:

- PRD §10.4/§60, CLAUDE.md §4.4 and UI-SCREENS PUB-01 describe a **tenant institute's** public website for prospective students (courses, eligibility, fees, admissions, tenant branding).
- PUB-02 Features, PUB-04 Pricing and PUB-05 Request Demo read like **MTI 360's own** SaaS marketing pages.

The repository root contains `index.html`, `app.js` and `styles.css`: a static marketing website that promotes MTI 360 itself. Its demo-request form is non-functional (it shows a success message without sending data).

## Decision

There are **two distinct concepts** and they must not be mixed:

| | MTI 360 Marketing Website | Tenant Public Website |
|---|---|---|
| Promotes | MTI 360 (the SaaS product) | One Maritime Training Institute |
| Audience | Prospective MTI 360 customers | Prospective students and public visitors |
| Branding | MTI 360 | Tenant-branded |
| Content | Product capabilities, demo requests | Tenant courses, eligibility, fees, admissions, enquiry, content |
| Part of the product's four experiences | **No** | **Yes** (experience 4) |
| Screens | Not in UI-SCREENS.md | PUB-* (Phase 14) |
| Location | Root `index.html`, `app.js`, `styles.css` → later `marketing-site/` | `frontend/src/app/sites/[site]/` via host-based rewrite |
| Tenancy | None | Tenant resolved server-side from a verified domain (ADR-0004) |

Rules for the marketing website:

1. The three root files are **preserved unchanged** during T00-01 and until an explicit task changes them. Their SHA-256 hashes are recorded in `DEVELOPMENT-STATUS.md`.
2. They are a **visual and brand reference only**. No code, CSS or tokens are imported into `frontend/`; application tokens are authored from `DESIGN-SYSTEM.md`.
3. Status: **Prototype: YES — Production Ready: NO** (non-functional demo form; marketing prototype, not the application).
4. A later, separate task relocates them to `marketing-site/` in a **rename-only commit** (after tag `marketing-site-v1`, with checksum verification, and after confirming whether any host deploys from the repository root). Functional fixes are separate tasks.

## Consequences

- The PUB-* screen list in UI-SCREENS.md still mixes both concepts and must be rewritten in a future documentation task; this is recorded in `spec-inconsistencies.md` rather than silently changed.
- Marketing-site work is tracked outside the product phases (proposed `MKT-*` tasks in TASKS.md).
- Tenant public websites share the application's design system and backend public API (`/api/v1/public/*`) but have no access to authenticated APIs.

## Alternatives considered

- **Treat the root landing page as PUB-01** — conflates a SaaS marketing page with a tenant-branded, tenant-scoped website. Rejected.
- **Convert the landing page to Next.js now** — out of scope for T00-01, risks altering an approved design, and couples marketing releases to application releases. Rejected.
- **Delete the landing page** — loses an approved brand reference. Rejected.
