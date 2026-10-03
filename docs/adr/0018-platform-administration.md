# ADR-0018 — Platform Administration Implementation

- **Status:** Accepted (T01-07)
- **Date:** 2026-10-03
- **Task:** T01-07
- **Related:** [platform-administration.md](../architecture/platform-administration.md) (locked decisions D7-1 … D7-10), [ADR-0014](0014-tenancy-core.md), [ADR-0016](0016-authorization-rbac.md), [ADR-0017](0017-platform-identity-mfa.md), [spec-inconsistencies.md](../architecture/spec-inconsistencies.md) INC-38, INC-39

## Context

The T01-07 review locked D7-1 … D7-10. This ADR records how they were implemented, and the points where the implementation had to refine them (§9).

## Decision

### 1. Migration `0007`

- **New table:** `platform_user_invitations` (HMAC token, `expires_at`, `accepted_at`, `revoked_at`, `invited_by`; RLS; `SELECT, INSERT, UPDATE` for the application role, nothing for `mti_readonly`).
- **New column:** `tenants.owner_membership_id`, with the composite foreign key `(id, owner_membership_id) → tenant_memberships(tenant_id, id)`.
- **Revoke reasons:** `user_sessions` gains `tenant_suspended`; `platform_sessions` gains `admin_suspended`.
- **Policies:** existing policies are altered in place, keeping their names. Each gains one equality-matched term; the downgrade restores the frozen 0004–0006 expressions.

| Key (published by) | Opens |
|---|---|
| `app.provisioning_tenant_id` together with the same `app.tenant_id` (`tenants.scopes`) | Inserts of that tenant's system roles and their permissions; an `INVITED` `users` row |
| `app.platform_target_tenant_id` (`tenants.scopes`) | `user_sessions` whose `active_tenant_id` is that tenant (select, update) |
| `app.platform_owner_membership_id` (`tenants.scopes`) | One `tenant_memberships` row, its `user_invitations` and its `users` row |
| `app.platform_admin_target_user_id` (`platform_identity.lookup`) | For an authenticated platform principal: that platform user's row (update; insert only as `INVITED`), roles (insert, delete), sessions and invitations |
| `app.platform_auth_token_hash` (0006 key, `platform_identity.lookup`) | Also one platform invitation, its user and that user's first credential |

Every new term requires `app.realm = 'platform'`. Tenant contexts and the read-only role gain nothing. No `SECURITY DEFINER`.

### 2. Provisioning (D7-1, D7-7)

- `tenants.scopes.provisioning_transaction` binds a copy of the authorized platform context with the new server-generated tenant ID and publishes the provisioning key. The ordinary tenant policies then admit the new tenant's rows.
- In one transaction it creates the tenant (`TRIAL`), the primary campus, the two system roles (`clone_system_roles`), the `INVITED` owner identity (unless the email already has one) and the owner membership. The membership gets the owner template role and an invitation (7 days, HMAC).
- `platform.tenant.created` and `platform.tenant.owner_invited` are written in the same transaction, with the new tenant as `tenant_id`.
- The existing identity is found with the T01-04 email lookup transaction. A `DISABLED` identity is refused with `409`.
- The email is sent after the response.

### 3. Tenant lifecycle (D15, D7-6)

- Suspension and reactivation use `tenants/domain.py`, take a reason (1–500 characters) and the `version`, and require step-up.
- Suspension publishes the suspension key and revokes every live session whose active institute is the tenant, in the same transaction. The audit metadata carries the revoked count.

### 4. Platform users (D7-2 … D7-5)

`PlatformUserAdmin` (`platform_identity/admin.py`) authorizes first, then opens one administration target transaction.

- **Create:** `INVITED` plus roles plus an invitation.
- **Update:** name and roles, under the current `version`.
- **Suspend:** revokes the user's sessions (`admin_suspended`) and open invitations.
- **Reactivate:** gives `ACTIVE`, or `INVITED` for a user who never accepted an invitation. MFA is never touched.
- **Resend invitation, MFA reset:** the reset delegates to the D6-3 service.
- **Self-protection:** no role change, suspension or MFA reset of one's own account (`platform.user.self_action_refused`).
- **Last guardian:** the last active holder of `GUARDIAN_ROLE` (`SUPER_ADMIN`) is never suspended or demoted.
- **Invitation acceptance:** public. Generic `404`, the T01-04 password rules, single use. The user becomes `ACTIVE`, and the first sign-in requires MFA enrolment.

### 5. Step-up (D7-4)

`platform_user.suspend` and `platform_user.reactivate` are declared `requires_step_up`. The flag lives in code only, so the permission catalogue is unchanged.

### 6. Audit read (D7-9)

`GET /api/v1/platform/audit-events` takes filters for category, event type, tenant (in it or about it), actor, target and a created-at range. Results are newest first, with offset pagination.

### 7. API

| Route | Permission |
|---|---|
| `GET/POST /api/v1/platform/tenants`, `GET /tenants/{id}` | `tenant.read` / `tenant.create` |
| `POST /tenants/{id}/suspend`, `/reactivate` | `tenant.suspend` / `tenant.reactivate` (step-up) |
| `POST /tenants/{id}/owner-invitation/resend` | `tenant.create` |
| `GET/POST /api/v1/platform/platform-users`, `GET/PATCH /platform-users/{id}` | `platform_user.read` / `.create` / `.update` (step-up for writes) |
| `POST /platform-users/{id}/suspend`, `/reactivate` | `platform_user.suspend` / `.reactivate` (step-up) |
| `POST /platform-users/{id}/invitation` | `platform_user.create` (step-up) |
| `POST /platform-users/{id}/mfa/reset` | `platform_user.update` (step-up) |
| `GET /api/v1/platform/audit-events` | `audit.read` |
| `POST /api/v1/platform/auth/invitations/preview`, `/accept` | `public_route` (reviewed exemption) |

### 8. Static enforcement

- Only `tenants/scopes.py` publishes the three tenant-scope keys or gives a platform context a tenant.
- Only `platform_identity/lookup.py` publishes the administration key.
- No `unscoped()` exists (D7-10; INC-38 stays open).

### 9. Refinements of the locked decisions

1. **D7-1:** besides the `users` insert, the provisioning key needs terms on `roles_insert` and `role_permissions_insert`, because migration 0005 lets only the system realm insert system roles. The terms require the key and `app.tenant_id` to name the row's tenant.
2. **D7-5:** concurrent guardian changes are serialised by a transaction-level advisory lock, not a row lock. `platform_user_roles` has no `UPDATE` privilege, and the target transaction opens one user only. The guarantee is the same.
3. **D7-4:** a platform-session revoke reason, `admin_suspended`, was added.
4. **D7-8:** `tenants.owner_membership_id` was added so the owner can be found without opening the tenant's other members. The tenant detail shows the owner's name, email and membership status.
5. **D7-3:** reactivating a user who never accepted their invitation restores `INVITED`.

## Consequences

- There is no `Idempotency-Key` on provisioning. A repeated request creates a second institute; PLATFORM-ADMIN.md §56 idempotency arrives with the provisioning engine (T02-12).
- The platform user directory has no MFA or last-sign-in columns: factors and sessions stay own-row (T01-06).
- Tenant audit readers see provisioning events, because those events carry the tenant ID. T01-08 decides whether they should (recorded in D7 constraints).

## Alternatives considered

- **`system_context` for provisioning:** it refuses to run inside an HTTP request (ADR-0014).
- **Platform-wide RLS on platform user tables:** this would lose the T01-06 own-row defence (D7-2).
- **Row locks on guardian rows:** this would need broader privileges and visibility (§9.2).
