# Authorization and RBAC

- **Status:** Implemented in T01-05 ([ADR-0016](../adr/0016-authorization-rbac.md); model: [ADR-0011](../adr/0011-rbac-model.md)). Platform user roles: T01-06. Role administration API: T01-08. Frontend: T01-09 ([UI contract](../ui/T01-05-AUTHORIZATION-RBAC-UI.md)).
- **Locked decisions:** D-B1 (campus semantics), D-B2 (system roles immutable), D-B3 (permission identity and the T01 baseline), D-B4 (migration-only sync).

## 1. Permission catalogue (T01 baseline)

| Realm | Code | Scope | Module |
|---|---|---|---|
| tenant | `campus.read` | campus | institute |
| tenant | `campus.create` | tenant | institute |
| tenant | `campus.update` | campus | institute |
| tenant | `member.read`, `member.invite`, `member.update`, `member.suspend`, `member.revoke` | tenant | identity |
| tenant | `role.read`, `role.create`, `role.update`, `role.delete`, `role.assign` | tenant | access |
| tenant | `tenant.profile.read` | tenant | tenants |
| tenant | `audit.read` | tenant | audit |
| platform | `tenant.read`, `tenant.create`, `tenant.suspend`, `tenant.reactivate` | — | tenants |
| platform | `platform_user.read`, `platform_user.create`, `platform_user.update`, `platform_user.suspend`, `platform_user.reactivate` | — | platform_identity |
| platform | `audit.read` | — | audit |

**Scope** (D-B1):

- `tenant` — tenant-wide; requires all-campus access (`campus_scope = ALL`).
- `campus` — checked against the campus of the resource.

### Adding a permission

1. Declare it in the owning module's `permissions.py`. Add the module to `app/modules/access/catalog.py` if it is new.
2. Add the row to the `permissions` table in a new migration.
3. If a system role must hold it, update `app/modules/access/templates.py` and insert the clone rows for every tenant in the same migration.
4. Reference the constant in code; never write the code as a string literal outside `permissions.py`. A test enforces this.

The drift tests (`tests/integration/test_permission_sync.py`) fail until code and database agree.

## 2. Roles

**Tenant system roles** (one clone per tenant, `is_system = true`):

| Template | Name | Permissions |
|---|---|---|
| `INSTITUTE_OWNER` | Institute owner | every tenant permission |
| `ADMIN` | Administrator | every tenant permission except `role.delete` |

**Custom roles:**

- They are tenant rows with explicit permissions.
- A membership may hold several roles; its effective permissions are the **union**.
- Migration `0005` cloned the system roles for existing tenants and assigned none.

**Platform roles** (code-defined, `app.modules.platform_identity.roles`):

| Role | T01 permissions |
|---|---|
| `SUPER_ADMIN` | every platform permission |
| `SECURITY_AUDIT_ADMIN` | `audit.read` |
| `PLATFORM_OPERATIONS_ADMIN`, `CUSTOMER_SUCCESS_ADMIN`, `BILLING_ADMIN`, `SUPPORT_ADMIN`, `AI_PLATFORM_ADMIN` | none |

They are assigned to platform users in T01-06.

## 3. Database (migration `0005`)

| Table | Runtime privileges (`mti_app`) | Row-Level Security (application role) |
|---|---|---|
| `permissions` | SELECT | everyone may read (also `mti_readonly`) |
| `roles` | SELECT, INSERT, UPDATE, DELETE | own tenant or system realm. INSERT, UPDATE and DELETE: custom roles only, except in the system realm |
| `role_permissions` | SELECT, INSERT, DELETE | own tenant or system realm. INSERT and DELETE: custom roles of the tenant only, except in the system realm |
| `membership_roles` | SELECT, INSERT, DELETE | own tenant or system realm |

- **Triggers** `roles_protect_system` and `role_permissions_protect_system` reject renaming, updating or deleting system roles and their permissions for everyone (SQLSTATE `MT001`). They also reject promoting a custom role to a system role.
- **Foreign keys.** `role_permissions.permission_realm` is a generated column, always `'tenant'`, inside the foreign key to `permissions(realm, code)`. Composite foreign keys keep memberships, roles and assignments in one tenant.
- **Read-only role.** `mti_readonly` may read only the catalogue.
- There are no `SECURITY DEFINER` functions.

## 4. Request flow

```text
cookie → IdentityService.resolve (T01-04)
           ├─ session, user, membership, tenant status, campus (D04)
           └─ effective permissions = ∪ role permissions
                 − unknown codes
                 − tenant-scope codes unless campus_scope = ALL
realm guard → RequestContext(permissions, all_campuses, campus_ids)
require_permission(P) → authorize(context, P)              401 / 403
handler loads resource (RLS + ORM filter; miss → 404)
        → authorize(context, P, resource)                  404 other tenant / campus
```

The order of the checks inside `authorize` is listed in [ADR-0016](../adr/0016-authorization-rbac.md) §4.

### Status codes

| Status | When |
|---|---|
| 401 | No session, or the session is not ready (no institute, campus not chosen, tenant or membership suspended) |
| 403 `PERMISSION_DENIED` | Missing permission; tenant-wide permission for a campus-restricted member; wrong realm |
| 404 `NOT_FOUND` | Another tenant's resource; a campus resource outside the permitted campuses; identical to a missing resource |

Denials never name the permission, role, tenant or campus.

**Audit:**

- `authz.denied` (security) records the permission code and realm of each refused `require_permission`.
- Allowed checks are not audited.

## 5. Session

`GET /api/v1/session` (and the sign-in and selection responses) add two fields, both for the active institute:

- `permissions` — sorted codes;
- `roles` — `[{name, is_system}]`, with no IDs.

Both are empty without an active institute. Changing the active campus never changes them. Role changes apply on the next session read (UI contract §6).

## 6. Route coverage

| Route kind | Requirement |
|---|---|
| `Access.AUTHENTICATED` | exactly one `require_permission(...)`, or a reviewed `authenticated_only` exemption |
| `Access.SESSION` | a reviewed `authenticated_only` exemption |
| `Access.ANONYMOUS` | a reviewed `public_route` exemption; never a permission |

The exemptions live in `app/api/coverage.py` (`REVIEWED_EXEMPTIONS`, each with a reason). They are the nine T01-04 authentication and session routes. `tests/security/test_route_coverage.py` runs the check on the real application.

## 7. Role administration service (API in T01-08)

`app.modules.access.service` provides:

- `create_role`, `update_role` and `delete_role`;
- `assign_role` and `remove_role`;
- `membership_access` and `clone_system_roles`.

Rules:

- each operation requires its `role.*` permission;
- another tenant's role or membership is not found (`404`);
- **no escalation:** a caller adds or removes only permissions it holds;
- system roles are refused (`403` + `role.system_change_rejected`);
- a stale version is `409`, and deleting an assigned role is `409`;
- audit events: `role.created`, `role.updated`, `role.permissions_changed`, `role.deleted`, `membership.role_assigned`, `membership.role_removed`.

## 8. Tests

| Suite | What it proves |
|---|---|
| `tests/unit/test_authz_registry.py` | Code format, realms and scopes; catalogue = T01 baseline; templates; platform role map; D-B1 filter |
| `tests/unit/test_authz_engine.py` | Decision order and outcomes of `authorize` |
| `tests/integration/test_rbac_schema.py` | Migration (clones, no assignments, downgrade); privileges; RLS; D-B2 triggers for the system realm and the owner; no platform or wildcard codes; tenant isolation |
| `tests/integration/test_permission_sync.py` | Database catalogue and system role clones = code (D-B4) |
| `tests/integration/test_session_permissions.py` | Session `permissions` and `roles`; tenant switch changes them, campus switch does not; role changes on reread |
| `tests/integration/test_authorization_api.py` | HTTP 401/403/404 matrix, D-B1, IDOR, forged identifiers, suspended tenant or membership, realm separation, `authz.denied` |
| `tests/integration/test_access_service.py` | Custom roles, D-B2 refusals, no escalation, union, cross-tenant 404, audit |
| `tests/security/test_route_coverage.py` | Coverage meta-test and every misuse it must catch |
| `tests/security/test_authorization_boundaries.py` | No role names in authorization logic; permission codes only in `permissions.py`; no catalogue writes |
