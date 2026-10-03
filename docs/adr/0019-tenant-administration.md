# ADR-0019 — Tenant Administration Implementation

- **Status:** Accepted (T01-08)
- **Date:** 2026-10-03
- **Task:** T01-08
- **Related:** [tenant-administration.md](../architecture/tenant-administration.md) (locked decisions D8-1 … D8-4), [ADR-0014](0014-tenancy-core.md), [ADR-0015](0015-identity-authentication.md), [ADR-0016](0016-authorization-rbac.md), [ADR-0018](0018-platform-administration.md), T01-00 decision D16 (development seed)

## Context

The T01-08 review locked D8-1 … D8-4. TASKS.md T01-08 also covers campuses, member roles and campus scope, custom roles, the tenant audit read and the development seed (D16). This ADR records how they were implemented, and the points where the implementation had to refine them (§10).

## Decision

### 1. Migration `0008`

- **`users_insert`** gains one term (D8-1): tenant realm, a trusted tenant, an authenticated principal, `id = app.tenant_invitee_user_id` and `status = 'INVITED'`.
- **`audit_events_tenant_read`** becomes `app.realm = 'tenant' AND realm = 'tenant' AND tenant_id = app.tenant_id` (D8-2).
- **`membership_campuses`:**
  - gains the column `removed_at`;
  - the application role gains UPDATE (it still has no DELETE);
  - a `membership_campuses_update` policy is added, with the table's own tenant rule (§10.1).
- Policies are altered in place; the downgrade restores the frozen 0002/0007 expressions. Before dropping the column, the downgrade deletes the removed `membership_campuses` rows (as the owner), so a removed campus never becomes permitted again.
- No `SECURITY DEFINER`.

### 2. Invitation (D8-1)

`app.modules.identity.members.MemberAdmin.invite` runs these steps:

1. Authorizes `member.invite`.
2. Finds the email with the T01-04 lookup transaction.
3. Refuses a `DISABLED` identity (`409`).
4. Opens one tenant transaction. For a new person it publishes the invitee key for one server-generated ID, then inserts the `INVITED` identity. An existing identity is reused unchanged; an existing membership in the institute returns `409`.
5. Creates the `INVITED` membership, its campus scope and a 7-day single-use HMAC invitation (T01-04 acceptance flow).
6. Assigns the initial roles through `access.assign_role`, which applies `role.assign` and the no-escalation rule.
7. Writes `member.invited` in the same transaction.

Every step is in one transaction except the read-only email lookup in step 2; a refusal at any later step rolls back the whole invitation. The email is sent after the response. Only `members.py` publishes the key (a static test).

### 3. Tenant audit visibility (D8-2)

`GET /api/v1/audit-events` (tenant `audit.read`) states `realm = 'tenant' AND tenant_id = <active tenant>` in the query. The RLS policy enforces the same rule. A `tenant_id` query parameter is ignored.

### 4. Member lifecycle (D8-3)

`identity.domain.membership_transition`:

| Action | From | To | Permission |
|---|---|---|---|
| suspend | `ACTIVE` | `SUSPENDED` | `member.suspend` |
| reinstate | `SUSPENDED` | `ACTIVE` | `member.suspend` |
| revoke | `INVITED`, `ACTIVE`, `SUSPENDED` | `REVOKED` (open invitations revoked) | `member.revoke` |
| reinvite | `REVOKED` | `INVITED` (same row, new invitation) | `member.invite` |

- `INVITED → ACTIVE` stays the T01-04 acceptance flow.
- Updates are conditional on `version` and the current status; a stale version or an invalid transition is `409`.
- No session is revoked: session resolution clears the active institute of a membership that is no longer `ACTIVE` (a static test keeps sessions out of member administration).

### 5. Self-protection and last owner (D8-4)

- **Self-protection:** `access.service.refuse_self` returns `403` and records `member.self_action_refused` for suspension, revocation, campus-scope changes and role removal on the caller's own membership.
- **Last owner:** `access.service.keep_an_owner` is called before suspending or revoking an `ACTIVE` member and before removing the owner role. When the membership is an `ACTIVE` owner, it:
  1. takes a per-tenant transaction advisory lock (`pg_advisory_xact_lock(70080001, hashtext(tenant_id))`);
  2. counts the other `ACTIVE` memberships holding the `INSTITUTE_OWNER` system role;
  3. returns `409` when there are none.

The owner template is referenced through `OWNER_TEMPLATE`, never by name.

### 6. API (`/api/v1`, tenant realm, one `require_permission` per route)

| Route | Permission |
|---|---|
| `GET /institute` | `tenant.profile.read` |
| `GET /campuses`, `GET /campuses/{id}` | `campus.read` (campus-scoped; another campus or tenant: `404`) |
| `POST /campuses` | `campus.create` (tenant-wide) |
| `PATCH /campuses/{id}` (name, version) | `campus.update` (campus-scoped) |
| `GET /members`, `GET /members/{id}` | `member.read` |
| `POST /members/invitations`, `POST /members/{id}/invitation/resend`, `POST /members/{id}/reinvite` | `member.invite` |
| `POST /members/{id}/suspend`, `/reinstate` | `member.suspend` |
| `POST /members/{id}/revoke` | `member.revoke` |
| `PUT /members/{id}/campus-scope` | `member.update` |
| `POST /members/{id}/roles`, `DELETE /members/{id}/roles/{role_id}` | `role.assign` |
| `GET /roles`, `GET /roles/{id}`, `GET /permissions` | `role.read` |
| `POST /roles`, `PATCH /roles/{id}`, `DELETE /roles/{id}?version=` | `role.create`, `role.update`, `role.delete` |
| `GET /audit-events` | `audit.read` (tenant) |

No new permissions and no step-up: tenant MFA is optional (D6).

### 7. Campuses, roles and the institute summary

- **Campuses** use `TenantScopedRepository` (T01-03) in the request transaction.
  - The code is upper case, unique per tenant and immutable; renames are versioned.
  - Campus status and archival are not defined yet (INC-40 stays open).
- **Roles** are thin routes over the T01-05 access service: custom roles only, system roles immutable (D-B2), no escalation.
- **Institute summary** (name, status, trial flag) is read-only; it belongs to the platform (T01-07).

### 8. Development seed (D16)

- `python -m app.cli seed [--file]` loads `database/seeds/dev.json` as the system realm.
- **Contents:** institutes (`TRIAL`/`ACTIVE`), campuses, system roles, `ACTIVE` members with credentials, and the owner pointer.
- **Rules:**
  - `.example` emails only;
  - random passwords printed once, never stored in the file, logged or audited;
  - refused when an email already exists, and refused unless `APP_ENV=development`.

### 9. Static enforcement

- Only `identity/members.py` publishes the invitee key.
- The identity module never deletes identity rows.
- Member administration never touches sessions.
- Route coverage requires one permission on every new route.

### 10. Refinements

1. **Campus scope without DELETE.** The review assumed DELETE on `membership_campuses`. T01-04 decision D16 (ADR-0015, "Grants") forbids DELETE on identity tables. A campus leaving a selection is therefore marked `removed_at`, and every reader of permitted campuses ignores marked rows (`identity.repository`, member reads). Re-adding a campus clears the mark.
2. **The owner role and the no-escalation rule.** An Administrator (no `role.delete`) cannot remove the owner role at all: the T01-05 no-escalation rule gives `403` before D8-4. The last-owner `409` therefore applies to callers who hold every owner permission (for example through a custom role), and to suspension and revocation by Administrators.
3. **Reinstatement and re-invitation** restore the member's existing roles. They are not role grants, so the no-escalation rule does not apply.
4. **Owner definition.** The protected set is exactly D8-4: an `ACTIVE` membership holding the `INSTITUTE_OWNER` system role, whatever its campus scope.

## Consequences

- Tenant administrators can run their institute's members, roles and campuses. The screens are Phase 03.
- Platform-written events no longer reach tenant readers (closes the ADR-0018 consequence).
- `membership_campuses` keeps a history of removed campuses; a later cleanup would be a system-realm job.

## Alternatives considered

- **DELETE on `membership_campuses`:** it contradicts T01-04 D16 (§10.1).
- **Filtering audit visibility only in the query:** rejected by D8-2.
- **Revoking sessions on suspension:** rejected by D8-3 (other institutes' access).
