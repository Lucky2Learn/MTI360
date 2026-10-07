# Platform Identity and MFA

- **Status:** Decisions locked (T01-06 architecture review, 2026-10-02); implemented and verified; merged to `main` by PR #25 (merge commit `9fdb40a`); see [ADR-0017](../adr/0017-platform-identity-mfa.md).
- **Builds on:** [ADR-0005](../adr/0005-identity-and-session-realms.md) (separate platform identity), [ADR-0010](../adr/0010-sessions-credentials-and-csrf.md) (`platform_users` / `platform_user_credentials` / `platform_sessions`, `__Host-mti360_psid`), [ADR-0011](../adr/0011-rbac-model.md) and [ADR-0016](../adr/0016-authorization-rbac.md) (code-defined platform roles, `requires_step_up` hook), [ADR-0012](../adr/0012-application-level-encryption.md) (`DATA_ENCRYPTION_KEY`, AES-256-GCM), T01-00 decision D9 (TOTP and recovery codes; MFA mandatory for platform users).
- **Scope (TASKS.md T01-06):** platform identity, platform sessions and MFA, plus optional MFA enrolment for tenant users. Platform user management (create, suspend, list) belongs to T01-07; the PLAT-01, PLAT-02 and AUTH-04 screens belong to T01-09.

## Locked decisions

| # | Decision |
|---|---|
| **D6-1** | **First platform administrator.** A system-realm CLI, `create-platform-admin`, creates the first `SUPER_ADMIN`. The account must enrol MFA at its first sign-in. The password is entered through a no-echo prompt, never as a command-line argument (shell history). The CLI never logs, prints or otherwise exposes it, including in logs, output and audit metadata. It is also the **break-glass** path when no usable `SUPER_ADMIN` exists. |
| **D6-2** | **Platform password recovery.** Self-service email reset with the T01-04 security model: generic responses, rate limits, a single-use expiring token stored only as an HMAC, no account enumeration, and the token never logged. A reset **never bypasses MFA**: the next sign-in still requires TOTP or a recovery code. |
| **D6-3** | **Lost MFA device.** A `SUPER_ADMIN` may reset another platform user's MFA under the existing permission `platform_user.update`; **no new permission is added**. The operation requires step-up (D6-5) and a reason. It is fully audited, revokes the user's sessions and forces MFA re-enrolment at the next sign-in. The bootstrap CLI (D6-1) remains the break-glass path. |
| **D6-4** | **MFA mechanisms.** T01-06 platform MFA is **TOTP plus recovery codes**. The data model stays extensible for WebAuthn/passkeys: factors are typed credential rows (ADR-0010 §2). **Deferred:** SMS OTP, email OTP, trusted devices, WebAuthn/passkeys and OTP resend. The "Resend" and "Trusted device" elements of PLAT-01/PLAT-02 (UI-SCREENS.md) and "OTP" / "Trusted device" in PLATFORM-ADMIN.md §16 are therefore out of T01 scope. |
| **D6-5** | **Step-up.** `tenant.suspend`, `tenant.reactivate`, `platform_user.create` and `platform_user.update` are declared `requires_step_up`. The freshness window is **10 minutes** after the session's last MFA verification. A stale session receives **`403 STEP_UP_REQUIRED`**. Enforcement stays in the backend authorization engine (`authorize()`), never in the UI. |
| **QR code** | No QR-generation dependency is added in T01-06. Enrolment returns the TOTP secret (shown once) and the `otpauth://` URI for manual setup. |

## Architecture constraints (from the approved review)

- **Realm separation.** Platform and tenant realms never share sessions, cookies, credentials, MFA factors, recovery codes or role tables. A tenant session cannot reach `/api/v1/platform/*`.
- **MFA-pending session.** A correct password creates a restricted, short-lived session that may only enrol, verify, use a recovery code or sign out. It carries no permissions. MFA success rotates the session ID and records `mfa_verified_at`.
- **TOTP.** RFC 6238 (SHA-1, 6 digits, 30-second step, ±1 step). Replay is prevented by an atomic `last_used_step` update. The secret is encrypted with AES-256-GCM, with the row identity bound as associated data. It is never logged, never returned after enrolment and never exported.
- **Recovery codes.** Ten single-use codes, stored only as HMAC hashes and shown once. Regeneration requires step-up.
- **Brute force.** Rate limits per IP, account and session in the `auth:platform:*` namespace. MFA failures count toward the credential lockout.
- **Authorization and RLS.**
  - Platform permissions come from `platform_user_roles` through the code-defined role map (T01-05).
  - The platform context has no tenant, so tenant data stays unreachable until support sessions (Phase 02).
  - Row-Level Security applies to every new table, keyed on the platform realm, `app.platform_user_id`, a platform pre-authentication lookup key and the system realm.
  - The read-only role gets no access. No `SECURITY DEFINER` functions.
- **Audit.** Every sign-in, MFA, recovery, reset, step-up and lockout outcome is a security event. Codes, secrets, tokens and emails never appear in metadata.
