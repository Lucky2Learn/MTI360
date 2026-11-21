# ADR-0023 — Membership Owner Scope and Safe Re-invitation

- **Status:** Accepted (decisions approved by the user, 2026-10-30). Implemented on `feat/platform-tenant-management` (uncommitted); not browser-verified.
- **Date:** 2026-10-30
- **Task:** 02-C tenant part — ADMIN-05 Users / ADMIN-06 User Detail (T03-04) membership security follow-up
- **Supersedes:** [ADR-0019](0019-tenant-administration.md) §10.3 (re-invitation part only) and §10.4
- **Related:** [tenant-administration.md](../architecture/tenant-administration.md) (D8-3, D8-4), [ADR-0016](0016-authorization-rbac.md) (no escalation, D-B1 campus scoping), [ADR-0013](0013-audit-events.md), INC-51

## Context

The ADMIN-05/06 security audit (2026-10-30) found two gaps in the T01-08 member administration.

1. **An owner could lose institute-wide administration through campus scope.** D-B1 removes every tenant-wide permission (members, roles, campus creation, audit) from a member whose campus scope is `SELECTED`. ADR-0019 §10.4 counted an owner "whatever its campus scope", and the last-owner check (`keep_an_owner`) was not applied to campus-scope changes. An Administrator could therefore limit the only owner to selected campuses, or limit one owner and then suspend the other. The institute would still have an "active owner" who could no longer manage members or roles; only the platform could recover it. The same state could be reached by giving the owner role to a campus-limited member, or by inviting an owner with selected campuses. D8-4's stated rationale ("the owner holds every tenant permission") is false for such an owner.
2. **Re-invitation silently restored roles.** Removal (`REVOKED`) keeps the membership's role assignments, and ADR-0019 §10.3 let re-invitation restore them without the no-escalation rule. An Administrator, who cannot grant the owner role, could remove a second owner and re-invite them back as owner.

## Decision

### 1. Owner all-campus invariant

**Every membership holding the `INSTITUTE_OWNER` system role has `campus_scope = ALL`, in every membership status.** A campus-limited member never becomes an owner; nothing silently widens access to make an owner valid.

Enforcement points, all in the request's tenant transaction:

| Entry point | Refusal | Error |
|---|---|---|
| `PUT /members/{id}/campus-scope` to `SELECTED` for a member holding the owner role | after self-protection (`403` stays first) | `422`, `field = "campus_scope"` |
| `POST /members/{id}/roles` with the owner role for a `SELECTED` member | after `role.assign` and the no-escalation rule (`403` stays first) | `422`, `field = "role_id"` |
| `POST /members/invitations` with the owner role and `campus_scope = SELECTED` | inside the invitation transaction; nothing remains (no identity, membership, campus row, role, invitation or audit event) | `422`, `field = "campus_scope"` |
| Development seed (`app.seed.parse_seed`) | an `INSTITUTE_OWNER` with `SELECTED` scope is a `SeedError` | — |

All three API refusals use the error detail code **`owner_requires_all_campuses`** in the standard `VALIDATION_ERROR` envelope. The membership is not changed and no success audit event is written. Reinstatement and re-invitation cannot create a limited owner on their own: re-invitation clears roles (§3), and reinstatement restores a membership that already satisfies the invariant.

### 2. Owner counting and concurrency

- An **administrative owner** is an `ACTIVE` membership holding the `INSTITUTE_OWNER` system role **and** `campus_scope = ALL`. `_active_owner_memberships` (access repository) applies all three conditions, so `keep_an_owner` and the last-owner `409` count only owners who can administer the institute. This is defence in depth: under §1, no other kind of owner can be created through the API.
- The campus-scope change (to `SELECTED`) and the owner-role assignment both take the existing per-tenant transaction advisory lock (`OWNER_LOCK_CLASS`, D8-4) **before** they read the state they check. Under PostgreSQL's default `READ COMMITTED` isolation, the second transaction reads the first one's committed result, so concurrent "limit this member" and "make this member owner" requests cannot both succeed.
- The last-owner protection is unchanged otherwise.

### 3. Re-invitation clears roles

`REVOKED → INVITED` (`POST /members/{id}/reinvite`, version only — no new request field) runs in one transaction:

1. load the member and authorize `member.invite`; refuse a disabled account (`409`);
2. apply the versioned transition (stale version or wrong status → `409`);
3. remove **every** role assignment of the membership (`access.repository.unassign_all`, through `access.service.clear_roles`);
4. revoke open invitations and issue a new single-use invitation;
5. write `member.reinvited`.

Any failure rolls the whole transaction back, so a refused re-invitation leaves the roles in place. Clearing does not use `remove_role`: removing a role only reduces access, so the no-escalation rule (which would refuse an Administrator clearing the owner role) does not apply, and the last-owner check is unnecessary because a removed member is not active. The response lists no roles; administrators assign roles again through `POST /members/{id}/roles`, which applies `role.assign`, no escalation and §1.

The previous **campus scope is kept**. With no roles it grants nothing.

**Reinstatement is unchanged:** `SUSPENDED → ACTIVE` keeps the member's roles (a suspension is temporary).

### 4. Audit

`member.reinvited` metadata gains `roles_cleared` (count), `cleared_role_ids` and `cleared_role_names` (parallel lists, the first 16 by role name — the audit metadata limit, as for `role.permissions_changed`), next to the existing `revoked` (invitations revoked). Tenant, actor and target come from the standard audit columns (`tenant_id`, `principal_id`, `target_type = tenant_membership`, `target_id`). No token or secret is recorded. Refusals under §1 write no audit event.

### 5. API addition: `is_owner`

The UI must recognise the owner role without matching role names or inspecting a member's role list (role names stay out of authorization logic; the frontend's static authorization check forbids role-list comparisons). `RoleOut` (`GET /roles`, `GET /roles/{id}`) and `MemberRoleOut` gain a read-only boolean **`is_owner`**, true for the `INSTITUTE_OWNER` system role, and `MemberOut` (every member response) gains **`is_owner`**, true when the member holds that role. The UI uses these flags only as hints; the API enforces §1. The fields are additive; requests are unchanged.

### 6. User interface

- Campus access dialog: for a member holding the owner role, "Selected campuses" is disabled with an explanation.
- Invite dialog: choosing Institute owner requires all campuses; the API error is shown at the campus access field.
- Add role: the Institute owner role is not offered to a campus-limited member, and the reason is shown.
- Re-invite confirmation: states that previous roles are removed and must be assigned again.

## Consequences

- An institute can no longer be left without an owner able to manage members and roles through campus scope.
- Administrators can no longer limit an owner's campuses. Owners (or holders of every owner permission) must widen a member's access before making them owner.
- A re-invited member joins with no roles until an administrator assigns them; a role an administrator could not grant can no longer come back through re-invitation.
- **Existing data:** no migration. Two read-only checks (DEVELOPMENT-STATUS.md, "ADR-0023 data checks") find limited owners and pending re-invitations that still hold roles; any result is handled manually with approval.
- **Compatibility:** the API adds the `is_owner` response field and new `422` cases; no request changes.

## Alternatives considered

- **Protect only the last owner's campus scope:** leaves other routes (owner role to a limited member, owner invitations) able to create a limited owner; rejected in favour of the invariant.
- **Silently widen to all campuses when the owner role is assigned:** a hidden privilege expansion; rejected.
- **A database trigger for the invariant:** owner status spans `membership_roles` and `roles`, so it would duplicate the rule in a trigger (CLAUDE.md §41). Rejected; the application enforces it under the owner lock, with tests.
- **Clear roles on removal instead of re-invitation:** would need a data fix for existing removed members and would erase who held which role until re-invitation; rejected.
- **Accept `role_ids` on re-invitation:** a request contract change; roles are assigned afterwards through the existing endpoint instead.
