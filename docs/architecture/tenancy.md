# Multi-Tenancy Architecture

- **Status:** Approved design (T00-01). Implementation: Phase 01 (T01-01 context plumbing, T01-03 tenancy core, T01-04 session tenant, T01-05 authorization, T01-10 isolation gate; task IDs re-baselined, INC-31).
- **Decision:** [ADR-0004 — Tenant Isolation](../adr/0004-tenant-isolation.md), refined by [ADR-0014 — Tenancy Core](../adr/0014-tenancy-core.md)
- **Related:** [ADR-0005](../adr/0005-identity-and-session-realms.md), [ADR-0006](../adr/0006-api-prefixes.md), CLAUDE.md §5–§8, §55

Implemented so far (T01-01): the request context (§3; realm, request ID, principal and tenant fields) bound by deny-by-default realm guards, and the transaction-scoped `SET LOCAL app.tenant_id / app.user_id / app.realm` publication that RLS policies will read ([backend-foundation.md](backend-foundation.md) §3, §6). Implemented in T01-03 ([ADR-0014](../adr/0014-tenancy-core.md), [backend-foundation.md](backend-foundation.md) §13): `tenants` and `campuses`, `TenantScopedMixin`, the tenant-scoped repository, the automatic ORM filter, Row-Level Security on both tables, the composite foreign-key helper, `system_context` and the tenant status access policy (layers 2–5 of §4). Session-based tenant resolution (T01-04), the authorization dependency (T01-05) and the route-level isolation gate (T01-10) follow.

## 1. Model

```text
MTI 360 Platform
    ↓
Tenant (Maritime Training Institute)
    ↓
Campus
    ↓
Users / Students / Operations
```

Initial strategy: **one PostgreSQL database, shared schema, `tenant_id` on every tenant-owned table** (ARCHITECTURE.md §8).

## 2. Tenant identification

The only trusted sources of tenant identity:

| Realm | Source of `tenant_id` |
|---|---|
| Tenant / Student | Server-side session: authenticated principal → validated membership → active tenant and campus stored in the session |
| Platform | None by default. Available only through an active support session record |
| Tenant Public Website | Request `Host` → `tenant_domains` (verified domains only) → tenant with status `ACTIVE` or `TRIAL` |
| Webhooks | Provider channel identifier (e.g. WhatsApp phone-number ID, payment merchant ID) → tenant channel configuration, **after** signature verification |
| Background jobs | Server-written job envelope, re-validated in the worker (tenant exists and status permits the work) |
| System (seed, CLI, jobs) | The trusted caller of `system_context(sessionmaker, tenant_id=…)` (T01-03); refused inside an HTTP request |

A `tenant_id` from a request body, query string or header is **never** used for authorization. Tenant-scoped write schemas do not contain `tenant_id`.

## 3. Request context

A FastAPI dependency builds a `RequestContext` once per request and stores it in a context variable:

Implemented fields (T01-01): `realm`, `request_id`, `principal_id`, `tenant_id`. The others are added by the tasks that establish them: campus scope and permissions in T01-05, the support session in Phase 02; `correlation_id` is the existing `request_id` (INC-35). The realm of background jobs is `system`.

```text
realm                 platform | tenant | student | public | webhook | job
principal_id
tenant_id             resolved per §2
campus_scope          ALL | [campus_id, …]
permissions
support_session_id    when acting inside a support session
support_mode          read_only | limited_write
correlation_id
```

## 4. Enforcement layers

1. **Authorization dependency** — `require_permission("lead.read")` checks realm, permission, tenant status and feature entitlement.
2. **`TenantScopedRepository`** — every query filtered by `context.tenant_id`; inserts stamped automatically; get-by-id is `WHERE id = :id AND tenant_id = :ctx`; a miss returns **404**, not 403.
3. **Automatic ORM filter** — a SQLAlchemy `do_orm_execute` hook applies `with_loader_criteria` to every `TenantScoped` model; a query without tenant context **raises**, except inside an explicit, named, platform-only, audited `unscoped()` block. T01-03 implements the filter (SELECT, UPDATE and DELETE, aliases and joins, tenant read from `session.info`) with no `unscoped()` block yet (INC-38).
4. **PostgreSQL Row-Level Security** — policy `tenant_id = current_setting('app.tenant_id')::uuid` on each tenant table (implemented as `nullif(current_setting('app.tenant_id', true), '')::uuid`, so an unset setting matches nothing; the first policies are on `audit_events`, T01-02); `SET LOCAL app.tenant_id` in every transaction (API and workers); the application role is not the table owner and has no `BYPASSRLS`. Tenant-owned tables use one realm-agnostic policy for every command (USING and WITH CHECK), for `mti_app`, and a SELECT policy for `mti_readonly`; `tenants` is realm-aware (ADR-0014 §2).
5. **Composite foreign keys** — parents have `UNIQUE (tenant_id, id)`; children reference `(tenant_id, parent_id)`.

## 5. Campus context

Campus-aware entities carry `campus_id`. Repositories apply `campus_id IN context.campus_scope` unless the principal has tenant-wide scope. Campus switching is a server-validated session update. Reporting supports tenant-wide, campus-level and permitted cross-campus aggregation (PRD.md §12).

Session campus semantics (T01-04 decision D04, locked; [identity-authentication.md](identity-authentication.md) §2):

- A membership's permitted campuses are every campus of its tenant (`ALL`) or its `membership_campuses` rows (`SELECTED`).
- For `ALL`, an active campus of `NULL` means all campuses, and no campus step is required.
- Exactly one permitted campus is selected automatically.
- `SELECTED` with two or more permitted campuses requires a choice, and never uses `NULL`. Until a campus is chosen, the session reaches only the session routes.
- `SELECTED` with no permitted campus makes the membership unusable.
- Options come only from the server and never include another tenant's campus. A value outside them returns `404`.
- A switch applies from the next request; the current request context never changes.

## 6. Other surfaces

| Surface | Rule |
|---|---|
| Object storage | Private bucket. Keys `tenants/{tenant_id}/{module}/{uuid}`; the client filename is never part of the key. Upload/download via an authorized API issuing short-lived presigned URLs. The storage wrapper rejects keys outside the context tenant prefix. |
| Cache / rate limits | Only the `core/cache` wrapper touches Redis; it prefixes `t:{tenant_id}:` automatically. Raw client use is lint-banned. |
| Audit logs | `audit_events` (T01-02, [ADR-0013](../adr/0013-audit-events.md)): `tenant_id` nullable (null = platform, system or pre-authentication event) with no foreign key; rows carry `realm` (`support_session_id` is added with support sessions in Phase 02). Append-only: the application role has INSERT/SELECT only, the read-only role has no access, and triggers reject UPDATE/DELETE/TRUNCATE. RLS: tenants read only their own rows, the platform realm reads all, and inserts must match the trusted tenant and realm. |
| AI / RAG | Knowledge chunks and embeddings carry `tenant_id` under RLS; retrieval filters by tenant and publication state. Tools run **as the invoking principal**. |
| SQL / Data Agent | Read-only database role, RLS, allow-listed views, statement timeout, row limit (ARCHITECTURE.md §24). |
| Analytics | Tenant analytics run under RLS. Platform analytics read only aggregated usage/metrics tables. |
| Exports / reports / search | Same repositories and RLS as list endpoints; covered by the isolation test gate. |
| Public website | Only published tenant content via `/api/v1/public/*`; enquiry capture creates leads in the host-resolved tenant; any body `tenant_id` is rejected. |
| Support sessions | Explicit start (tenant, reason, mode, expiry) → separate support context → effective permissions = mode allow-list ∩ operator's platform role → every request audited with `support_session_id` → visible banner from server state → ends on exit, expiry or revocation. |

## 7. Cross-tenant leakage vectors

| Vector | Control |
|---|---|
| ID enumeration on detail endpoints | Tenant-filtered get-by-id → 404; UUIDs, no sequential IDs exposed |
| Forgotten `WHERE tenant_id` | ORM auto-filter (raises without context) + RLS |
| Raw SQL / reporting queries | RLS on app and read-only roles |
| List / search / export endpoints | Repository filter + RLS + route-coverage test |
| Cross-tenant foreign-key linking | Composite foreign keys |
| Background job with wrong or missing tenant | Envelope re-validation; `SET LOCAL` in worker; job without context fails |
| Cache key collision | Mandatory tenant namespace in the cache wrapper |
| Presigned URL sharing / object key guessing | Private bucket, short TTL, UUID keys, authorization before signing |
| RAG retrieving another tenant's documents | Tenant filter + RLS on embeddings |
| AI tool privilege escalation | Tools execute with caller context; registry declares permission and scope |
| Webhook spoofing into a tenant | Signature verification before channel → tenant resolution |
| Public-site `Host` spoofing | Only verified domains map to tenants; unknown host → 404 |
| Platform staff browsing tenant data | No tenant context without an audited support session |
| Connection-pool context bleed | `SET LOCAL` (transaction-scoped), reset on checkout, context variable reset per request |
| Logs / errors containing tenant data | Structured logs with redaction; error envelope without internals |

## 8. Tenant isolation test gate

The automated suite must prove **Tenant A cannot access Tenant B**. It is a mandatory CI gate.

- **Fixture world:** Tenants A and B, each with two campuses, users per role and sample records per module; one platform administrator; one student per tenant.
- **Route-coverage meta-test:** enumerates every route registered on the FastAPI application and **fails if any tenant, student or public route has no cross-tenant test case** or documented exemption.
- **Per-route assertions:**
  - A's session → B's resource ID on GET / PATCH / DELETE / state transitions → **404**.
  - A's list, search and export results contain **zero** B rows.
  - A create containing `tenant_id = B` in the body is rejected (unknown field); nothing is written to B.
- **Realm assertions:** tenant session on `/api/v1/platform/*` → 401/403; platform session on tenant routes without a support session → denied; read-only support session attempting a write → 403 and audited.
- **Layer assertions:** ORM query without context raises; raw SQL as the application role with `app.tenant_id = A` sees no B rows; composite FK rejects a cross-tenant link; a job for A cannot read B; the storage wrapper rejects B's prefix; a cache key without a tenant prefix cannot be built; RAG retrieval for A returns no B chunks; an AI tool invoked by A cannot touch B.
- **Campus assertions:** a campus-scoped user cannot see another campus's records in the same tenant.
- **End-to-end layer** (`tests/e2e/`): signed in as A, navigating to B's resource URL shows a not-found / denied state.

## 9. Database conventions supporting isolation

| Convention | Rule |
|---|---|
| Primary keys | Application-generated **UUIDv7**; sequential IDs never exposed; human-facing numbers (e.g. admission number) are separate per-tenant sequences |
| `TimestampMixin` | `created_at`, `updated_at` (`timestamptz`, UTC) — all tables |
| `ActorMixin` | `created_by`, `updated_by` — business tables |
| `TenantScopedMixin` | `tenant_id NOT NULL`, `UNIQUE (tenant_id, id)`, RLS policy — every tenant-owned table (`app/core/tenancy/mixins.py`, T01-03; the table declares the unique constraint, a unit test enforces it; `tenant_foreign_key()` builds composite foreign keys) |
| `CampusScopedMixin` | `campus_id` — campus-aware entities |
| `SoftDeleteMixin` | `deleted_at` — business records that need history; **not** audit logs (never deleted) or financial records (reversed, not deleted) |
| `VersionedMixin` | `version` (optimistic locking; stale edit → 409) — concurrently edited aggregates such as applications, students, invoices, fee structures, workflows |
| Indexes | Tenant-table indexes lead with `tenant_id`; uniqueness is per tenant and partial `WHERE deleted_at IS NULL` where soft delete applies; FK columns indexed |
| Foreign keys | Always declared; composite within the tenant boundary; `ON DELETE RESTRICT` by default |
| Status fields | `text` + CHECK constraints; transitions enforced in `domain.py` |
| Migrations | Alembic in `backend/migrations/`; one linear history; autogenerated output always reviewed; RLS policies, roles and grants in migrations or `database/init` |
| Global tables (platform services) | `tenants`, `tenant_domains`, `plans`, `features`, `plan_features`, `platform_users`, `platform_roles`, `support_sessions`, `feature_flags`. `tenants` has realm-aware RLS (ADR-0014 §2, INC-36): platform and system read all and write; any other context reads only its trusted tenant's row. Each other global table decides its policy when it is created. |
| Database roles | `mti_owner` (migrations), `mti_app` (DML, RLS applies), `mti_readonly` (SELECT, RLS applies) |
