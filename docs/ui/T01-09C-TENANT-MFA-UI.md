# T01-09C Tenant MFA — UI/UX Specification

- **Status:** Implemented in T01-09C. Completes **D9B-9** (tenant MFA enrolment and removal, deferred from T01-09B).
- **Screen:** AUTH-04 MFA (UI-SCREENS.md §14): the sign-in step on `/login` (T01-09A) and the in-shell **Sign-in security** page `/app/account/security` (this task).
- **Builds on:** [ADR-0017](../adr/0017-platform-identity-mfa.md) §6 (tenant MFA: opt-in enrolment and confirmation, removal with a current code, MFA-pending sign-in), [T01-04](T01-04-IDENTITY-AUTHENTICATION-UI.md) §10–§13, [T01-05](T01-05-AUTHORIZATION-RBAC-UI.md) §11 (error matrix), and the T01-09B contract [T01-09B-PLATFORM-IDENTITY-MFA-UI.md](T01-09B-PLATFORM-IDENTITY-MFA-UI.md) (shared components, security rules §11, accessibility §12). Where this document is silent, those apply.

## 1. Locked inputs

| Source | Locked |
|---|---|
| ADR-0017 §6 | Tenant MFA is **optional** (opt-in). Users without MFA are unaffected. There is no "set-up required" sign-in state for tenants |
| D6-4 | TOTP plus ten single-use recovery codes. No SMS/email OTP, resend, trusted devices or passkeys. No QR code |
| ADR-0010 / D9B-10 | Tenant calls carry only `__Host-mti360_tsid`; never the platform cookie |
| T01-05 §11 | 401 → session ended; `SESSION_REFRESH_REQUIRED` → re-read, unsafe requests never resent; `PERMISSION_DENIED` → fixed denial and background re-read |

## 2. Decisions

| ID | Decision |
|---|---|
| **D9C-1** | **Location.** No existing tenant screen hosts a member's own MFA (ADMIN-13/ADMIN-14 are institute administration). Mirroring the accepted platform precedent (D9B-8), the tenant gets a personal **Sign-in security** page at `/app/account/security`, reached from the account menu ("Sign-in security"), not the navigation. Requirement: any ready tenant session — the session MFA endpoints need a session, not a permission, so no permission is added. The page gate is the existing `requireReadyTenantSession` |
| **D9C-2** | **Set-up** runs in Dialogs on the page: an explicit "Set up two-step verification" press starts enrolment (never on mount); the key Dialog shows the shared setup steps (key, Copy key, `otpauth://` link, settings) and the confirm code; Cancel or Escape drops the key; success shows the recovery codes in a non-dismissable Dialog with the shared required acknowledgement and `beforeunload` guard |
| **D9C-3** | **Turning off** is the backend's self-service removal (`POST /session/mfa/remove`), which requires a **current authenticator code** (a recovery code is not accepted). Dialog with a code field and a destructive "Turn off" action |
| **D9C-4** | **The server decides the state.** After every change the page re-reads `GET /session` (`mfa_enabled`); the UI never infers MFA state from its own actions. Set-up does not rotate the session (the backend marks it MFA-verified), so no navigation follows |
| **D9C-5** | **Sign-in step unchanged.** The tenant `mfa_required` step from T01-09A (shared `MfaStep`, TOTP and recovery code) already implements the contract; T01-09C adds tests only |
| **D9C-6** | **Copy.** Every code field in the shell says "Each wrong code counts toward locking your account." (wrong codes count toward the credential lockout; the fifth on a session revokes it) |

## 3. Routes and screens

| Route | Screen | Notes |
|---|---|---|
| `/login` (step) | AUTH-04 sign-in step | T01-09A; in-memory step, never restored after a reload |
| `/app/account/security` | AUTH-04 Sign-in security | New. Account (name, email, institute — read-only) and Two-step verification (status; Set up / Turn off) |

## 4. API mapping (all existing; tenant realm)

| Method and path | Access | CSRF | Request | Response | Errors used | Session effect |
|---|---|---|---|---|---|---|
| POST `/api/v1/auth/mfa/verify` | MFA-pending | yes | `{code}` | `SessionOut` | 422, 401, 429 | rotated |
| POST `/api/v1/auth/mfa/recovery` | MFA-pending | yes | `{recovery_code}` | `SessionOut` | 422, 401, 429 | rotated |
| POST `/api/v1/session/mfa/enrolment` | session | yes | — | `{secret, otpauth_uri}` (no-store) | 409, 401, 429 | replaces an unconfirmed secret |
| POST `/api/v1/session/mfa/enrolment/confirm` | session | yes | `{code}` | `{recovery_codes}` (no-store) | 422, 401, 429 | not rotated; marked MFA-verified |
| POST `/api/v1/session/mfa/remove` | session | yes | `{code}` (TOTP) | 204 | 422, 401, 429 | factor and codes disabled |
| GET `/api/v1/session` | session | — | — | `SessionOut` (`mfa_enabled`) | 401 | — |

All shell calls go through `TenantSessionProvider.request`.

## 5. States and copy

| State | Presentation |
|---|---|
| Off | Status "Off"; explanation; primary "Set up two-step verification" |
| On | Status "On — authenticator app"; "Recovery codes: Saved when you turned it on. Each code works once."; secondary "Turn off two-step verification" |
| Wrong code (422) | Field error "That code didn't work. Check your authenticator app and try again."; field cleared and focused |
| 409 on start | "Two-step verification is already on." and a session re-read |
| Cancelled set-up | "Set-up cancelled. If you added an MTI 360 entry to your authenticator app, remove it." |
| Done | "Two-step verification is on." / "…is off." in a focused status region |
| Other failures | The T01-05 `formFeedback` copy (refreshed session, denied, rate limited, unavailable, generic) |
| 401 | Session ended (navigation by the provider) |

Recovery codes copy (tenant): "Each code works once. They can't be retrieved later. Use one when you can't use your authenticator app. To get new codes later, turn two-step verification off and on again from Sign-in security."

## 6. Security, accessibility, responsive

T01-09B §11 and §12 apply unchanged (secret, URI, codes and code values in component memory only; copy on press; no storage, URL, title, console or telemetry; one h1; labelled fields with `one-time-code` / numeric; no auto-submit; Dialog focus trap and Escape; announced outcomes; AA in Light and Dark; 390 / 768 / 1024 / 1440). The modal page behind a Dialog is hidden from assistive technology.

## 7. Known backend limitations

| ID | Limitation | UX consequence |
|---|---|---|
| BG-T1 | The tenant session exposes no recovery-code count and there is no tenant regeneration endpoint | No remaining count, no low-codes warning, no regeneration; the hint explains off-and-on |
| BG-T2 | No tenant permission requires step-up | No tenant step-up UI |
| BG-T3 | No institute MFA policy (MFA cannot be required for members) | Opt-in only |
| BG-2 | TOTP issuer "MTI 360" in both realms (T01-09B) | Field description on the platform side; tenant copy refers to "MTI 360" |

## 8. Out of scope

Platform MFA (T01-09B); QR codes; download or print; step-up; session lists; institute MFA policy; member administration; every deferred factor (D6-4).

## 9. Tests

Status Off/On; no start on mount (StrictMode); one start on press with the tenant CSRF token on tenant paths; key, link and settings, no QR; copy on press; wrong code keeps the key; success drops the key, codes once, Escape does not dismiss, acknowledgement required, `beforeunload` armed then released, session re-read and focused outcome; cancel drops the key; 409; `SESSION_REFRESH_REQUIRED` not resent; `PERMISSION_DENIED`; 401 → session ended; 429; turn off (wrong code, success, cancel); page gate and account menu; source rules (no role gating, storage, logging or platform paths); sign-in step (rotated-session destination, tenant paths only, refused recovery code, 429, focus); leak checks across complete flows; axe in Light and Dark.
