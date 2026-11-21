# ADR-0024 — Public Enquiry: Verified Institute Hosts, Consented Leads and the Transactional Outbox

- **Status:** Accepted (design decisions approved by the user, 2026-10-31). Implemented on `feat/platform-tenant-management` (uncommitted); not browser-verified.
- **Date:** 2026-11-01
- **Task:** Phase 02-4 Public Enquiry (V1)
- **Related:** [ADR-0003](0003-marketing-vs-tenant-public-website.md), [ADR-0004](0004-tenant-isolation.md), [ADR-0006](0006-api-prefixes.md), [ADR-0013](0013-audit-events.md), [ADR-0014](0014-tenancy-core.md), [ADR-0020](0020-courses-and-leads.md); [PHASE-02-MASTER-READINESS.md](../architecture/PHASE-02-MASTER-READINESS.md) §15–§16, §22 (L8, L9); [tenancy.md](../architecture/tenancy.md) §2, §8; INC-27, INC-52

## Context

Slice 02-4 lets a prospective student send an enquiry to an institute from a page hosted by MTI 360, and acknowledges it by email. The public realm has no session, so the institute must come from somewhere the visitor cannot choose freely, and a lead must never land in the wrong institute. Email delivery must not decide whether the lead is kept.

## Decisions (approved by the user)

1. **Platform domain `mti360.in`; institute addresses `{slug}.mti360.in`; page `https://{slug}.mti360.in/enquiry`.** The domain is a setting (`PUBLIC_SITE_DOMAIN`, backend and frontend; `localhost` locally).
2. **The institute is resolved only from a verified, platform-issued hostname.** Never from a body, query, path or header the client controls.
3. **PostgreSQL transactional outbox** for the acknowledgement email; a Python worker; Redis only as a wake-up hint. No Celery, RabbitMQ or Kafka (L9).
4. **Two new tables:** institute domains (`tenant_domains`) and the outbox (`outbox_messages`).
5. **Consent is mandatory and versioned.** **Retention: 12 months, configurable.** **Minimal personal data.**

## Implementation decisions

### Institute domains (`tenant_domains`)

- Global table: `hostname` (normalized: lowercase, no port, no trailing dot; DNS-name CHECK) **unique across the platform**, `kind = PLATFORM_SUBDOMAIN` (verified by construction: `verified_at` NOT NULL), `status ACTIVE | INACTIVE`, at most **one active platform address per institute** (partial unique index). Never deleted; deactivated instead, so a hostname stays with its institute.
- Slugs: 3–40 lowercase letters, digits and single hyphens; platform labels (`www`, `api`, `app`, `platform`, `sites`, …) are reserved.
- Row-Level Security: platform and system realms read every row and are the only realms that insert or update; the **public realm reads only `ACTIVE`, verified rows**; a tenant context reads its own rows.
- Issued by `python -m app.cli issue-site --tenant UUID --slug SLUG` (audited `platform.tenant.site_issued`) and by the development seed (`site_slug`; a tagged copy gets `<slug>-<tag>`). A platform screen for addresses is later work.

### Host resolution and spoofing

- The browser calls the same-origin proxy (`/api/v1/*` on the institute host). The Next.js server rebuilds **`X-Forwarded-Host` with exactly one entry from its own request's `Host`**, for `/api/v1/public/*` only; a client-supplied `X-Forwarded-Host` is dropped.
- The API reads `X-Forwarded-Host` (right-most entry) **only when it trusts a proxy** (`TRUSTED_PROXY_HOPS ≥ 1`, the same trust rule as `X-Forwarded-For`, D08); otherwise it uses `Host`. Deployments run the API behind the Next.js server with `TRUSTED_PROXY_HOPS=1`.
- Whatever the host claims, only an exact match on one `ACTIVE`, verified row of an institute in `TRIAL` or `ACTIVE` resolves. **Unknown, inactive, unverified, malformed (IP literals, credentials, paths), ambiguous hosts and institutes in any other status get the same 404**, before the body is read.
- A browser `Origin` naming another site is refused with 403 (`enquiry.origin_rejected` security event). Requests without `Origin` are accepted (not a cross-site browser post).
- The resolved tenant is published through `tenants.scopes.public_site_transaction`, the only place besides provisioning that gives a request context a tenant (`test_platform_administration_boundaries.py`).

### API

- `GET /api/v1/public/enquiry-form` — institute name, its `ACTIVE` courses, consent text and version, privacy notice.
- `POST /api/v1/public/enquiries` — `full_name`, `email` and/or `mobile` (at least one), optional `course_id` and `message` (≤ 1,000), `consent_accepted`, `consent_version`, `website` (spam trap). Unknown fields (`tenant_id`, …) are 422. Body read in chunks and refused with **413 above 16 KiB**, unparsed.
- **202 `{"status": "received"}` for every accepted outcome**: stored, repeated within the duplicate window, or spam trap. The answer never reveals whether a contact is known, here or elsewhere.
- **Rate limits (Redis, fail closed with 503):** per client IP (default 5 / 10 min) and per institute (default 200 / hour); 429 with `Retry-After`. Configurable.
- **Duplicates:** the same email or mobile with the same course at the same institute within `ENQUIRY_DUPLICATE_WINDOW_SECONDS` (default 10 min) is acknowledged but not stored again. Submissions of one contact are serialized with a transaction advisory lock, so concurrent repeats store one lead.
- **Spam trap:** a filled `website` field is answered like success; nothing is stored; `enquiry.discarded` security event.
- **Course:** must be an `ACTIVE` course of the resolved institute; anything else (another institute's course, a draft, an unknown ID) is the same `422 course_not_available`.

### The lead and consent evidence

- A `NEW` lead, `source = WEBSITE`, institute pool (`campus_id` NULL), no owner, **no creator**. `leads.created_by_membership_id` becomes nullable, but a CHECK allows NULL **only for a `WEBSITE` lead with consent evidence**.
- `leads.consent_version` and `leads.consented_at` (set together, CHECK). Version `enquiry-2026-10`; the wording is rebuilt from the version and the retention months recorded in the `CREATED` activity. A submission naming another version is `422 consent_outdated` (stale page).
- The message is the lead's first note (`NOTE` activity, no actor). The `CREATED` activity records `channel = public_enquiry`, the consent version, the retention months and a count of possible duplicates. The `lead.created` audit event (realm `public`, the resolved tenant) carries flags only, never contact data.
- **Retention:** 12 months (`ENQUIRY_RETENTION_MONTHS`), stated in the consent text and the privacy notice. **No deletion job exists yet**: a retention job needs its own approval, design and tests.
- Wording: [docs/legal/enquiry-privacy-notice.md](../legal/enquiry-privacy-notice.md) is a **draft for review, not legal advice or approval**.

### Transactional outbox and worker

- `outbox_messages` (tenant-scoped): `kind`, `idempotency_key` (unique per tenant), `payload` (**identifiers only**), `status PENDING → PROCESSING → SENT | FAILED`, `attempts` / `max_attempts`, `available_at`, `locked_at` / `locked_by`, `last_error` (exception class name only), `sent_at`, `failed_at`. Tenant Row-Level Security plus a system-realm policy for the worker; no DELETE privilege.
- **Atomic:** the lead, its activities, the audit event and the outbox message are one transaction. A failure anywhere stores nothing.
- **Worker** (`python -m app.worker`, `pnpm worker`): claims with `FOR UPDATE SKIP LOCKED` (any number of workers), builds the email from current data in a tenant-scoped system transaction, sends it **outside any transaction**, then settles with an update **fenced on `locked_by` and `locked_at`**: a reclaimed message's late result changes nothing.
- **Retries:** 1, 2, 4 … 60 minutes; `FAILED` after `OUTBOX_MAX_ATTEMPTS` (default 6) or at once for a permanent failure (nothing to send). **A delivery failure never touches the lead.**
- **Stale recovery:** `PROCESSING` older than `OUTBOX_STALE_SECONDS` (default 300) is claimed again, or `FAILED` when no attempt is left. Delivery is therefore **at least once** (a crash between sending and recording can repeat one email).
- **Signalling:** after commit the API pushes a one-token Redis list (`outbox:wake`); the worker waits on it or `OUTBOX_POLL_SECONDS` (default 5). Losing the signal only delays delivery.
- **Logging:** message ID, kind, tenant, attempt and error class; never a recipient, subject or body.

### Hosted page

- `src/proxy.ts` rewrites `/enquiry` on `<slug>.<PUBLIC_SITE_DOMAIN>` to the internal route `/sites/<host>/enquiry` (**resolves INC-27** in favour of repository-structure.md §2). On an institute address **every other page path** (including `/`, `/app`, `/platform`, `/login`) is rewritten to `/sites/<host>/not-found`, so no staff or platform page is served on an institute address. On any other host, `/enquiry` and `/sites/*` get the same route. `/api/*`, Next.js internals and files are not matched.
- **Branded public 404** (approved 2026-11-01): `app/sites/[site]/[...missing]` calls `notFound()` (HTTP 404); `app/sites/[site]/not-found.tsx` asks the API (`GET /public/enquiry-form`, forwarded host) for the institute. Only a verified, active address of a `TRIAL`/`ACTIVE` institute returns a name: the page then shows it and links to `/enquiry`. Anything else (unknown, inactive, unverified host, API unreachable) gets a neutral page that names no institute, has no navigation and no link. No staff or platform navigation in either case. No logo exists in the data model yet (Phase 14 website branding).
- T18 Public Website template through `PublicSiteShell` (new optional footer note). The institute's name is its identity; logos and colours come with the Phase 14 website. UI-SCREENS.md has no enquiry screen (INC-52).

## Consequences

- An institute receives website enquiries only after the platform issues its address.
- Local development of the page needs `PUBLIC_SITE_DOMAIN=localhost` (both sides) and `TRUSTED_PROXY_HOPS=1` for the API, and the worker running for emails (Mailpit).
- Migrations: `0012` (tables, lead consent columns) and `0013` (`outbox_messages` `UNIQUE (tenant_id, id)`, the composite-key convention of every tenant-scoped table; a separate revision because `0012` was already applied to `mti360_test`). Downgrading `0012` is a development operation that loses data: it deletes leads without a creator (public enquiries) with their follow-ups and activities, and refuses while such a lead has an application or is another lead's duplicate target.
- Out of scope: custom domains (DNS verification, TLS), a platform address screen, campaign/UTM capture, WhatsApp and SMS acknowledgements (02-7), the retention job, CAPTCHA.
