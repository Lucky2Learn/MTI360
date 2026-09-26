# ADR-0006 — API Prefixes

- **Status:** Accepted
- **Date:** 2026-09-26
- **Task:** T00-01
- **Related:** ARCHITECTURE.md §35–§36; PLATFORM-ADMIN.md §91; ADR-0005

## Context

The specifications use conflicting API path conventions:

- ARCHITECTURE.md §35: `/api/v1/leads`, `/api/v1/applications/{id}`, …
- PLATFORM-ADMIN.md §91: `/platform/api/tenants`, … and `/api/tenant/*`, while noting "exact implementation must follow ARCHITECTURE.md".

Each realm (ADR-0005) needs a distinct, easily enforced API surface.

## Decision

| Realm | Prefix | Tenant source | Principal |
|---|---|---|---|
| Platform | `/api/v1/platform/*` | none, or active support session | platform user |
| Tenant | `/api/v1/*` | session | tenant user (or platform user in a support session) |
| Student | `/api/v1/student/*` | session | student |
| Public (tenant website) | `/api/v1/public/*` | verified request host | anonymous |
| Webhooks | `/api/v1/webhooks/*` | provider channel mapping after signature verification | provider |

Rules:

1. Each router is mounted with a **realm dependency** that rejects any principal from another realm before handlers run.
2. Tenant routes keep ARCHITECTURE.md §35's examples unchanged (`/api/v1/leads`, …).
3. All realms use the ARCHITECTURE.md §36 response envelope (`{data, meta}` / `{error: {code, message, details}}`) with no internal details in errors.
4. Business transitions are explicit endpoints (`POST /api/v1/applications/{id}/approve`), per ARCHITECTURE.md §64.
5. The browser reaches the API through the Next.js same-origin proxy so cookies stay first-party.

## Consequences

- PLATFORM-ADMIN.md §91 paths are superseded by this ADR; the difference is recorded in `spec-inconsistencies.md` for a future documentation update.
- Realm checks can be applied per router rather than per handler, reducing the chance of an unprotected endpoint.
- The route-coverage tenancy test (ADR-0004) can classify routes by prefix.

## Alternatives considered

- **PLATFORM-ADMIN.md §91 style (`/platform/api/*`, `/api/tenant/*`)** — breaks the single `/api/v1` version root from ARCHITECTURE.md. Rejected.
- **Explicit `/api/v1/tenant/*` prefix** — symmetric, but changes every ARCHITECTURE.md example. Rejected.
- **One undifferentiated `/api/v1/*` surface with per-handler checks** — easy to miss a check on a new handler. Rejected.
