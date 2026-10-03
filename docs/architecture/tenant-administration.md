# Tenant Administration Foundation (API)

- **Status:** Decisions D8-1 … D8-4 locked (T01-08 architecture review, 2026-10-03); implementation not started. The implementation ADR (ADR-0019) is written with the implementation.
- **Builds on:**
  - [ADR-0004](../adr/0004-tenant-isolation.md) and [ADR-0014](../adr/0014-tenancy-core.md): realm-agnostic tenant RLS; `system_context` refuses to run inside an HTTP request.
  - [ADR-0013](../adr/0013-audit-events.md): the audit writers and the `audit_events` policies.
  - [ADR-0015](../adr/0015-identity-authentication.md) and [identity-authentication.md](identity-authentication.md): global `users`, memberships, invitations (D05, D19), per-request session resolution.
  - [ADR-0016](../adr/0016-authorization-rbac.md) and [authorization.md](authorization.md): `authorize`, `require_permission`, the access service, the no-escalation rule, immutable system roles (D-B2), D-B1.
  - [ADR-0018](../adr/0018-platform-administration.md) and [platform-administration.md](platform-administration.md): the narrow-key pattern (D7-1, D7-2), the advisory-lock pattern (D7-5), and the tenant-audit consequence handed to T01-08.
  - T01-00 decision D14: tenant admins cannot change global identity or credentials.
- **Scope (TASKS.md T01-08):** campuses, members (invite, suspend, revoke), member roles and campus scope, custom roles, tenant audit read, and the development seed (D16). The screens remain in Phase 03.

## Locked decisions

| # | Decision |
|---|---|
| **D8-1** | **New tenant invitee identity.** New invitees' `INVITED` identities are created through a narrow invitee key published only by the tenant invitation module after authorization. Existing accounts are reused unchanged, and `DISABLED` identities return `409`. There is no tenant-realm-wide `users` INSERT. |
| **D8-2** | **Tenant audit visibility.** Tenant audit reads return only events written in the tenant realm for the trusted tenant, enforced by the `audit_events_tenant_read` RLS policy. Platform-written events, including provisioning events, remain platform-only. |
| **D8-3** | **Member lifecycle and sessions.** Membership transitions are listed below; all of them are versioned. Membership suspension or revocation does not globally revoke the user's sessions: authorization already re-checks the membership on each request and removes access to the affected tenant. |
| **D8-4** | **Self-protection and last owner.** Tenant administrators cannot suspend, revoke, change the campus scope of, or remove roles from their own membership. Every institute must retain at least one `ACTIVE` membership holding the `INSTITUTE_OWNER` system role. The last-owner check is serialised by a per-tenant transaction advisory lock. Self-protected actions return `403`. Attempting to remove, suspend or revoke the last active owner returns `409`. |

D8-3 membership transitions:

| Transition | Through |
|---|---|
| `INVITED → ACTIVE` | The existing invitation acceptance flow (T01-04) |
| `ACTIVE ⇄ SUSPENDED` | `member.suspend` (both directions) |
| `INVITED` \| `ACTIVE` \| `SUSPENDED` → `REVOKED` | `member.revoke`, which also revokes the membership's open invitations |
| `REVOKED → INVITED` | Re-invitation of the same membership row |

## Rationale, security and impact

### D8-1 — New tenant invitee identity

- **Gap.** `users_insert` is `SYSTEM`, plus the T01-07 provisioning term `PROVISIONED_OWNER` (migrations 0004 and 0007). A tenant-realm request cannot create an identity, so only people who already have an account could be invited.
- **Rationale.** Widening `users_insert` to the tenant realm would let any tenant code path create global identities. `system_context` cannot run inside an HTTP request (ADR-0014). The narrow-key pattern of D7-1 and D7-2 is already established.
- **Security.**
  - The new term admits one server-generated user ID, with status `INVITED` only.
  - The key is published only after `member.invite` (and, for initial roles, `role.assign` with the no-escalation rule) has been authorized.
  - A static test allows only the tenant invitation module to publish the key.
  - Existing accounts are found with the T01-04 email lookup transaction and never changed (as D7-7 and D14 require).
  - Tenant isolation continues to rest on the membership and the invitation, which the ordinary tenant RLS already protects.
- **RLS.** `users_insert` gains one term: tenant realm, a trusted tenant, `id` equal to the invitee key, and `status = 'INVITED'`. The downgrade restores the 0007 expression.
- **Migration.** 0008 (`users_insert` policy term).
- **Implementation consequence.** The invitation service authorizes, looks the email up, publishes the key in the request's tenant transaction, then creates or reuses the identity, the membership and the invitation (T01-04 token and link). Email is sent after commit (D10).

### D8-2 — Tenant audit visibility

- **Gap.** `audit_events_tenant_read` is `app.realm = 'tenant' AND tenant_id = app.tenant_id` (migration 0002). That `app.realm` is the *reader's* realm. T01-07 provisioning writes `platform.tenant.created` and `platform.tenant.owner_invited` with `realm = 'platform'`, the new tenant as `tenant_id`, and the platform administrator as `principal_id` (ADR-0018 Consequences; platform-administration.md, Architecture constraints).
- **Rationale.** A query filter would rely on every future reader remembering it. An event allow-list would invent a vocabulary the specifications do not define. The RLS policy closes the leak for every tenant-realm reader.
- **Security.** Platform principal IDs and platform-internal events never reach a tenant. Sign-in events have no tenant ID (ADR-0015) and stay invisible. Platform reads (`audit_events_platform_read`) are unchanged.
- **RLS.** `audit_events_tenant_read` becomes `app.realm = 'tenant' AND realm = 'tenant' AND tenant_id = app.tenant_id`. The downgrade restores the 0002 expression. The `(tenant_id, created_at)` index still serves the read.
- **Migration.** 0008 (`audit_events_tenant_read` policy change).
- **Implementation consequence.** The tenant audit read requires the tenant `audit.read` permission (T01-05 baseline). No new permission is needed.

### D8-3 — Member lifecycle and sessions

- **Gap.**
  - The four membership statuses exist (`MembershipStatus`), but nothing sets `SUSPENDED` or `REVOKED`, and no transition rules exist.
  - `tenant_memberships_update` admits any change within the tenant.
  - `UNIQUE (tenant_id, user_id)` prevents a second membership row for a revoked person.
  - Sessions belong to the user (`user_sessions.user_id`), and one user may have memberships in several institutes.
- **Rationale.**
  - Session resolution already re-checks the membership, tenant status and campus on every request: only `ACTIVE` memberships are usable, and an unusable one clears the session's active tenant. Revoking the user's sessions would also sign them out of their other institutes.
  - Re-inviting the same row respects the unique constraint and keeps the membership history in one place.
  - Tenant suspension (D7-6) revokes sessions because the whole institute closes. A membership change affects only one institute, so the re-check is the right mechanism.
- **Security.**
  - Access to the affected tenant ends on the next request.
  - Other tenants are unaffected.
  - Global identity is never touched (D14).
  - Because the database admits any status write, the transitions live in one domain function, like `tenants/domain.py`.
- **RLS.** No change.
- **Migration.** None.
- **Implementation consequence.** Each transition takes the membership's `version` (stale → `409`; invalid transition → `409`). Reinstatement uses `member.suspend`, and re-invitation uses `member.invite`. No new permission is needed.

### D8-4 — Self-protection and last owner

- **Gap.** No self-protection or last-owner rule exists. `remove_role` (access service) and the coming suspend, revoke and campus-scope changes could leave an institute without an owner, and only the platform could recover it. The no-escalation rule does not prevent an owner from removing their own role.
- **Rationale.** This mirrors D7-5 (self-protection; last guardian; advisory lock). `INSTITUTE_OWNER` holds every tenant permission and can re-grant any other role, so protecting the last owner is sufficient.
- **Security.**
  - Self-lockout and concurrent mutual removal cannot empty an institute.
  - The lock is per tenant, so tenants never block each other.
  - The rule refers to the owner template through the `OWNER_TEMPLATE` constant (`access/templates.py`), so role names stay out of authorization logic (`test_authorization_boundaries`).
- **RLS.** No change. The count reads tenant-scoped `tenant_memberships`, `membership_roles` and `roles` in the trusted tenant. The advisory lock needs no privilege.
- **Migration.** None.
- **Implementation consequence.** The rule applies to suspend, revoke, campus-scope change and role removal. Self-actions return `403`; removing, suspending or revoking the last active owner returns `409`.

## Migration summary

| Decision | Migration 0008 |
|---|---|
| D8-1 | `users_insert`: narrow invitee-key term |
| D8-2 | `audit_events_tenant_read`: also requires `realm = 'tenant'` |
| D8-3 | None |
| D8-4 | None |
