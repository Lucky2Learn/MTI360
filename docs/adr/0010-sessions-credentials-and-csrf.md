# ADR-0010 — Sessions, Credentials and CSRF

- **Status:** Accepted (T01-00 approval, decisions D2, D3, D11, D12, D14 as amended, D19; implementation in T01-04 and T01-06)
- **Date:** 2026-09-30
- **Task:** T01-00 (recorded in T01-01)
- **Related:** [ADR-0005](0005-identity-and-session-realms.md) (refined, not superseded), [ADR-0004](0004-tenant-isolation.md), [security.md](../architecture/security.md), [backend-foundation.md](../architecture/backend-foundation.md)

## Context

ADR-0005 chose opaque, revocable server-side sessions with distinct `__Host-` cookies per realm, CSRF protection and a separate platform identity. It left four points open:

- where sessions are stored;
- how tokens are protected at rest;
- how credentials relate to the identity record;
- how brute force is limited.

The T01-00 review proposed answers, and the user approved them with one amendment: **user identity must be separated from authentication credentials (D14)**.

## Decision

1. **Session store: PostgreSQL (D2).**
   - `user_sessions` holds the tenant and student realms: the user, the realm, the active tenant and campus, MFA state, idle and absolute expiry, and revocation.
   - `platform_sessions` holds the platform realm.
   - A session token is 256 random bits. The database stores only `HMAC-SHA256(SESSION_SECRET, token)`, so a leaked table yields no usable sessions.
   - The session ID rotates on login, MFA completion, tenant switch and privilege change.
   - There are no refresh tokens; revocation is a row update.
   - A Redis cache is added only if measurements require it.
2. **Identity is separated from credentials (D14, amended).**

   | Table | Holds | Never holds |
   |---|---|---|
   | `users` (identity) | id, email, display name, status, `email_verified_at`, timestamps | password hash, lockout counters, MFA secrets, tokens |
   | `user_credentials` (1:1 with `users`) | `password_hash` (Argon2id), `password_changed_at`, `failed_login_count`, `locked_until` | profile data |
   | `platform_users` / `platform_user_credentials` | the same split for the platform realm | — |

   Rules:
   - Only the authentication services of the `identity` and `platform_identity` modules read or write credential tables.
   - No API schema, generic repository, list or join exposes them.
   - Identity queries (members, audit actors, admin screens) never load a credential row.
   - MFA factors, recovery codes, reset tokens and invitation tokens are further credential tables (hashed or encrypted, ADR-0012).
   - Adding SSO or passkeys later adds credential types without changing the identity table.
3. **Cross-tenant identity (D14).**
   - `users` is one global identity per person.
   - RLS limits a `users` row to the person themselves or to members of the current tenant.
   - A tenant administrator manages only tenant-local data: membership, roles and campus scope. They can never change another user's email or credentials. A user who belongs to another tenant owns their own identity.
4. **Cookies (D19):**
   - `__Host-mti360_tsid` (tenant), `__Host-mti360_psid` (platform), `__Host-mti360_ssid` (student, reserved).
   - All are `HttpOnly`, `Secure`, `SameSite=Lax` and `Path=/`.
5. **CSRF protection.**
   - Unsafe methods require an `X-CSRF-Token` header equal to `HMAC(CSRF_SECRET, session id)`, delivered by `GET /session`.
   - This is in addition to SameSite cookies and the same-origin proxy.
6. **Brute force (D3).**
   - Redis rate limits per IP and per account on authentication endpoints.
   - A progressive lockout (`failed_login_count`, `locked_until`) on the credential row.
   - Generic responses and equalised timing.
7. **Passwords (D11, D12).**
   - Email is the only login identifier.
   - Passwords are 12–128 characters, checked against a bundled common-password blocklist, with no composition rules.
   - An external breached-password check is deferred.

## Consequences

- A session lookup costs one indexed query per request; the table supports "active sessions" views and immediate revocation.
- The credential split adds one join at login only, and gives a hard boundary for grants and reviews.
- `SESSION_SECRET` and `CSRF_SECRET` (validated since T00-04) gain their consumers in T01-04.

## Alternatives considered

- **Redis session store:** faster and TTL-native, but not durable or auditable, and harder to list and revoke per user. Kept only as an optional cache.
- **Password hash on `users`:** simpler, but every identity query would touch credential data, and grants could not separate them. Rejected by the D14 amendment.
- **JWT access with refresh tokens:** rejected in ADR-0005.
