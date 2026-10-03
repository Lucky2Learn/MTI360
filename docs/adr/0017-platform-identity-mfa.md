# ADR-0017 — Platform Identity and MFA Implementation

- **Status:** Accepted (T01-06)
- **Date:** 2026-10-03
- **Task:** T01-06
- **Related:** [platform-identity.md](../architecture/platform-identity.md) (locked decisions D6-1 … D6-5), [ADR-0005](0005-identity-and-session-realms.md), [ADR-0010](0010-sessions-credentials-and-csrf.md), [ADR-0012](0012-application-level-encryption.md), [ADR-0013](0013-audit-events.md), [ADR-0015](0015-identity-authentication.md), [ADR-0016](0016-authorization-rbac.md)

## Context

The T01-06 architecture review locked D6-1 … D6-5 (first administrator CLI, platform password recovery, lost-MFA reset, TOTP plus recovery codes, step-up). This ADR records how they were implemented. It does not change them.

## Decision

### 1. Schema and RLS (migration `0006`)

- **Platform realm:** `platform_users`, `platform_user_credentials`, `platform_user_roles` (the seven fixed T01-05 codes), `platform_sessions` (MFA-pending until `mfa_verified_at`), `platform_mfa_factors` (encrypted secret, `last_used_step`, one live factor per user), `platform_recovery_codes` (HMAC) and `platform_password_reset_tokens`. There is no link to `users`: the same email may exist in both realms.
- **Tenant optional MFA:** `user_mfa_factors`, `user_recovery_codes`, and `user_sessions.mfa_pending` / `mfa_failed_attempts`. A pending session has no tenant.
- **RLS** is keyed on `app.realm = 'platform'`, `app.platform_user_id` (published by `context_transaction` for platform principals) and equality-matched lookup keys (email, reset-token hash, session-token hash, MFA-reset target). Only `platform_identity.lookup` publishes those keys; a static test enforces it. Credentials, factors, codes, sessions and reset tokens are own-row only. Tenant contexts and `mti_readonly` see nothing. No `SECURITY DEFINER`.
- The downgrade revokes live MFA-pending tenant sessions first, so it never turns them into sessions that skipped MFA.

### 2. Encryption, TOTP and recovery codes (D6-4)

- `app.core.security.encryption`: AES-256-GCM, `v1:<key-id>:<nonce>:<ciphertext>`, with `<table>:<row id>` as associated data. `DATA_ENCRYPTION_KEY` (base64 of 32 bytes) and `DATA_ENCRYPTION_KEY_ID`; `DATA_ENCRYPTION_RETIRED_KEYS` are decrypt-only. The key is required outside development; development uses a public development-only key.
- `app.core.security.totp`: RFC 6238 on the standard library (SHA-1, 6 digits, 30 s, ±1 step), returning the matched step, tested against the RFC vectors. Manual setup only: the secret and the `otpauth://` URI, no QR dependency.
- `app.core.security.mfa.MfaStore` is realm-neutral and works on each realm's own tables: enrolment, confirmation, verification with an atomic `last_used_step` update (replay protection), ten single-use HMAC recovery codes bound to their owner, replacement and disabling. An undecryptable secret fails closed.
- Dependency: `cryptography`. `pyotp` is not used.

### 3. Platform authentication and sessions

| Route | Access |
|---|---|
| `POST /api/v1/platform/auth/login`, `/logout`, `/password-reset`, `/password-reset/confirm` | `public_route` (same-origin check) |
| `POST /api/v1/platform/auth/mfa/enrolment`, `/enrolment/confirm`, `/verify`, `/recovery` | `Access.MFA_PENDING` + CSRF |
| `GET /api/v1/platform/session`, `POST /session/step-up` | `authenticated_only` (CSRF on POST) |
| `POST /api/v1/platform/session/mfa/recovery-codes` | `authenticated_only`, fresh step-up required |

- **Sign-in:** a generic 401, the dummy hash for unknown accounts, Redis limits in the `auth:platform` namespace and the database lockout. The password opens an MFA-pending session (`__Host-mti360_psid`, 5 minutes, no permissions). Enrolment returns the secret and URI once; confirmation returns the recovery codes once. TOTP or a recovery code completes sign-in, rotates the session and sets `mfa_verified_at`. Five wrong codes revoke the pending session; wrong codes also count toward the lockout.
- **Permissions** come from `platform_user_roles` through the T01-05 role map. No second role system.
- **Session read:** status, MFA state, roles, permissions, `step_up_expires_at` and the CSRF token; no internal IDs.
- **Password reset (D6-2):** the T01-04 model with platform tables and templates. A reset ends every session and never touches MFA.

### 4. Step-up (D6-5)

`RequestContext.mfa_verified_at`. `authorize()` checks the permission first, then, for `requires_step_up` permissions, an MFA verification within `STEP_UP_WINDOW` (10 minutes); otherwise `403 STEP_UP_REQUIRED` (`authz.step_up_required`). `tenant.suspend`, `tenant.reactivate`, `platform_user.create` and `platform_user.update` are declared `requires_step_up`. `POST /session/step-up` takes a TOTP code and refreshes `mfa_verified_at`.

### 5. Lost-MFA reset (D6-3)

`PlatformIdentityService.reset_mfa(target, reason)`: `platform_user.update` with step-up, a reason of 1–500 characters, never one's own account. It disables the factor and recovery codes, revokes the target's sessions and records `platform.mfa.reset` with the actor and reason. The next sign-in requires enrolment. The HTTP route belongs to T01-07.

### 6. Tenant MFA (optional)

On the existing identity model: opt-in enrolment and confirmation (`/api/v1/session/mfa/enrolment`, `/enrolment/confirm`), removal with a current code (`/session/mfa/remove`), and `/api/v1/auth/mfa/verify` and `/recovery` on an MFA-pending session. Institute and campus resolution happens after MFA. Users without MFA are unaffected.

### 7. Bootstrap (D6-1)

`python -m app.cli create-platform-admin --email … --display-name …` creates the first `SUPER_ADMIN`. It is refused while an active one exists or the email is taken. `--break-glass --reason …` resets an existing account's password, clears its MFA and revokes its sessions, or creates a new `SUPER_ADMIN`. The password comes only from a no-echo prompt (entered twice) and is never printed, logged or audited.

### 8. Audit

Security events `platform.auth.*` and `platform.mfa.*` for sign-in, lockout, logout, session rotation and revocation, MFA enrolment, verification and failure, recovery-code use and regeneration, MFA reset, step-up, password reset and rate limiting; tenant `auth.mfa.*` equivalents. Metadata never contains passwords, secrets, codes, tokens or emails.

## Consequences

- Platform users exist, but there is no platform user management API (T01-07) and no screen (T01-09).
- A platform session reaches no tenant data until support sessions (Phase 02).
- Rotating `DATA_ENCRYPTION_KEY` needs the old key in `DATA_ENCRYPTION_RETIRED_KEYS` until factors are re-encrypted; no re-encryption job exists yet.

## Alternatives considered

- **`pyotp`:** not needed; RFC 6238 is small and tested against the RFC vectors.
- **A QR-code library:** deferred by the locked decisions.
- **One session table for both realms:** rejected by ADR-0005/ADR-0010.
