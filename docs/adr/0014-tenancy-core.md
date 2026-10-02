# ADR-0014 — Tenancy Core: Tenants, Campuses, Row-Level Security and Trusted Tenant Context

- **Status:** Accepted (T01-03 locked decisions; refines ADR-0004 and the T01-00 decision D15)
- **Date:** 2026-10-02
- **Task:** T01-03
- **Related:** [ADR-0004](0004-tenant-isolation.md), [ADR-0005](0005-identity-and-session-realms.md), [ADR-0011](0011-rbac-model.md), [ADR-0013](0013-audit-events.md), [tenancy.md](../architecture/tenancy.md), [backend-foundation.md](../architecture/backend-foundation.md) §13

## Context

ADR-0004 chose five isolation layers: authorization, tenant-scoped repositories, an automatic ORM filter, PostgreSQL Row-Level Security and composite foreign keys. T01-01 added the trusted `RequestContext` and the `SET LOCAL` publication that RLS reads. T01-02 added the first RLS policies, on `audit_events`.

T01-03 creates the first tenant tables. The T01-03 architecture review (second pass) found points that the specifications leave open or contradict:

- `tenants` is listed as a global table with no RLS (tenancy.md §9). The default privileges, however, give the read-only role SELECT on every table.
- ADR-0004 states a realm-agnostic tenant policy. `audit_events` is realm-aware.
- The status a new tenant starts in is not specified (INC-32).
- The campus code has no stated uniqueness (PLATFORM-ADMIN.md §30).

The user approved the decisions below before implementation.

## Decision

### 1. Tables

| Table | Columns | Notes |
|---|---|---|
| `tenants` (global registry) | `id` (UUIDv7), `name` varchar(200), `status` varchar(16), `created_at`, `updated_at`, `version` | `status` CHECK on the eight lifecycle states, stored upper case. There is no slug, code, profile field or soft delete. The institute profile is a separate 1:1 extension in Phase 03 (INC-34). |
| `campuses` (tenant-owned) | `id`, `tenant_id`, `name` varchar(200), `code` varchar(32), `created_at`, `updated_at`, `version` | `tenant_id` references `tenants(id)` with `ON DELETE RESTRICT`. `UNIQUE (tenant_id, id)` is the composite foreign-key target. The code is required, matches `^[A-Z0-9][A-Z0-9-]*$` (CHECK) and is unique per tenant (`UNIQUE (tenant_id, code)`). There is no address, contact, timezone, status or primary flag yet. |

- Neither table is ever hard-deleted. The runtime roles have no DELETE privilege. Tenants are deactivated, not deleted (PLATFORM-ADMIN.md §38).
- Migration `0003` creates both tables, replaces the default privileges and creates the policies:

  | Role | Privileges |
  |---|---|
  | `mti_app` | SELECT, INSERT, UPDATE |
  | `mti_readonly` | SELECT, restricted by RLS |

- RLS is enabled but not forced. The owner runs migrations only, as in `0002`. The runtime roles stay NOBYPASSRLS.

### 2. Row-Level Security

The trusted values are `nullif(current_setting('app.tenant_id', true), '')::uuid` and `nullif(current_setting('app.realm', true), '')`. Both are published only by `context_transaction` (`SET LOCAL`). An unset value is NULL and matches nothing.

**Tenant-owned tables (the pattern for every later tenant table) are realm-agnostic, as ADR-0004 states:**

| Policy | Command | Role | Rule |
|---|---|---|---|
| `campuses_tenant_isolation` | ALL | `mti_app` | USING and WITH CHECK `tenant_id = trusted tenant` |
| `campuses_readonly_tenant_read` | SELECT | `mti_readonly` | `tenant_id = trusted tenant` |

- Without a trusted tenant, every realm (platform and system included) sees and writes nothing.
- Which realm may use which route is decided by the authorization layer (T01-05).
- A tenant context established later through a support session (Phase 02), a verified host (Phase 14) or a webhook channel (Phase 09) needs no policy change.

**`tenants` (the global registry) is realm-aware, like `audit_events`:**

| Policy | Command | Role | Rule |
|---|---|---|---|
| `tenants_platform_read` | SELECT | `mti_app` | realm is `platform` or `system`: every row |
| `tenants_own_read` | SELECT | `mti_app`, `mti_readonly` | `id = trusted tenant` |
| `tenants_platform_insert` | INSERT | `mti_app` | realm is `platform` or `system` |
| `tenants_platform_update` | UPDATE | `mti_app` | realm is `platform` or `system` |

The tenant, student, public and webhook realms read only their trusted tenant's row and never write.

**Platform access to tenant-owned rows:** none in T01-03. The provisioning write path (tenant, primary campus, roles) is decided by T01-07 (INC-39).

### 3. Trusted tenant context

- **Single source.** The tenant is always the `RequestContext` of the transaction. `context_transaction` publishes it with `SET LOCAL` and also records it in `session.info` (`session_context()`). The ORM filter, the repositories and RLS therefore read the same value. A `tenant_id` from a request body, query, header or frontend state is never used.
- **`RequestContext` keeps its four fields.** Campus scope, permissions and the support session are added by T01-05 and Phase 02.
- **`system_context(sessionmaker, tenant_id=None)`** (`app/core/tenancy/system.py`) handles trusted work outside HTTP: the seed, command-line tools and jobs.
  - It builds `RequestContext(realm=SYSTEM, request_id=<new UUIDv7>, principal_id=None, tenant_id=<the trusted caller's UUID or None>)`.
  - It binds the context with a contextvar token through `context_scope()`, which restores the previous context on exit and on error.
  - It runs the block in one `context_transaction`.
  - It **refuses to run while an HTTP request context is bound**, so a request cannot switch realm, override its tenant or hold a second connection.
  - Nested system contexts restore the outer one.

### 4. Application layers

- **`TenantScopedMixin`** (`app/core/tenancy/mixins.py`) adds the UUIDv7 `id` and `tenant_id NOT NULL` with a foreign key to `tenants` (`ON DELETE RESTRICT`).
  - The table must declare `UNIQUE (tenant_id, id)`; a unit test enforces this for every mapper.
  - `tenant_foreign_key(column, parent)` builds the composite key `(tenant_id, column) → parent(tenant_id, id)`.
- **ORM filter** (`app/core/tenancy/filter.py`) is a `do_orm_execute` listener on every `Session`. It adds `with_loader_criteria(TenantScopedMixin, tenant_id = trusted tenant, include_aliases=True)` to every ORM SELECT, UPDATE and DELETE, including joins, aliases, refreshes and bulk statements.
  - It **fails closed**: a statement on a tenant-scoped entity without a trusted tenant raises `MissingTenantContextError`, and any other ORM statement gets an always-false criterion.
  - Core statements are not rewritten; RLS still applies to them.
  - There is no unscoped escape hatch. It is added by its first platform consumer, with audit (INC-38).
- **`TenantScopedRepository[Model]`** (`app/core/tenancy/repository.py`) offers `select`, `find`, `get`, `list` and `count`, all filtered by the trusted tenant.
  - `get` treats another tenant's row exactly like a missing one (`NotFoundError`, 404).
  - `add` stamps the trusted tenant and raises `TenantMismatchError` for a conflicting one.
  - There is **no delete operation**.

### 5. Tenant status

The pure rules live in `app/modules/tenants/domain.py`.

- **States:** `PROSPECT`, `TRIAL`, `PROVISIONING`, `ACTIVE`, `PAST_DUE`, `SUSPENDED`, `CANCELLED` and `DEACTIVATED`. A new tenant starts in `TRIAL`.
- **Transitions in T01 (D15):**
  - suspend: `TRIAL`, `ACTIVE` or `PAST_DUE` → `SUSPENDED`;
  - reactivate: `SUSPENDED` → `ACTIVE`.

  Any other transition raises `InvalidTenantTransitionError`. The full matrix is defined in T02-05 (INC-32).
- **Access policy:**
  - tenant and student realms: `TRIAL`, `ACTIVE` and `PAST_DUE`;
  - public website: `TRIAL` and `ACTIVE` (INC-37).
- Enforcement is wired in T01-04 (session resolution) and T01-05 (`authorize()` step 3).

### 6. Placement

- `app/core/tenancy/` holds the mechanisms.
- `app/modules/tenants/` holds the `Tenant` model and its lifecycle rules.
- `app/modules/institute/` holds `Campus` (repository-structure.md §3).
- `core` refers to `tenants` by table name only. No import-linter contract changed.

## Consequences

- An isolation bug must defeat three independent layers (repository, ORM filter, RLS). The tests prove each one alone: the ORM filter and the repository are tested as the owner role, which bypasses RLS, and RLS is tested with raw SQL.
- Later tenant tables inherit the pattern: `TenantScopedMixin`, `UNIQUE (tenant_id, id)`, the realm-agnostic policy in their migration, explicit grants without DELETE, and composite foreign keys to tenant-scoped parents.
- No platform principal can read or write tenant-owned rows until support sessions or the T01-07 provisioning path exist.
- T01-04 must add a way for a signed-in user without an active tenant to list the tenants of their memberships, for example a membership-based `tenants` read policy.
- Test rows cannot be deleted by the runtime roles. Tests create their own tenants and never count whole tables.

## Alternatives considered

- **No RLS on `tenants` (tenancy.md §9).** Any tenant-realm bug, raw query or the read-only role could list every institute. Rejected.
- **Realm-aware policies on tenant-owned tables.** Every table's policy would have to be rewritten for support sessions, the public website and webhooks. Realm limits belong to the authorization layer. Rejected.
- **The ORM filter reading the ambient contextvar.** It could disagree with the context the transaction published (as with the security-event flush). Rejected in favour of `session.info`.
- **A tenant slug or code.** No specification defines one, and ADR-0005 rejects tenant slugs in URLs. Rejected.
- **An `unscoped()` block now.** It has no consumer, and RLS would return nothing anyway. Deferred.
