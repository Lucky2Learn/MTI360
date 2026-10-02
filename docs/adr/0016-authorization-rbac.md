# ADR-0016 — Authorization and RBAC Implementation

- **Status:** Accepted (T01-05)
- **Date:** 2026-10-02
- **Task:** T01-05
- **Related:** [ADR-0011](0011-rbac-model.md) (RBAC model), [ADR-0014](0014-tenancy-core.md), [ADR-0015](0015-identity-authentication.md), [authorization.md](../architecture/authorization.md), [security.md](../architecture/security.md) §5, [UI contract](../ui/T01-05-AUTHORIZATION-RBAC-UI.md)

## Context

ADR-0011 fixed the RBAC model. The T01-05 architecture review locked four decisions:

- **D-B1** — campus authorization semantics;
- **D-B2** — system roles are immutable;
- **D-B3** — permission identity is `(realm, code)`, with the T01 baseline;
- **D-B4** — permissions are synchronised by migrations only.

The frozen UI contract fixed the session shape (`permissions`, `roles`). This ADR records how they were implemented and the decisions the implementation had to take.

## Decision

### 1. Permission registry (D-B3, D-B4)

- **Declaration.** Permissions are declared in each module's `permissions.py` with `permission(code, realm, scope, description, module=…)`.
  - The code is `resource.action` in lower case; wildcards cannot be declared.
  - Only the `platform` and `tenant` realms have permissions.
  - Tenant permissions carry a scope (`TENANT` or `CAMPUS`); platform permissions have none.
- **Catalogue.** `app.modules.access.catalog` imports every `permissions.py`. A test fails if a module's `permissions.py` is missing from it.
- **Database sync.** The registry never writes to the database. Migration `0005` seeds the `permissions` table from a frozen copy, and the runtime roles can only read it. Tests compare the table with the registry (D-B4 drift test).

### 2. Tenant roles and system-role immutability (D-B2)

- **Tables.** `roles`, `role_permissions` and `membership_roles` are tenant-scoped, with composite tenant foreign keys and Row-Level Security.
- **System roles.** A system role has `is_system = true` and `template_code` (`INSTITUTE_OWNER` or `ADMIN`), enforced by a CHECK.
- **Database enforcement.** It does not depend on the application:
  - **RLS:** a tenant context may create, update or delete only custom roles. Only the system realm may create a system role or insert its permissions.
  - **Triggers:** `roles_protect_system` and `role_permissions_protect_system` reject renaming, updating or deleting a system role and changing its permissions (SQLSTATE `MT001`), for every database role, the table owner included. They also reject turning a custom role into a system role. They are plain `SECURITY INVOKER` functions.
- **Changing a template.** A later change to a template is a migration that updates both `templates.py` and every tenant's clone; a test compares them.
- **Generated realm column.** `role_permissions.permission_realm` is a generated column, always `'tenant'`, and part of the foreign key `(permission_realm, permission_code) → permissions(realm, code)`. The database therefore rejects platform, unknown and wildcard codes on tenant roles (ADR-0011 §2).
- **Migration of existing tenants.** `0005` clones `INSTITUTE_OWNER` (every tenant permission) and `ADMIN` (every tenant permission except `role.delete`) for every existing tenant. It assigns **no** role to existing members.

### 3. Effective permissions (D-B1)

- **Resolution.** `IdentityService.resolve` (T01-04) computes the effective permissions of the active membership on every request: the **union** of its roles' permissions.
  - Codes that are not declared in code are dropped (fail closed).
  - When the membership's `campus_scope` is not `ALL`, permissions with `TENANT` scope are dropped as well.
- **Request context.** The realm guard puts the permissions, `all_campuses` and the permitted campus IDs in `RequestContext`. The active campus is not part of them.
- **Session.** The session returns the same permissions, sorted, and the roles as `{name, is_system}`, both for the active institute only. Changes apply on the next session read; there is no polling.

### 4. `authorize` and `require_permission`

`authorize(context, permission, resource=None)` is synchronous and does no I/O. It checks, in order:

1. **Principal:** an authenticated principal is required, otherwise `401`.
2. **Realm:** the permission must belong to the request's realm, otherwise `403`.
3. **Tenant:** a tenant permission needs an active tenant. Tenant status was already validated when the session was resolved: a suspended tenant has no active tenant, so `401`.
4. **MFA hook:** `requires_step_up` permissions are refused (`403`) until T01-06.
5. **Permission:** the code must be among the effective permissions, otherwise `403`.
6. **Campus scope:** `TENANT` scope needs all-campus access, otherwise `403`.
7. **Resource tenant:** a resource of another tenant is `404`.
8. **Resource campus:** a `CAMPUS`-scope resource outside the permitted campuses is `404`.

The principal is checked before the realm (ADR-0011 listed the realm first), so that an unauthenticated caller always receives `401`.

`require_permission(permission)` applies steps 1–6 as a route dependency and records the security event `authz.denied` (permission code and realm only) on refusal. Handlers that load a resource call `authorize` again with it. Denial bodies are the standard envelope and never name the permission, role, tenant or campus.

### 5. Route coverage

- **Rule.** Every API route has exactly one `require_permission`, or is listed in `app/api/coverage.py:REVIEWED_EXEMPTIONS` with a kind and a reason:
  - `public_route` on anonymous routes;
  - `authenticated_only` on session or authenticated routes, for routes that act only on the caller's own data.
- **Exemptions.** The nine T01-04 routes are the reviewed exemptions.
- **Meta-test.** It runs on the real application and rejects:
  - unprotected routes;
  - more than one permission on a route;
  - permissions on anonymous routes;
  - permissions of another realm;
  - exemptions that do not match the access level;
  - stale exemptions.

### 6. Custom roles and assignments — service only

`app.modules.access.service` provides the foundation for T01-08: create, update and delete custom roles, and assign and remove roles. Each operation:

- authorizes the caller (`role.*`) and the resource;
- applies **no escalation** (ADR-0011 §5) to granting **and** removing: a caller adds or takes away only permissions it holds. An Administrator can therefore neither give nor remove the Institute owner role;
- refuses system roles with `403` and the security event `role.system_change_rejected`;
- uses optimistic versions (`409` when stale), refuses deleting an assigned role (`409`) and writes an admin audit event in the same transaction:
  - `role.created`, `role.updated`, `role.permissions_changed`, `role.deleted`;
  - `membership.role_assigned`, `membership.role_removed`.

There is no HTTP API for these operations in T01-05.

### 7. Platform roles

The seven platform role codes and their permission map are code (`app.modules.platform_identity.roles`):

- `SUPER_ADMIN` has every T01 platform permission, expanded;
- `SECURITY_AUDIT_ADMIN` has `audit.read`;
- the others have nothing in T01.

`platform_user_roles` storage arrives with `platform_users` in T01-06. Platform routers still deny every request.

## Consequences

- Authorization data is server-authoritative. The frontend may hide controls with the session permissions, but every protected route and resource load is checked by `authorize`.
- Role names and codes are never authorization logic: a static test allows them only in the template and platform role definitions.
- Each authenticated request runs one more query (role permissions) inside the existing session-resolution transaction.
- Adding a permission is a code declaration **plus** a migration row (plus template clone rows when a system role must hold it); the drift tests fail otherwise.

## Deviations from the T01-05 prompt and specifications

- **Platform role assignment storage is deferred to T01-06**, because there are no platform users before T01-06. The role map is implemented and unit-tested.
- **No HTTP API for custom roles or assignments** (T01-08). Tenant creation, which calls `clone_system_roles`, arrives in T01-07.
- **Feature entitlements are not checked**: subscriptions and entitlements do not exist yet (Phase 15). tenancy.md §4 lists them for the authorization dependency.

## Alternatives considered

- **RLS alone for D-B2.** Rejected: the table owner and the system realm pass RLS, and D-B2 requires the database to refuse system-role changes whatever the caller. The triggers close that gap without `SECURITY DEFINER`.
- **A CHECK `permission_realm = 'tenant'` instead of a generated column.** Rejected in favour of ADR-0011 §2: a generated column cannot be written at all.
- **Wildcard grants for templates or `SUPER_ADMIN`.** Rejected (D-B3). Templates are expanded to explicit codes.
- **Synchronising permissions at application start-up.** Rejected (D-B4). Migrations are reviewed and repeatable; runtime roles cannot write the catalogue.
- **Per-route exemption decorators.** Rejected in favour of one reviewed list (`REVIEWED_EXEMPTIONS`) that a reviewer reads in one place, with a reason for each entry.
- **Loading permissions on each `authorize` call.** Rejected: permissions are resolved once per request with the session, and `authorize` stays pure and synchronous.
