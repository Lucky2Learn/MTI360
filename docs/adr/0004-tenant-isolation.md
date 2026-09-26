# ADR-0004 — Tenant Isolation

- **Status:** Accepted (implementation in Phase 01: T01-05, T01-07, T01-10, T01-12)
- **Date:** 2026-09-26
- **Task:** T00-01
- **Related:** CLAUDE.md §5–§8, §55; ARCHITECTURE.md §8–§9, §33; PLATFORM-ADMIN.md §88–§90; [tenancy.md](../architecture/tenancy.md)

## Context

MTI 360 is a multi-tenant SaaS platform. Cross-tenant data leakage is a critical platform failure (DEVELOPMENT-STATUS RISK-02). ARCHITECTURE.md §8 selects a shared PostgreSQL database with a shared schema and a `tenant_id` column. A single application-level filter is a single point of failure: one forgotten `WHERE` clause leaks data.

## Decision

**Tenant context is derived server-side only.** A `tenant_id` in a request body, query string or header is never used for authorization; tenant-scoped write schemas do not accept `tenant_id`.

Trusted tenant sources:

| Realm | Source |
|---|---|
| Tenant / Student | Server-side session → validated membership → active tenant (and campus) |
| Platform | None by default; only via an active, audited **support session** |
| Tenant Public Website | Request host → verified `tenant_domains` entry |
| Webhooks | Provider channel identifier → tenant channel configuration, after signature verification |
| Background jobs | Server-written job envelope, re-validated in the worker |

**Five enforcement layers (defence in depth):**

1. **Authorization dependency** — realm, permission, tenant status and entitlement checked per request.
2. **Tenant-scoped repositories** — every query filtered by the context tenant; inserts stamped automatically; get-by-id is `id AND tenant_id`; a miss returns **404** (never reveals existence).
3. **Automatic ORM filter** — a SQLAlchemy hook applies the tenant criterion to every tenant-scoped model and **raises** if no tenant context exists, unless inside an explicit, platform-only, audited unscoped block.
4. **PostgreSQL Row-Level Security** — policy `tenant_id = current_setting('app.tenant_id')::uuid`; `SET LOCAL app.tenant_id` per transaction (API and workers); the application role is not the table owner and has no `BYPASSRLS`.
5. **Composite foreign keys** — `UNIQUE (tenant_id, id)` on parents, `(tenant_id, parent_id)` references on children, so the database rejects cross-tenant links.

Additional rules: tenant-prefixed object-storage keys with authorization before presigning; a mandatory tenant namespace in the cache wrapper; tenant-scoped RAG retrieval under RLS; AI tools executing with the caller's context; a read-only RLS-bound role for the SQL/Data Agent; platform analytics read only aggregates.

**Mandatory test gate:** an automated suite proves *Tenant A cannot access Tenant B* for every tenant, student and public route, enforced by a route-coverage test that fails when a route has no cross-tenant test (see tenancy.md).

## Consequences

- Stronger guarantees than an application filter alone; RLS catches bugs in raw SQL, reports and new code paths.
- RLS adds complexity: transaction-scoped settings, connection-pool hygiene, worker context, and migration discipline for policies. These are addressed with dedicated tests in T01-10.
- Every tenant-owned table needs `TenantScopedMixin` and an RLS policy migration.
- Returning 404 for other tenants' resources is required behaviour and must be reflected in API tests.

## Alternatives considered

- **Application-level filtering only** — simplest, but a single missed filter leaks data. Rejected as insufficient on its own.
- **Schema-per-tenant** — strong separation but complex migrations and pooling at scale. Rejected for the initial SaaS.
- **Database-per-tenant** — strongest isolation, highest operational cost. Reserved for possible future enterprise tenants (ARCHITECTURE.md §8).
