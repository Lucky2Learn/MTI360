# Tenant Identity & Authentication (T01-04) — Decision Record and Contract

- **Status:** Implemented in T01-04 (branch `feat/T01-04-identity-authentication`). All decisions D01–D19 are locked; the architecture is recorded in [ADR-0015](../adr/0015-identity-authentication.md). The frontend (T01-09) builds against this contract and the frozen UI contract.
- **Related:** [ADR-0015](../adr/0015-identity-authentication.md), [ADR-0005](../adr/0005-identity-and-session-realms.md), [ADR-0006](../adr/0006-api-prefixes.md), [ADR-0010](../adr/0010-sessions-credentials-and-csrf.md), [ADR-0014](../adr/0014-tenancy-core.md), [tenancy.md](tenancy.md) §5, [security.md](security.md) §2, [backend-foundation.md](backend-foundation.md) §7, UI contract [T01-04-IDENTITY-AUTHENTICATION-UI.md](../ui/T01-04-IDENTITY-AUTHENTICATION-UI.md)

## 1. Decision register

| ID | Decision | Status |
|---|---|---|
| D01 | Pre-authentication lookups: one `SET LOCAL` key per lookup transaction, equality policies, no `SECURITY DEFINER` (ADR-0015 §1) | Locked, implemented |
| D02 | Explicit sequential transactions; Argon2 outside transactions (ADR-0015 §2) | Locked, implemented |
| D03 | Membership discovery in the identity repository; Core statements with explicit predicates before a tenant is active | Locked, implemented |
| D04 | Campus selection semantics (§2) | Locked, implemented |
| D05 | Invitations: 7 days, `invited_by` nullable, existing credentials never overwritten, no automatic sign-in | Locked, implemented |
| D06 | Common-password blocklist: SecLists 10k (MIT, pinned commit; §5) | Locked, implemented |
| D07 | Argon2id via `argon2-cffi`, configurable, rehash detection | Locked, implemented |
| D08 | `TRUSTED_PROXY_HOPS` (default 0) | Locked, implemented |
| D09 | Redis rate limits in a dedicated `auth:` namespace | Locked, implemented |
| D10 | Compose `api` gets `REDIS_URL` and Mailpit; CI starts Redis | Locked, implemented |
| D11 | Stdlib SMTP `EmailSender` with a bounded timeout, plus a fake | Locked, implemented |
| D12 | `Access.SESSION` (§4.2) | Locked, implemented |
| D13 | Sign-in security events in the anonymous context; user as target | Locked, implemented |
| D14 | CSRF token on session routes; same-origin check on anonymous routes | Locked, implemented |
| D15 | `APP_BASE_URL`; plain-text emails; tokens only in URL fragments and bodies | Locked, implemented |
| D16 | No read-only access to identity tables; no DELETE | Locked, implemented |
| D17 | 20/IP/5 min, 10/account/15 min, lockout 1/5/15/60 min, fail closed, `Retry-After` | Locked, implemented |
| D18 | T01-03 status correction | Done (TASKS.md, DEVELOPMENT-STATUS.md) |
| D19 | Invitation preview (§3) | Locked, implemented |

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

## 4. Implementation (T01-04)

### 4.1 Code

| Area | Location |
|---|---|
| Models, domain rules, tokens, passwords, lookup and subject transactions, repository, services, schemas, routes, security events, email templates | `backend/app/modules/identity/` |
| Bundled blocklist and its licence | `backend/app/modules/identity/data/common-passwords.{txt,LICENSE}` |
| Rate limiter (Redis, fail closed) | `backend/app/core/ratelimit.py` |
| Client IP behind trusted proxies | `backend/app/core/net.py` |
| `EmailSender`, SMTP adapter, fake | `backend/app/integrations/email/` |
| Session resolution, access levels, CSRF and origin checks | `backend/app/api/realms.py` (guard), `backend/app/api/tenant.py` (mounting) |
| Migration | `backend/migrations/versions/0004_identity_authentication.py` |

### 4.2 API

All routes are in the tenant realm (`/api/v1/*`); request bodies reject unknown fields.

| Route | Access | Integrity check | Success | Failures |
|---|---|---|---|---|
| `POST /auth/login` `{email, password}` | Anonymous | Same origin | `200` session read + cookie | `401` generic, `422`, `429` (+`Retry-After`), `503` |
| `POST /auth/logout` | Anonymous (revokes the presented session, if any) | Same origin | `204`, cookie cleared (always) | — |
| `POST /auth/password-reset` `{email}` | Anonymous | Same origin | `202` (always) | `422`, `429`, `503` |
| `POST /auth/password-reset/confirm` `{token, new_password}` | Anonymous | Same origin | `204` | `404` generic, `422` (`password_too_short` / `_long` / `_common`), `429` |
| `POST /auth/invitations/preview` `{token}` | Anonymous | Same origin | `200` `{institute_name, email_masked, account}` | `404` generic, `429` |
| `POST /auth/invitations/accept` `{token, display_name?, password?}` | Anonymous | Same origin | `204` (no sign-in) | `404` generic, `422`, `429` |
| `GET /session` | Session | — | `200` session read | `401` |
| `PUT /session/tenant` `{tenant_id}` | Session | `X-CSRF-Token` | `200` session read + rotated cookie | `404`, `401` |
| `PUT /session/campus` `{campus_id or null}` | Session (needs an active institute) | `X-CSRF-Token` | `200` session read | `404`, `401` |

Session read: `status` (`ready`, `institute_selection_required`, `campus_selection_required`), `user {display_name, email}`, `active_institute`, `institutes [{id, name, is_trial}]`, `active_campus`, `campus_options`, `all_campuses_allowed`, `campus_selection_required`, `csrf_token`.

New error codes: `SESSION_REFRESH_REQUIRED` (403) for a failed CSRF or same-origin check (the UI contract's OQ-5 default already treats any `403` from `/auth/*` and `/session/*` this way), and `SERVICE_UNAVAILABLE` (503) when Redis cannot protect a sign-in.

### 4.3 Data and Row-Level Security

The tables are `users`, `user_credentials`, `tenant_memberships`, `membership_campuses`, `user_sessions`, `password_reset_tokens` and `user_invitations`.

- RLS is enabled on every table (not forced), and there are no `SECURITY DEFINER` functions.
- `mti_app` has SELECT, INSERT and UPDATE (`membership_campuses`: SELECT and INSERT). There is no DELETE anywhere, and `mti_readonly` has no access.

| Table | Visible to |
|---|---|
| `users` | Own row (`app.user_id`), members of the active tenant, the email lookup key, system. Updates: own row or system. Inserts: system only (identities are created by provisioning and administration, T01-07/T01-08, or the seed) |
| `user_credentials` | Own row, the email lookup key, system. **Never** a tenant context |
| `tenant_memberships` | Active tenant, own memberships (tenant discovery), the invitation token key, system |
| `membership_campuses` | Active tenant, own memberships, system |
| `user_sessions` | Own sessions, the session token key, system |
| `password_reset_tokens` | Own, the reset token key (read), system |
| `user_invitations` | Active tenant, the invitation token key (read), system |
| `tenants` (new `tenants_member_read`) | Tenants of the user's own memberships, and the tenant of the invitation being looked up |

Composite foreign keys keep a membership campus inside its membership's tenant, a session's active tenant among the user's memberships, and its active campus inside the active tenant.

### 4.4 Deviations and clarifications

- **Sign-out is an anonymous route** with the same-origin check. It revokes the presented session if there is one. D12 allowed it on `Access.SESSION`, but the frozen UI contract requires sign-out to answer `204` even without a valid session; an anonymous route gives both.
- **`PUT /session/campus` is a session route**, as D04 §2.2 requires: a user whose campus choice is pending can only reach session routes.
- **Invited people already have a `users` row** (`INVITED`) when they are invited. The membership references it, and the inviter (T01-07/T01-08) creates it. Accepting a "new account" invitation activates that row, sets the name and creates the credential. An "existing account" is one with a credential.
- **The identity repository reads the `tenants` and `campuses` tables directly** (joins for institute choices and campus options) instead of calling those modules' services, which do not exist yet. This is a read-only, documented exception to "modules call each other only through services".
- **The request middleware clears the request context when the request ends** (`clear_context`). Found by the T01-04 tests: when the application runs in the caller's task (tests, ASGI transports), the context bound by the realm guard would otherwise outlive the request.

## 5. Password blocklist provenance

| Item | Value |
|---|---|
| Source | SecLists, `Passwords/Common-Credentials/10k-most-common.txt` |
| Repository | https://github.com/danielmiessler/SecLists |
| Commit | `913b327317496d062bcc7cace524aaad8a693be2` (2026-09-08) |
| SHA-256 | `68782d6a4a19a4768d5f15dd66bd534e7a33055cc755411e33f16d18c50fdcce` |
| Licence | MIT (Copyright (c) 2018 Daniel Miessler), reproduced in `common-passwords.LICENSE` |
| Use | Unmodified; compared case-insensitively after the 12–128 length rule |

Only 10 entries are 12 characters or longer, so the length rule rejects almost all of the list on its own (INC-42).
