# T01-09B Platform Identity & MFA — UI/UX Specification

- **Status:** Frozen (T01-09B readiness review, 2026-10-07: `READY_FOR_IMPLEMENTATION`); implemented in T01-09B. Resolves blocker **B1** of the T01-09 readiness review.
- **Screens:** PLAT-01, PLAT-02, PAUTH-01 … PAUTH-07 and a partial PLAT-52 (UI-SCREENS.md §12, §12A).
- **Builds on:** [ADR-0005](../adr/0005-identity-and-session-realms.md), [ADR-0010](../adr/0010-sessions-credentials-and-csrf.md), [ADR-0017](../adr/0017-platform-identity-mfa.md) and [platform-identity.md](../architecture/platform-identity.md) (D6-1 … D6-5), [ADR-0018](../adr/0018-platform-administration.md) (D7-3, D7-4), the tenant contracts [T01-04](T01-04-IDENTITY-AUTHENTICATION-UI.md) (§6, §7, §10, §11 S1–S16, §12, §13) and [T01-05](T01-05-AUTHORIZATION-RBAC-UI.md) (§11 error matrix). This document adds the platform realm; where it is silent, those contracts apply unchanged.
- **Out of scope:** tenant MFA enrolment and removal (deferred to **T01-09C**, D9B-9); every item in §13.

## 1. Locked inputs (not changed here)

| Source | Locked |
|---|---|
| ADR-0005 / ADR-0010 | Platform and tenant realms never share sessions, cookies or credentials. Platform cookie `__Host-mti360_psid` (HttpOnly, Secure, SameSite=Lax, Path=/); tenant cookie `__Host-mti360_tsid`. Opaque server-side session; no JWT |
| ADR-0017 §3 | Idle 15 min, absolute 240 min. A correct password opens an MFA-pending session (5 min fixed, no permissions, `user: null`). MFA success rotates the session and records `mfa_verified_at` |
| D6-4 | TOTP (RFC 6238, SHA-1, 6 digits, 30 s, ±1 step, replay protection) plus ten single-use recovery codes stored as HMAC and shown once. **No** SMS/email OTP, OTP resend, trusted or remembered devices, WebAuthn/passkeys |
| ADR-0017 "QR code" row | No QR library. Enrolment returns the secret and the `otpauth://` URI for manual setup |
| D6-5, D7-4 | Step-up: 10-minute window after the last MFA verification; `403 STEP_UP_REQUIRED`; enforced only in `authorize()` |
| D6-1, D6-3 | Break-glass is the CLI only. A lost device is reset by another Super Admin (Phase 02 UI) |
| D6-2, D7-3 | Reset and invitation tokens: single use, HMAC, fragment links `/platform/reset-password#token=` and `/platform/accept-invitation#token=` (fixed by the backend email templates) |

## 2. Decisions (D9B-1 … D9B-12)

| ID | Class | Decision |
|---|---|---|
| **D9B-1** | UX (docs) | Screen IDs as in §3. The IDs PLAT-03 … PLAT-13 are already the Platform Dashboard … Billing screens, so new platform authentication screens form a new family **PAUTH-xx** (the T01-05 precedent: AUTHZ-, RESOURCE-, NAV-, SESSION-). "Remember device", "Resend" and "Trusted device" are removed from PLAT-01/PLAT-02 (D6-4) |
| **D9B-2** | UX | MFA-pending states are **in-memory steps of `/platform/login`**, never routes. Reload, back or a new tab restarts sign-in. Reason: a pending session receives `401` on `GET /platform/session`; its status and CSRF token exist only in the login response |
| **D9B-3** | UX | Enrolment starts **only on an explicit button press**, never on mount (each `POST /enrolment` replaces the unconfirmed secret; React StrictMode double effects would silently replace it). A restart after `401` tells the person to remove the entry they added |
| **D9B-4** | Locked | Manual key (grouped in fours), `otpauth://` link "Open in authenticator app", "Copy key", TOTP settings. No QR code |
| **D9B-5** | UX | Recovery codes are shown once, with "Copy codes", a required "I've saved my recovery codes" checkbox (it validates; Continue is never disabled for it), and a `beforeunload` guard. No download, print or sync |
| **D9B-6** | UX | Step-up is **reactive only**: a `403 STEP_UP_REQUIRED` opens PAUTH-07. TOTP only. After success the original request is resent **exactly once** (the backend raises `STEP_UP_REQUIRED` in the route's authorization dependency, or first thing in recovery-code regeneration, before any work). A second `STEP_UP_REQUIRED` stops with an error. Never resent after `401`, `5xx`, a network error or `SESSION_REFRESH_REQUIRED`. Cancel performs nothing and shows no toast. The browser clock never decides anything |
| **D9B-7** | Implementation | Low recovery-code warning when the server session reports `recovery_codes_remaining ≤ 3`, on Overview and Sign-in security. The count never goes in a URL |
| **D9B-8** | Scope — **accepted** | Partial **PLAT-52** at `/platform/profile` ("Sign-in security"): name, email, roles (read-only), MFA status, recovery codes remaining, "Generate new recovery codes" (the only step-up action of T01-09B). The rest of PLAT-52 stays in Phase 02 (T02-23) |
| **D9B-9** | Scope — **accepted** | Tenant MFA enrolment and removal are **not** in T01-09B. They move to **T01-09C**, which will reuse the PAUTH-04/PAUTH-05 components |
| **D9B-10** | Implementation (security) | The same-origin proxy forwards **only the called realm's cookie**: `/api/v1/platform/*` gets `__Host-mti360_psid`, every other `/api/v1/*` path gets `__Host-mti360_tsid`. Never both |
| **D9B-11** | Implementation | `AuthenticationTemplate` shows the context label "Platform administration" in the banner; page titles end in "· MTI 360 Platform". No cross-link between tenant and platform sign-in |
| **D9B-12** | Out of scope | No idle-timeout warning, countdown or keep-alive; no polling |

## 3. Screen inventory

| ID | Screen | Route | Experience | Template |
|---|---|---|---|---|
| PLAT-01 | Platform sign-in | `/platform/login` | Platform auth | T16 |
| PLAT-02 | Two-step verification (TOTP and recovery-code modes) | step of `/platform/login` | Platform auth | T16 |
| PAUTH-01 | Forgot password | `/platform/forgot-password` | Platform auth | T16 |
| PAUTH-02 | Reset password | `/platform/reset-password#token=` | Platform auth | T16 |
| PAUTH-03 | Accept invitation | `/platform/accept-invitation#token=` | Platform auth | T16 |
| PAUTH-04 | Set up two-step verification (intro → key → confirm). Also re-enrolment after an MFA reset (indistinguishable to the UI) | step of `/platform/login` | Platform auth | T16 |
| PAUTH-05 | Recovery codes, shown once (component) | step of `/platform/login`; inside PLAT-52 | Platform auth / shell | T16 / Dialog |
| PAUTH-06 | Platform session ended | `/platform/session-ended?reason=` | Platform auth | T16 |
| PAUTH-07 | Step-up verification | Dialog in the platform shell | Platform shell | Dialog |
| PLAT-52 (partial) | Sign-in security | `/platform/profile` | Platform shell | T03 (partial) |

## 4. Routes

| Kind | Routes | Next.js location |
|---|---|---|
| Public platform authentication (no shell) | `/platform/login`, `/platform/forgot-password`, `/platform/reset-password`, `/platform/accept-invitation`, `/platform/session-ended` | `app/platform/(auth)/…` |
| Protected (shell) | `/platform`, `/platform/profile`, the T00-08 placeholders `/platform/{tenants,users,system-health,integrations,audit,settings}` | `app/platform/(console)/…` |
| MFA-pending | none (D9B-2) | — |
| Step-up | Dialog (PAUTH-07) | — |

- **`src/proxy.ts`** (UX only): a protected `/platform` path without the `__Host-mti360_psid` cookie redirects to `/platform/session-ended?reason=ended&next=<path>`. The five public routes are excluded. With a cookie, the server page gate reads `GET /api/v1/platform/session` and decides; a pending session (401 there) never reaches the shell.
- **Platform `next`:** only `/platform` or `/platform/<plain segments>` (unreserved characters, no dot segments, no `%`, `:`, `//` or backslash), and never one of the five authentication routes. Anything else is ignored and `/platform` is used. The tenant `next` keeps rejecting every `/platform` path.
- **`reason`:** allow-lists. `/platform/login`: `signed-out`, `password-reset`, `invitation-accepted`. `/platform/session-ended`: `signed-out`, `ended` (default).
- **Entry check of `/platform/login`:** a full platform session redirects to `next` or `/platform`. A pending or absent session shows the form.

## 5. API mapping

All paths are under `/api/v1/platform`. "Same-origin" = the realm guard's same-origin check, no CSRF token.

| Method and path | Access | CSRF | Request | Response | Errors used by the UI | Session effect |
|---|---|---|---|---|---|---|
| POST `/auth/login` | anonymous | same-origin | `{email, password}` | `PlatformSessionOut` (pending) | 401 generic, 422, 429 (+Retry-After), 403 refresh, 503 | new pending cookie |
| POST `/auth/logout` | anonymous | same-origin | — | 204 | — | revoked, cookie cleared |
| POST `/auth/password-reset` | anonymous | same-origin | `{email}` | 202 | 422, 429 | — |
| POST `/auth/password-reset/confirm` | anonymous | same-origin | `{token, new_password}` | 204 | 404, 422 `new_password`/`token` | all sessions end; MFA kept |
| POST `/auth/invitations/preview` | anonymous | same-origin | `{token}` | `{email}` (masked) | 404, 429 | — |
| POST `/auth/invitations/accept` | anonymous | same-origin | `{token, password}` | 204 | 404, 422 `password`/`token` | none (no sign-in) |
| POST `/auth/mfa/enrolment` | pending | CSRF | — | `{secret, otpauth_uri}` | 401, 409 | replaces the unconfirmed secret |
| POST `/auth/mfa/enrolment/confirm` | pending | CSRF | `{code}` | `{recovery_codes, session}` | 422 `code`, 401, 429 | **rotated** to full |
| POST `/auth/mfa/verify` | pending | CSRF | `{code}` | `PlatformSessionOut` | 422, 401, 429 | **rotated** |
| POST `/auth/mfa/recovery` | pending | CSRF | `{recovery_code}` | `PlatformSessionOut` | 422, 401, 429 | **rotated** |
| GET `/session` | full only | — | — | `PlatformSessionOut` | 401 | idle extended |
| POST `/session/step-up` | full | CSRF | `{code}` | `PlatformSessionOut` | 422, 401, 429 | `mfa_verified_at` refreshed; no rotation |
| POST `/session/mfa/recovery-codes` | full + step-up | CSRF | — | `{recovery_codes}` | 403 `STEP_UP_REQUIRED`, 409, 401 | old codes invalid |

`PlatformSessionOut`: `status` (`authenticated` \| `mfa_required` \| `mfa_enrolment_required`), `user {display_name, email} | null`, `permissions[]`, `roles[]`, `mfa {enrolled, verified_at, step_up_expires_at, recovery_codes_remaining}`, `csrf_token`. Wrong MFA codes (including step-up) count toward the credential lockout; the fifth wrong code on a session revokes it (`401`).

## 6. Sign-in, MFA and enrolment flows

```
UNKNOWN → UNAUTHENTICATED → AUTHENTICATING ─401→ FAILED | ─429→ RATE_LIMITED
AUTHENTICATING ─ok→ MFA_REQUIRED (PLAT-02) | MFA_ENROLMENT_REQUIRED (PAUTH-04)   [memory: status + pending CSRF]
MFA_* ─verify / recovery ok→ AUTHENTICATED (rotated) → full navigation to next | /platform
MFA_ENROLMENT_REQUIRED ─confirm ok→ RECOVERY_CODES_UNACKED (session already full) ─ack→ full navigation
MFA_* ─401 (expired after 5 min / 5 wrong codes)→ UNAUTHENTICATED + notice
MFA_* ─reload / back / new tab→ UNAUTHENTICATED (pending state is never restored)
AUTHENTICATED ─401 anywhere→ /platform/session-ended?reason=ended&next=
AUTHENTICATED ─403 STEP_UP_REQUIRED→ PAUTH-07 ─ok→ AUTHENTICATED (one resend)
AUTHENTICATED ─sign out→ /platform/session-ended?reason=signed-out
```

- **PLAT-01:** Email (`autocomplete=username`), Password (revealable, `current-password`), "Sign in", "Forgot password?". Every refusal renders the same DOM: "We couldn't sign you in" (no "locked", "suspended" or "unknown account"). The password is cleared after every failure.
- **PLAT-02:** the generalised `MfaStep` (one implementation for both realms). TOTP: `one-time-code`, numeric, cleared after every attempt, no auto-submit. Recovery mode (`xxxxx-xxxxx`, `autocomplete=off`). "Use a recovery code instead" / "Use your authenticator app instead", "Back to sign in" (ends the pending session). `422` → field error; `401` → back to PLAT-01 with "Sign in again"; `429` → rate-limit Alert.
- **PAUTH-04:** intro ("Your authenticator app is required every time you sign in to MTI 360 platform administration" and the time-limit notice: "Finish within 5 minutes of signing in, or you'll need to sign in again."); "Set up authenticator app" (the explicit start, D9B-3); then the key (`SecretValue`, grouped in fours), "Copy key", "Open in authenticator app" (`otpauth://`), the settings (time-based, 6 digits, every 30 seconds), and the confirm code (`MfaCodeField`, "Verify and turn on"). `422` keeps the key. `401` → PLAT-01 notice "Set-up ended. Sign in again. Remove the MTI 360 entry you added — a new key will be issued." `409` (already set up) → PLAT-01 with "Sign in again". On success the key and URI are dropped **before** PAUTH-05 renders; they are also dropped on unmount.
- **PAUTH-05:** the ten codes (`CodeList`, `<ol>`, monospace), "Copy codes", copy "Each code works once. This is the only time they're shown — they can't be retrieved later. You can generate new codes from Sign-in security.", required checkbox, "Continue". An unchecked box gives the field error "Confirm that you've saved your recovery codes." While shown, `beforeunload` asks before leaving. Continue drops the codes, removes the guard and makes a full document navigation.
- **Recovery-code sign-in:** succeeds like TOTP. The low-codes warning (D9B-7) then appears from the server session.

## 7. Password reset and invitation (PAUTH-01 … PAUTH-03)

They are the tenant AUTH-02/03/06 screens on the platform endpoints, with the T01-09A fragment pattern unchanged: read `#token=`, remove it with `history.replaceState`, hold it in memory, send it only in POST bodies.

- **PAUTH-01:** identical confirmation for any 2xx ("If a platform account uses …").
- **PAUTH-02:** description "Your new password replaces the old one and signs you out everywhere. Your authenticator app is still required when you sign in." Success → `/platform/login?reason=password-reset`.
- **PAUTH-03:** the preview shows only the server-masked email ("Invitation for j…@example.com"); no name field (the API takes token and password). One `404` message. Success → `/platform/login?reason=invitation-accepted` ("Your password is set. Sign in to set up two-step verification.").
- **PAUTH-06:** the AUTH-05 copy; "Sign in" → `/platform/login` (valid `next` carried).

## 8. Platform shell

- `ExperienceFrame` (PLATFORM) with the session; no `TenantContext` or `CampusSwitcher`.
- **UserMenu:** header with display name, email and "Roles: …" (display only, never used to decide). Items: "Sign-in security" (→ `/platform/profile`), Preferences, Sign out. Sign out: full-page `LoadingRegion`, `POST /platform/auth/logout`, then `/platform/session-ended?reason=signed-out` whatever the outcome. It never touches the tenant cookie.
- **Navigation requirements:** Overview `ALWAYS`; Tenants `tenant.read`; Platform Users `platform_user.read`; Audit `audit.read`; System Health, Integrations, Settings `UNRELEASED`. Sign-in security (`/platform/profile`) is `ALWAYS` and reached from the user menu. Pages enforce the same requirement: unmet permission → AUTHZ-01 (`ShellAccessDenied`) at the same URL; `UNRELEASED` outside development or an unknown path → not found.
- **Zero-permission user** (any role other than `SUPER_ADMIN` / `SECURITY_AUDIT_ADMIN` in T01): Overview shows `EmptyState` "No platform areas are assigned to your role yet."
- **`PlatformSessionProvider`** (T01-05 §11 matrix): `401` → re-read, then `/platform/session-ended`; `SESSION_REFRESH_REQUIRED` → re-read (fresh CSRF), retry a GET once, never resend an unsafe request (`SessionRefreshedError`); `PERMISSION_DENIED` → background re-read; `STEP_UP_REQUIRED` → PAUTH-07. Re-read on tab visibility. No polling, no idle timer.

## 9. Step-up (PAUTH-07)

Dialog "Confirm it's you": "Enter the 6-digit code from your authenticator app to continue. Each wrong code counts toward locking your account." Field `MfaCodeField`. Actions "Verify and continue" / "Cancel". Help: "Lost your authenticator? Ask another Super Admin to reset your two-step verification."

| Outcome | Behaviour |
|---|---|
| 2xx | Replace the session from the response, close, restore focus, resend the original request once (D9B-6) |
| Resend → `STEP_UP_REQUIRED` | Error to the caller ("We couldn't confirm it's you. Try again."), no loop |
| 422 | Field error, code cleared, focus on the field |
| 429 | Alert in the dialog |
| 401 | Session ended (navigate) |
| `SESSION_REFRESH_REQUIRED` | Re-read the session (fresh CSRF), keep the dialog open, "Your session was refreshed. Try again." |
| Network / 5xx | Alert in the dialog; nothing resent |
| Cancel / Escape | Original action not performed; no toast |

## 10. Partial PLAT-52 — Sign-in security (`/platform/profile`)

Page header "Sign-in security". Sections: **Account** (name, email, roles, read-only); **Two-step verification** ("On — authenticator app", recovery codes remaining; warning Alert at ≤ 3). Action "Generate new recovery codes" → `AlertDialog` ("Your current recovery codes stop working as soon as new ones are generated.", confirm "Generate new codes") → `POST /session/mfa/recovery-codes` (step-up via PAUTH-07 when required) → PAUTH-05 in a non-dismissable Dialog; acknowledgement closes it and re-reads the session.

## 11. Security rules

1. The TOTP secret and `otpauth://` URI live only in PAUTH-04 component state; cleared on confirmation and unmount; never in storage, a URL, the console, telemetry or the page title; copied only on a button press.
2. Recovery codes live only in PAUTH-05's owner state; dropped on acknowledgement; never persisted or logged; copied only on a button press; no download/print/sync.
3. MFA and step-up codes are cleared after every attempt; never in a URL, storage or a log.
4. Reset and invitation tokens follow T01-04 S9/S10 (fragment, memory, POST body).
5. Authority comes only from the server (session read and API answers). No role-name decisions; nothing from storage or the URL.
6. The pending CSRF token exists only in memory; the pending state is never restored.
7. D9B-10 cookie scoping; realm-specific `next` allow-lists; `reason` allow-lists.
8. The server `message` is never displayed; fixed copy by error code only.

## 12. Accessibility and responsive

T01-04 §12–§13 apply. Additionally: one h1 per step and focus moved to it when the step changes; explicit labels and `autocomplete` (`username`, `current-password`, `new-password`, `one-time-code`); no auto-submit (WCAG 3.2.2); errors via `FieldErrorMessage` / `Alert` with focus; the key is readable text and the codes an ordered list; the checkbox validates; Dialogs trap focus and Escape cancels; 44px targets; reduced motion; AA contrast in Light and Dark (semantic tokens; `font-mono` for keys and codes). The 5-minute pending limit is server-enforced (security exception to WCAG 2.2.1) and announced in the copy. Tiers 390 / 768 / 1024 / 1440 as T16; codes and keys wrap, never clip.

## 13. Out of scope

Tenant MFA (T01-09C); trusted or remembered devices; SMS or email OTP; OTP resend; WebAuthn/passkeys; social or biometric sign-in; QR codes; recovery-code download or print; idle warning or keep-alive; signed-in password change; self-service MFA removal or re-enrolment; session lists; platform MFA reset and every platform/tenant administration screen (Phase 02); billing; support sessions and impersonation; platform analytics; notifications data; CSP and security headers.

## 14. Known backend limitations (not fixed here)

| ID | Limitation | UX consequence |
|---|---|---|
| BG-1 | No read of an MFA-pending session | D9B-2 (restart on reload) |
| BG-2 | TOTP issuer is "MTI 360" in both realms | A person with the same email in both realms sees two similar authenticator entries; wrong codes count toward lockout. Follow-up: issuer "MTI 360 Platform" |
| BG-3 | Enrolment shares the fixed 5-minute pending window | Slow set-up restarts; copy announces the limit |
| BG-4 | Step-up accepts TOTP only | A lost device mid-session needs a Super Admin reset (D6-3) |
| BG-5 | No signed-in password change, self-service re-enrolment or session list endpoints | Not offered |

## 15. Tests (required)

- **Unit:** platform `next` and `reason` allow-lists; tenant `next` rejects `/platform`; session conversion; platform navigation requirements and the zero-permission state; per-realm cookie forwarding.
- **Server gate:** no cookie, valid, invalid (401), tenant cookie only, pending session (401), read error.
- **Screens:** PLAT-01 identical DOM for every refusal and both MFA statuses; PLAT-02 modes, 422, 401 restart, 429; PAUTH-04 no call on mount, a single call under StrictMode, restart, 422 keeps the key, key cleared after confirmation; PAUTH-05 acknowledgement, `beforeunload`, codes dropped; PAUTH-01/02/03 fragments, 404, 422; PAUTH-06 reasons; PLAT-52.
- **Provider matrix:** 401; `SESSION_REFRESH_REQUIRED` (GET retried once, POST never); `PERMISSION_DENIED`; `STEP_UP_REQUIRED` (exactly one resend, cancel, repeated, 401 in the dialog).
- **Security:** no password, token, MFA or recovery code, secret, URI or CSRF token in the console, storage, request URLs, page title or rendered page after the step; fragment removed; pending state not restored; tenant cookie never sent to a platform API and vice versa; platform sign-out leaves the tenant session; no role-name authorization; no storage authority.
- **Accessibility:** axe in Light and Dark for every screen and state; focus targets.
- **Chromium journeys** (D18 harness, 390/768/1024/1440): run outside the repository; recorded as not run when the runtime rules exclude it.

## 16. Change log

| Date | Change |
|---|---|
| 2026-10-07 | Created from the T01-09B readiness review; D9B-8 and D9B-9 accepted |
