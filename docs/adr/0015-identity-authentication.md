# ADR-0015 — Tenant Identity and Authentication: Pre-Authentication Lookups and Session Resolution

- **Status:** Accepted (T01-04 locked decisions D01–D19; refines ADR-0005 and ADR-0010)
- **Date:** 2026-10-02
- **Task:** T01-04
- **Related:** [ADR-0004](0004-tenant-isolation.md), [ADR-0005](0005-identity-and-session-realms.md), [ADR-0010](0010-sessions-credentials-and-csrf.md), [ADR-0013](0013-audit-events.md), [ADR-0014](0014-tenancy-core.md), [identity-authentication.md](../architecture/identity-authentication.md), UI contract [T01-04-IDENTITY-AUTHENTICATION-UI.md](../ui/T01-04-IDENTITY-AUTHENTICATION-UI.md)

## Context

ADR-0010 chose PostgreSQL sessions stored as an HMAC of the token, identity separated from credentials, CSRF tokens bound to the session, Redis rate limits and a database lockout. ADR-0014 protects every tenant table with Row-Level Security that reads only the trusted, transaction-local `SET LOCAL` context.

Authentication has to read identity rows **before** the request has a user or a tenant: a user and credential by email at sign-in, a session by its token on every request, and a reset or invitation token by its hash. Under the intended policies ("own identity or a member of the active tenant") none of these rows is visible at that moment. The T01-04 review (D01) ruled out three ways round this:

- weakening or disabling RLS;
- `SECURITY DEFINER` lookup functions;
- reusing `system_context`, which is refused inside HTTP requests by ADR-0014.

## Decision

### 1. Pre-authentication lookup keys (D01)

The identity module publishes **one** extra trusted setting with `SET LOCAL` in a short **lookup transaction** (`app/modules/identity/lookup.py`):

| Setting | Value | Reaches |
|---|---|---|
| `app.auth_email` | The canonical email | That user and that user's credential |
| `app.auth_token_hash` | HMAC of a reset or invitation token | That token row; for an invitation, also its membership and the tenant name |
| `app.session_token_hash` | HMAC of the presented session token | That session row (read, and revoke at sign-out) |

- Policies match each key **by equality** (migration `0004`), so a key can reach only the row it names. It can never list users or read a tenant's data.
- Values are computed by the server: a canonical email, or an HMAC of the presented token under `SESSION_SECRET` with a purpose prefix. No client-supplied hash, tenant or user ID is ever used.
- Only the lookup module names these settings, and a test enforces it.
- Once a lookup has resolved *who* the operation concerns (a verified password, a valid session or token), the work continues in a **subject transaction** as that user, and optionally a tenant, through the ordinary `app.user_id` / `app.tenant_id` policies.

### 2. Explicit sequential transactions (D02)

- Sign-in, reset, invitation and session resolution use short `context_transaction`s one after another, never two at once, and never `DbSession`.
- Argon2id runs **between** transactions, so no connection is held during the slow hash.
- A failed sign-in therefore commits its lockout counter while the response is a 401.
- The session read and the campus switch, which run with a resolved context, use the request's `DbSession`.

### 3. Session resolution in the realm guard

- For tenant-realm routes the guard resolves the `__Host-mti360_tsid` cookie **on every request**. It checks the token hash, revocation, idle and absolute expiry, the user's status, the membership, the tenant status (T01-03 policy) and the campus (D04).
- It applies corrections (a withdrawn campus, a membership no longer usable) and builds the request's `RequestContext` (`principal_id`, `tenant_id`). This happens in its own short transactions, before the request transaction.
- The context is never changed during a request: a tenant or campus switch applies from the next request.
- Access levels:

  | Access | Requires |
  |---|---|
  | `AUTHENTICATED` | An institute and, for a restricted campus scope, a chosen campus |
  | `SESSION` | Any valid session (`/api/v1/session*`) |
  | `ANONYMOUS` | Nothing (sign-in, reset, invitations, sign-out) |

### 4. Browser request integrity (D14)

- Unsafe methods on session routes need `X-CSRF-Token = HMAC(CSRF_SECRET, session id)` (ADR-0010 §5).
- Unsafe anonymous tenant routes need a same-origin signal: `Origin` in the allow-list (`CORS_ALLOWED_ORIGINS` plus `APP_BASE_URL`), or `Sec-Fetch-Site: same-origin` when there is no `Origin`.
- Failures return `403 SESSION_REFRESH_REQUIRED` and record a security event.

### 5. Other locked parameters

| Decision | Rule |
|---|---|
| Lockout (D17) | 5 failures → 1, then 5, 15, 60 minutes (cap). Never for unknown accounts, and nothing is counted while the account is locked |
| Rate limits (D09, D17) | Redis fixed windows of 20 attempts per IP per 5 minutes and 10 per account per 15 minutes. Keys are `auth:<kind>:<action>:<sha256>`. They fail closed (`503`) and send `Retry-After` on `429` |
| Client IP (D08) | `TRUSTED_PROXY_HOPS` (default 0 ignores `X-Forwarded-For`) |
| Passwords (D06, D07) | Argon2id with configurable parameters and rehash on change. 12–128 characters plus the bundled SecLists 10k blocklist (MIT). No composition rules |
| Sessions | 256-bit tokens. Rotation on sign-in, institute switch and password reset (by revocation). No rotation on a campus switch (D04) |
| Email (D10, D11, D15) | `EmailSender` (stdlib SMTP in a thread with a bounded timeout, plus a fake). Sent after commit and after the response; at most once. Links built from `APP_BASE_URL` with the token in the URL fragment |
| Invitations (D05, D19) | 7 days. `invited_by` nullable. The preview is `POST` with the token in the body. An existing credential is never overwritten. Acceptance never signs in |
| Grants (D16) | No DELETE for the runtime roles on identity tables, and `mti_readonly` has no access to them |
| Audit (D13) | Security events through the T01-02 buffer. In anonymous sign-in contexts the user is the event's target |

## Consequences

- Authentication needs no RLS exception, no definer function and no bypass. Every identity row is still protected by the same mechanism as tenant data, and the raw-SQL tests prove each key reaches one row.
- Each authenticated request costs two short extra transactions (lookup and validation) before the request transaction. Sessions are re-validated in full each time, so disabled users, revoked memberships and suspended tenants take effect immediately. The cost is to be measured before any caching is added.
- Sign-in security events carry no principal or tenant (the request was anonymous). Tenant audit reads (T01-08) will see them only by target.
- The blocklist is the approved 10k list. Only 10 of its entries are 12 characters or longer, so the length rule does most of the work. A larger list can replace the file without code changes.

## Alternatives considered

- **`SECURITY DEFINER` lookup functions:** each lookup would bypass RLS entirely and hide logic in SQL. Rejected (D01).
- **A permissive policy for anonymous tenant-realm contexts:** any bug could list identities. Rejected.
- **One transaction for sign-in:** it would hold a connection during Argon2 and could not keep the lockout counter on failure. Rejected (D02).
- **Rotating the session on campus switches:** the campus is not an authentication boundary, and rotation would break concurrent tabs needlessly. Rejected (D04).
