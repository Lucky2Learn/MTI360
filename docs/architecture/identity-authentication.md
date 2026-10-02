# Tenant Identity & Authentication (T01-04) — Decision Record and Contract

- **Status:** Pre-implementation. This record holds the T01-04 decisions that are **locked** so that the backend (T01-04) and the frontend (T01-09) build against the same contract. The other decisions of the T01-04 second-pass architecture review (D01–D18) are **not yet approved**; T01-04 records them here, and in its ADR, when they are.
- **Related:** [ADR-0005](../adr/0005-identity-and-session-realms.md), [ADR-0006](../adr/0006-api-prefixes.md), [ADR-0010](../adr/0010-sessions-credentials-and-csrf.md), [ADR-0014](../adr/0014-tenancy-core.md), [tenancy.md](tenancy.md) §5, [security.md](security.md) §2, [backend-foundation.md](backend-foundation.md) §7, UI contract [T01-04-IDENTITY-AUTHENTICATION-UI.md](../ui/T01-04-IDENTITY-AUTHENTICATION-UI.md)

## 1. Decision register

| ID | Decision | Status |
|---|---|---|
| D04 | Campus selection semantics (§2) | **Locked** (2026-10-02) |
| D19 | Invitation preview (§3) | **Locked** (2026-10-02) |
| D01–D03, D05–D18 | Remaining T01-04 review decisions (pre-authentication lookup path, authentication transactions, membership discovery, invitation TTL, blocklist, Argon2 parameters, client IP, Redis namespace, compose/CI, SMTP, guard access mode, login security-event attribution, anonymous CSRF, link building, read-only grants, thresholds, status correction) | Open — approved and recorded by T01-04 |

## 2. D04 — Campus selection semantics

### 2.1 Rules

The **permitted campuses** of a membership are:

| `campus_scope` | Permitted campuses |
|---|---|
| `ALL` | Every campus of the membership's tenant |
| `SELECTED` | The campuses listed in `membership_campuses` for the membership |

The session's **active campus** (`user_sessions.active_campus_id`) follows these rules:

1. **All-campus scope.** For `ALL`, `NULL` means "all campuses". It is a valid, complete state: no campus step is required.
2. **Exactly one permitted campus** (either scope) is selected automatically when an institute becomes active (login with one usable membership, or a tenant switch).
3. **`SELECTED` with two or more permitted campuses** and no active campus requires a campus choice. The session is in the **campus selection required** state until one is chosen.
4. **`ALL` with two or more campuses** starts at `NULL` ("All campuses"). Choosing a single campus is optional (through the campus switcher), and `NULL` can be chosen again.
5. **`SELECTED` never uses `NULL`.** There is no session-level "all my selected campuses" aggregate. Cross-campus reporting is a permission matter (PRD.md §12, T01-05), not a session state.
6. **`SELECTED` with no permitted campus** makes the membership **not usable**. It is excluded from the institutes the person can choose, like a suspended membership. The database cannot prevent a `SELECTED` membership with zero rows, so the domain enforces it.
7. **Options come only from the server.** They are computed from the membership and the active tenant, and a campus of another tenant can never be an option. RLS on `campuses` (ADR-0014) and the composite foreign key `(active_tenant_id, active_campus_id) → campuses(tenant_id, id)` enforce this in the database as well.
8. **Re-validation on every request.** If the active campus is no longer permitted (removed from the selection, or the scope changed), session resolution clears it and re-applies rules 1–3. Under `SELECTED`, that can return the session to "campus selection required".
9. **The request context does not change mid-request.** A campus switch updates the session row. The new campus applies from the **next** request; the current request's `RequestContext` keeps the campus it started with (ADR-0014 §3).
10. **No session rotation on a campus switch** (a campus is not an authentication boundary). A tenant switch rotates the session (ADR-0010 §1) and re-applies rules 1–3 for the new tenant.

### 2.2 Access while a campus choice is required

A session in **campus selection required** may only use the routes available to a session without an institute: `GET /api/v1/session`, `PUT /api/v1/session/tenant`, `PUT /api/v1/session/campus` and `POST /api/v1/auth/logout`. Every other tenant route answers `AUTHENTICATION_REQUIRED`, as it does for a session without an institute. Data of a `SELECTED` membership is never served without a chosen campus.

### 2.3 Session read: campus fields (`GET /api/v1/session`)

| Field | Type | Meaning |
|---|---|---|
| `active_campus` | `{id, name, code}` or `null` | `null` means "All campuses" when `all_campuses_allowed`, otherwise "not chosen yet" |
| `campus_options` | list of `{id, name, code}`, sorted by name | The permitted campuses of the active membership; empty when there is no active institute |
| `all_campuses_allowed` | boolean | `true` only for `ALL` scope with two or more campuses |
| `campus_selection_required` | boolean | `true` only in state 3 above |

The raw `campus_scope` value and the membership ID are **not** returned; the UI needs only the derived fields.

### 2.4 `PUT /api/v1/session/campus`

| Aspect | Contract |
|---|---|
| Realm / authentication | Tenant realm; a valid session with an active institute |
| CSRF | Required (`X-CSRF-Token`, ADR-0010 §5) |
| Body | `{"campus_id": "<uuid>" \| null}` (`RequestModel`, `extra="forbid"`: any other field, such as `tenant_id`, is a `VALIDATION_ERROR`) |
| Success | `200` with the updated session read (§2.3) |
| Not permitted | Any value outside the current options returns `404 NOT_FOUND` with the standard envelope. That covers a campus of another tenant, an unknown ID, a campus outside a `SELECTED` scope, and `null` when `all_campuses_allowed` is false. The response never reveals whether the campus exists |
| Effect | Updates `active_campus_id`; the new campus applies from the next request (rule 9); no rotation (rule 10) |
| Audit | Security event `auth.campus.switched`, target `campus` (or none for "All campuses"), in the T01-02 post-request flush |

## 3. D19 — Invitation preview

### 3.1 Why

The invitation screen (AUTH-06) must know, before it asks for a password, whether the invitation can be used and whether the invited email already has an MTI 360 account. Without that, it would either ask an existing user for a "new password" (implying the password changes) or fail only after the person typed one.

### 3.2 Contract

`POST /api/v1/auth/invitations/preview`

| Aspect | Contract |
|---|---|
| Realm / authentication | Tenant realm, anonymous (`Access.ANONYMOUS`) |
| CSRF | No session token (there may be no session). Subject to the Origin check for anonymous unsafe routes (T01-04 review D14) |
| Body | `{"token": "<string>"}`; `RequestModel` (`extra="forbid"`), the length bounded to the token format |
| Success | `200` `{"data": {"institute_name": "…", "email_masked": "r•••@westernmaritime.edu", "account": "new" \| "existing"}}` |
| Unusable invitation | `404 NOT_FOUND`, one generic response for an unknown token, an expired invitation, an accepted invitation and a revoked invitation (membership no longer `INVITED`, tenant not accessible under the T01-03 status policy, or user `DISABLED`) |
| Rate limiting | Per IP, like the other anonymous authentication routes; `429 RATE_LIMITED` |
| Side effects | None. The preview is read-only: it does not consume the token, change any state or create a session |
| Audit | None for a successful preview. Abuse is limited by rate limiting |

**Why `POST` and not `GET /api/v1/auth/invitations/{token}`:** the request log records the full URL path of every request (`request.completed`, backend-foundation.md §8, `app/core/middleware.py`). A token in the path would be written to the logs, reverse-proxy logs and browser history. In a `POST` body it is never logged, because request bodies are not logged.

### 3.3 What the response may and may not contain

| Returned | Never returned |
|---|---|
| `institute_name`: the tenant name, already known to the invitee from the invitation email | Tenant, membership, invitation or user IDs; tenant status; other memberships of the email |
| `email_masked`: first character of the local part, `•••`, full domain. Masked by the server | The full email address, the display name, roles, the inviter |
| `account`: `new` (no user with a credential) or `existing` | Password, credential, lockout or session information; whether the person is signed in; expiry time |

**Account enumeration.** `account` tells the token holder whether the invited email already has an account. That is not enumeration: only someone with a valid, unexpired invitation token (sent to that email address) can ask, the answer concerns only the invited email, and unknown tokens get the same `404` as every other unusable invitation.

### 3.4 Acceptance contract consequences

`POST /api/v1/auth/invitations/accept`:

| Account | Required body | Rejected |
|---|---|---|
| `new` | `token`, `display_name` (1–200), `password` (ADR-0010 §7 policy) | none |
| `existing` | `token` | `password` or `display_name` present → `VALIDATION_ERROR`. **An existing credential is never overwritten** |

- Acceptance activates the membership (`INVITED` → `ACTIVE`, `joined_at`) and marks the invitation accepted. For a new account it also sets the user `ACTIVE` with `email_verified_at` and creates the credential.
- It does **not** sign the person in and does not change any existing session.
- Unusable invitations get the same `404 NOT_FOUND` as the preview.
- Audit: `auth.invitation.accepted`.

### 3.5 Token handling (both endpoints)

- The token arrives only in the body. Links use `/accept-invitation#token=…`, so the browser never sends it to the frontend server (UI contract §6.1).
- It is looked up by its hash (stored hashed, never in plain text).
- It is never logged, never echoed in a response or error, and never put in audit metadata.
- The lookup uses the pre-authentication lookup path that T01-04 approves (review D01). This contract does not depend on which option is chosen.
