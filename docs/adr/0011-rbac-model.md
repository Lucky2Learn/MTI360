# ADR-0011 — Role-Based Access Control Model

- **Status:** Accepted (T01-00 approval, decisions D7, D8; implementation in T01-05, T01-06)
- **Date:** 2026-09-30
- **Task:** T01-00 (recorded in T01-01)
- **Related:** [ADR-0005](0005-identity-and-session-realms.md), [security.md](../architecture/security.md) §5, PRD.md §85, PLATFORM-ADMIN.md §7, §85, INC-06, INC-30

## Context

Platform and tenant roles must be separate: a tenant administrator can never gain platform access. Roles must be granular and configurable per tenant, and the specifications disagree on the role names (INC-06, INC-30).

## Decision

1. **Permission registry in code.**
   - Each module declares `resource.action` permissions with a realm (`platform` or `tenant`).
   - They are synced to a `permissions` table, with columns code, realm, module and description.
2. **Tenant roles are per-tenant rows** (`roles`, RLS), cloned from code templates when a tenant is provisioned; tenants may create custom roles.
   - `role_permissions` carries a generated column `permission_realm = 'tenant'` and a foreign key `(permission_code, permission_realm) → permissions(code, realm)`, so **the database rejects a platform permission on a tenant role**.
   - Assignment goes through `membership_roles`, per tenant membership.
3. **Platform roles are a fixed set of codes** (PRD.md §85: `SUPER_ADMIN`, `PLATFORM_OPERATIONS_ADMIN`, `CUSTOMER_SUCCESS_ADMIN`, `BILLING_ADMIN`, `SUPPORT_ADMIN`, `SECURITY_AUDIT_ADMIN`, `AI_PLATFORM_ADMIN`), assigned in `platform_user_roles`.
   - Their permission map lives in code and is unit-tested.
4. **One authorization function.** `authorize(context, permission, resource)` checks, in order:
   1. realm;
   2. authentication and MFA;
   3. tenant status;
   4. permission;
   5. campus scope;
   6. resource ownership.

   It is applied through `require_permission(...)` on every route, and the route-coverage test fails when a route has neither a permission nor a reviewed exemption.
5. **No escalation.** A principal can grant only permissions it holds.
6. **T01 minimum (D7):**
   - Platform permissions are granted to `SUPER_ADMIN` and `SECURITY_AUDIT_ADMIN` only.
   - Tenant templates are `INSTITUTE_OWNER` and `ADMIN` only.
   - Business role templates arrive with their modules, after INC-06 is resolved (before Phase 04).
   - Students are a separate realm, never a staff role.
7. **Support sessions are deferred to Phase 02 (D8).** Until then no platform principal has any path to tenant data, and tests assert it.

## Consequences

- Role names can change (INC-06) without code changes to authorization; only templates change.
- Permission checks are explicit and testable per route; UI gating stays cosmetic.

## Alternatives considered

- **Roles only, without permissions:** too coarse for configurable tenant roles (PLATFORM-ADMIN.md §85). Rejected.
- **Platform roles as database rows:** unnecessary while the set is fixed. Revisit if platform role customisation is required.
- **One shared role table for both realms:** a single mistake could grant platform access. Rejected (ADR-0005).
