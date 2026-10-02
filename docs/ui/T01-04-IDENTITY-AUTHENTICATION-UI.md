# T01-04 Identity & Authentication — UI/UX Specification

- **Status:** Ready for freeze. The two blocking questions (OQ-1 invitation preview, OQ-4 campus selection) are resolved by the locked T01-04 decisions D19 and D04 ([identity-authentication.md](../architecture/identity-authentication.md)). The open questions left in §17 do not block.
- **Version:** 1.1 (2026-10-02)
- **Designs for:** T01-04 Tenant Identity & Authentication (backend). **Implemented in:** T01-09 Frontend Authentication & Session Integration.
- **Screens:** AUTH-01 … AUTH-03 and AUTH-05 (UI-SCREENS.md §14), plus AUTH-06 … AUTH-08 added by this specification. AUTH-04 (MFA) belongs to T01-06 and is not designed here.
- **Sources:**
  - Product: CLAUDE.md, PRD.md, APP-FLOW.md §4, DESIGN-SYSTEM.md (§5, §42, §57–§61, §84, §90), UI-SCREENS.md §14.
  - Decisions: ADR-0005, ADR-0006, ADR-0010, ADR-0014.
  - Frontend architecture: repository-structure.md §2, application-shell.md, components.md, layout.md, accessibility.md, design-tokens.md.
  - The T01-04 decision record [identity-authentication.md](../architecture/identity-authentication.md): locked D04 (campus selection) and D19 (invitation preview). The other review decisions (D01–D03, D05–D18) are backend matters that do not change this contract.

This document is the UI contract for the tenant authentication journeys. It specifies behaviour, structure, copy, states and accessibility. Backend behaviour it relies on is the contract in identity-authentication.md; §15 lists exactly what the UI reads from the API.

---

## 1. Purpose

Staff of a Maritime Training Institute sign in to the Tenant Application, choose the institute and campus they work in, and recover access when they forget their password or are invited. These screens are the first impression of MTI 360. They must feel like the same calm, premium maritime product as the application, and they must not leak information to anyone who is not yet authenticated.

The specification is detailed enough that T01-09 can build the screens without new UX decisions, using only the existing design system plus the four additions listed in §14.2.

## 2. Scope

### 2.1 In scope

| ID | Screen / state | Route |
|---|---|---|
| AUTH-01 | Sign in | `/login` |
| AUTH-02 | Forgot password | `/forgot-password` |
| AUTH-03 | Reset password | `/reset-password` |
| AUTH-05 | Session ended (expired, ended, signed out) | `/session-ended` |
| AUTH-06 | Accept invitation | `/accept-invitation` |
| AUTH-07 | Choose institute | `/select-institute` |
| AUTH-08 | Choose campus | `/select-campus` |
| — | In-shell session controls: institute context, campus switcher, sign out | inside `/app/*` |

### 2.2 Out of scope

These are not designed here and must not be added to these screens:

- MFA and TOTP (AUTH-04, PLAT-02: T01-06).
- Platform sign-in (PLAT-01: T01-06 and T01-09).
- Permission-restricted pages ("insufficient permissions", part of AUTH-05 in UI-SCREENS.md: T01-05).
- Roles, tenant and platform administration, user provisioning and invitation sending (T01-07 and T01-08).
- Support sessions and impersonation (Phase 02).
- SSO, social sign-in and passkeys.
- Student sign-in (STU-01).
- Billing, domains, profile and account settings pages.
- "Remember me" and "Remember device" (PLAT-01 only).
- Self sign-up (there is none: ADR-0010, invitation only).

### 2.3 Terminology

| Term in architecture | Term shown to users |
|---|---|
| Tenant | **Institute** (PRD.md §11: a tenant *is* a Maritime Training Institute) |
| Campus | Campus |
| Membership | (never shown) |
| Session | "signed in" / "session" only in session-ended copy |

The word "tenant" never appears in user-facing copy.

## 3. Constraints carried into the design

1. **Server-authoritative.** Every institute, campus and user value shown comes from the server session (§15). The browser never decides access. Routing guards are UX only (repository-structure.md §2).
2. **No tenant in URLs.** Tenant-application URLs never carry an institute identifier (ADR-0005). Choosing an institute is a server-validated call; the selected value is a *selector*, never authority.
3. **Generic authentication outcomes.** The API returns the same failure for wrong password, unknown email, disabled user, locked account and no usable membership (ADR-0010 §6, T01-04 review). The UI must not try to tell them apart.
4. **One design system.** Only `@/design-system/components`, `@/design-system/layout` and `@/shells` are used. Semantic tokens only, with no new colours, no `dark:` utilities and no arbitrary values (components.md §2). Light, Dark and System come from the existing theme runtime.
5. **Accessibility contract.** WCAG 2.2 AA as defined in accessibility.md. Every rule there applies; this document adds only authentication-specific behaviour.

## 4. User journeys

### J1 — Sign in, one institute
```text
/login → submit → [server: authenticated, institute resolved] → /app (dashboard)
```

### J2 — Sign in, several institutes
```text
/login → submit → [server: institute selection required] → /select-institute
       → choose → [server: switch ok] → (campus step if required, J3) → /app
```

### J3 — Campus step (D04)
```text
… → [server: campus_selection_required — SELECTED scope, 2+ permitted campuses]
  → /select-campus → choose → /app
```
No campus step for: one permitted campus (selected automatically), or all-campus scope (starts at "All campuses").

### J4 — Forgot and reset password
```text
/login → "Forgot password?" → /forgot-password → submit → generic confirmation
email link → /reset-password#token=… → new password → success → /login
```

### J5 — Accept an invitation, new person (D19)
```text
email link → /accept-invitation#token=… → preview: account "new"
           → name + create password → accept → /login?reason=invitation-accepted
```

### J6 — Accept an invitation, existing account (D19)
```text
email link → /accept-invitation#token=… → preview: account "existing"
           → accept (no password field) → /login?reason=invitation-accepted
           (sign in with the existing password)
```

### J7 — Switch institute inside the application
```text
/app/* → institute context → choose → [server: switch ok, session rotated] → full reload to /app
```

### J8 — Switch campus inside the application
```text
/app/* → campus switcher → choose → [server: ok] → same page, data refreshed
```

### J9 — Sign out
```text
/app/* → User menu → Sign out → /session-ended?reason=signed-out
```

### J10 — Session ends while working
```text
/app/* → any request answers "authentication required"
       → /session-ended?reason=ended&next=<current /app path> → Sign in → /login?next=… → back to the page
```

## 5. Screen inventory

| ID | Name | Route | Template | Visible to | Priority |
|---|---|---|---|---|---|
| AUTH-01 | Sign in | `/login` | T16 | Anyone | P0 |
| AUTH-02 | Forgot password | `/forgot-password` | T16 | Anyone | P0 |
| AUTH-03 | Reset password | `/reset-password` | T16 | Holder of a reset link | P0 |
| AUTH-05 | Session ended | `/session-ended` | T16 | Anyone | P0 |
| AUTH-06 | Accept invitation | `/accept-invitation` | T16 | Holder of an invitation link | P0 |
| AUTH-07 | Choose institute | `/select-institute` | T16 | Signed in, no institute selected | P0 |
| AUTH-08 | Choose campus | `/select-campus` | T16 | Signed in, institute selected, `campus_selection_required` | P0 |
| — | Institute context | `/app/*` header | Shell | Signed in, institute selected | P0 |
| — | Campus switcher | `/app/*` header | Shell | Signed in, two or more campus options | P0 |
| — | Sign out | `/app/*` user menu | Shell | Signed in | P0 |

## 6. Route inventory

All authentication routes live in the `(tenant-auth)` route group (repository-structure.md §1), outside the `/app` shell. The route group is invisible in URLs.

| Route | Server-side entry check (UX only) | Query / fragment | Notes |
|---|---|---|---|
| `/login` | Signed in with institute → `/app`; signed in without institute → `/select-institute` | `?next=`, `?reason=` | |
| `/forgot-password` | None | none | Reachable when signed in, too (no redirect) |
| `/reset-password` | None | `#token=` (fragment only) | Token never in the query string (§11) |
| `/accept-invitation` | None | `#token=` (fragment only) | |
| `/select-institute` | Not signed in → `/login`; one institute only → `/app` | `?next=` | |
| `/select-campus` | Not signed in → `/login`; no institute → `/select-institute`; `campus_selection_required` false → `/app` | `?next=` | Only reached when a choice is mandatory (D04) |
| `/session-ended` | None | `?reason=`, `?next=` | Never redirects automatically |

### 6.1 Parameters

- **`next`:** where to go after signing in.
  - Accepted only if it is a relative path beginning with `/app/` or equal to `/app`, with no scheme, no `//`, no backslash and no encoded variants of these.
  - Anything else is ignored silently and `/app` is used. This prevents open redirects.
  - `next` is carried through `/login → /select-institute → /select-campus`.
  - It is **not** honoured after an institute switch, because the page may belong to the previous institute.
- **`reason`:** what notice to show. It is an allow-list: `signed-out`, `ended`, `password-reset`, `invitation-accepted`. Unknown values are ignored. It is never free text and never displayed verbatim.
- **Tokens:** read from the URL **fragment** (`#token=…`), so they are never sent to the Next.js server, the proxy or access logs, and never leak through `Referer`. On load, the page reads the token into memory and immediately removes it from the address bar with `history.replaceState` (same path, no fragment). The token is sent only in a POST body. This needs the email links to use the fragment form (§15, OQ-7).

### 6.2 Transitions between routes

| From | Event | To |
|---|---|---|
| any `/app/*` page | No session cookie (proxy) or any API call answers `AUTHENTICATION_REQUIRED` | `/session-ended?reason=ended&next=<path>` |
| any `/app/*` page | Session has no institute | `/select-institute?next=<path>` |
| any `/app/*` page | `campus_selection_required` (for example, the active campus was removed from a `SELECTED` scope) | `/select-campus?next=<path>` |
| `/login` | Authenticated, institute resolved, no campus step | `next` or `/app` |
| `/login` | Authenticated, institute selection required | `/select-institute?next=…` |
| `/login` | Authenticated, `campus_selection_required` | `/select-campus?next=…` |
| `/select-institute` | Switch accepted | `/select-campus` if `campus_selection_required`, else `next` or `/app` (full document navigation) |
| `/select-campus` | Campus accepted | `next` or `/app` |
| `/reset-password` | Success | `/login?reason=password-reset` |
| `/accept-invitation` | Success | `/login?reason=invitation-accepted` |
| User menu | Sign out (any outcome) | `/session-ended?reason=signed-out` |
| `/session-ended` | "Sign in" | `/login` (`next` carried) |

Navigation that changes the active institute is a **full document navigation** (`window.location.assign`), not a client transition, so no data cached for the previous institute survives.

## 7. Authentication template (T16)

All AUTH screens share one page template, **`AuthenticationTemplate`** (T16; DESIGN-SYSTEM.md §68, §90). It does not exist yet (§14.2).

### 7.1 Structure

```text
<body>
 ├── SkipNavigation                       "Skip to main content" (first tab stop)
 ├── header (banner)                      MTI 360 wordmark (not a link before sign-in)
 ├── main#main-content
 │    └── SplitLayout ratio="1:1" stackBelow="desktop" secondaryPosition="end"
 │         ├── primary:   Container (form column, max-w-md)
 │         │                └── Card elevation="sm" padding="lg"
 │         │                     ├── CardHeader  title (h1) + description
 │         │                     └── CardBody    screen content (Form / list / state)
 │         │                └── secondary links (below the card)
 │         └── secondary: Show from="desktop"   Brand panel (decorative)
 └── footer (contentinfo)                 ThemeSelector · © MTI 360
```

- **One `h1`:** the card title. The brand panel has no headings.
- **Landmarks:** `banner`, `main`, `contentinfo`. No navigation landmark: there is no site navigation before sign-in.
- **Page title:** `"<Screen title> · MTI 360"`, for example "Sign in · MTI 360". There is no experience label, because the person has not entered an experience yet.
- **Tenant branding:** none. The authentication pages are shared by all institutes on `app.<domain>`, so showing an institute's logo or name before sign-in would reveal tenants (§11, R2).

### 7.2 Brand panel (desktop and large only)

- Background `background-secondary`, start border `border-subtle`, full height of the content area.
- Content, vertically centred and left-aligned, capped at `max-w-md`:
  1. A thin route line: `CompassIcon` in `accent-maritime` with a 1px `accent-maritime` rule, and a short 2px `accent-brass` segment. All decorative (`aria-hidden`).
  2. Tagline in `text-section`, `text-primary`: "Acquire Students. Simplify Operations. Grow Your Institute."
  3. One line in `text-body`, `text-secondary`: "The complete growth and operations platform for maritime training institutes."
- No images, illustrations, waves, gradients, glass effects or animation.
- Reading order: the panel follows the form in the DOM (`secondaryPosition="end"`), so screen-reader and keyboard users meet the task first. It contains no focusable elements.
- **Why tokens and not a Deep Ocean panel:** the semantic set has no tested text pair for a dark brand surface in both themes. `brand-primary` becomes bright Sea Glass in Dark (design-tokens.md §3). A Deep Ocean panel would need new component tokens, which is outside this task (OQ-9).

### 7.3 Widths and spacing

| Tier | Layout | Form column | Card | Gutter |
|---|---|---|---|---|
| Mobile 390–767 | Single column, brand panel hidden | full width | full width | 16px |
| Tablet 768–1023 | Single column, centred | `max-w-md` (28rem) | as column | 24px |
| Desktop 1024–1439 | Two columns 1:1 | `max-w-md`, centred in its column | as column | 32px |
| Large 1440+ | Two columns 1:1, content height-centred | `max-w-md` | as column | 32px |

- Vertical rhythm inside the card: `Stack gap="lg"` between groups, `gap="md"` between fields.
- Actions: one primary `Button size="lg" fullWidth` (44px at every width), secondary links below as `Button variant="tertiary"`.
- Card header to body follows Card defaults (padding 16 → 24px from tablet).
- No page-level horizontal scroll at 390px. Long emails and institute names wrap (`break-words`).

### 7.4 Theme

The footer holds the existing `ThemeSelector` (Light / Dark / System, storage key `mti360.theme`). Before sign-in the preference is local only (repository-structure.md §2). Every state in this document must be verified in Light, Dark and System (§16).

## 8. Screen specifications

Common rules for every form in this section:

- Use `Form` (React Aria, `validationBehavior="native"`).
- Required fields show `*` and the form shows "* Required field" (INC-23).
- Client validation is for UX only; the server validates authoritatively.
- On submit the primary button shows `isPending` with its pending label, and duplicate submits are blocked.
- Field values are kept on error, except password fields where stated.

### 8.1 AUTH-01 — Sign in (`/login`)

**Purpose:** authenticate with email and password.

**Hierarchy**
```text
AuthenticationTemplate
 └── Card
      ├── CardHeader  h1 "Sign in to MTI 360"  description "Use the email address your institute invited."
      └── CardBody
           ├── Notice (Alert, only with ?reason=)
           ├── Form-level error (Alert, only after a failed attempt)
           ├── Form
           │    ├── Input  Email
           │    ├── Input  Password (revealable)
           │    ├── Inline: "Forgot password?" (Button tertiary, href /forgot-password)
           │    └── Button primary fullWidth "Sign in"
           └── Help text  "Need access? Ask your institute administrator to invite you."
```

**Fields**

| Field | Component | Attributes | Client validation | Messages |
|---|---|---|---|---|
| Email | `Input type="email"` | `name="email"`, `autoComplete="username"`, `inputMode="email"`, `autoCapitalize="none"`, `spellCheck={false}`, `isRequired`, `maxLength={254}` | required; email format (native) | "Enter your email address." / "Enter an email address like name@institute.edu." |
| Password | `Input type="password"` + reveal (§14.2) | `name="password"`, `autoComplete="current-password"`, `isRequired`, `maxLength={128}` | required only — **no length rule on sign-in** (do not hint at the policy) | "Enter your password." |

- **Caps Lock:** while the password field has focus and Caps Lock is on (`KeyboardEvent.getModifierState`), the field description reads "Caps Lock is on." (polite).
- The email is trimmed before sending. It is not lower-cased in the UI; the server canonicalises.

**Actions**
- **Sign in** (primary; pending label "Signing in…").
- **Forgot password?** links to `/forgot-password`. The typed email is **not** carried in the URL.

**States**

| State | Trigger | Presentation |
|---|---|---|
| Default | Page load | Empty fields; no focus moved (no autofocus) |
| Notice | `?reason=signed-out` | `Alert tone="success"` "You've signed out." |
| | `?reason=password-reset` | `Alert tone="success"` "Your password has been changed. Sign in with your new password." |
| | `?reason=invitation-accepted` | `Alert tone="success"` "Invitation accepted. Sign in to continue." |
| Validation error | Submit with an empty or invalid field | Field errors; focus to the first invalid field (Form) |
| Pending | Request in flight | Button pending; fields stay editable but submit is blocked |
| Authentication failed | `AUTHENTICATION_REQUIRED` (401) from login | `Alert tone="error"`, title "We couldn't sign you in", body "Check your email and password and try again. If the problem continues, contact your institute administrator." Password cleared; focus to the password field; email kept |
| Locked account | Same 401 (indistinguishable, ADR-0010 §6) | Same as Authentication failed. See OQ-3 if the API ever distinguishes it |
| Rate limited | `RATE_LIMITED` (429) | `Alert tone="warning"`, title "Too many attempts", body "Wait a few minutes before trying again." If the API supplies a retry time: "Try again in about N minutes." (OQ-2). Password cleared; button **not** disabled |
| Session refresh needed | Security check failure (§10, OQ-5) | `Alert tone="warning"` "Your sign-in page has expired. Reload the page and try again." with action "Reload page" |
| Network error | No response | `Alert tone="error"` "We couldn't reach MTI 360. Check your connection and try again." Values kept |
| Server error | 500 / unexpected | `Alert tone="error"` "Something went wrong on our side. Try again in a moment." Values kept, password cleared |
| Success | Server reports the next step | Navigate per §6.2; no success message (the destination's h1 is announced) |

- Only one form-level Alert is shown at a time. A new submit removes the previous Alert before the request.
- The Alert is mounted in a persistent live container, so it is announced (accessibility.md §6).

**Accessibility specifics**
- `Alert tone="error"` uses `role="alert"`. After a failed attempt, focus goes to the password field, so the message and the field are both perceived.
- The reveal control is a named toggle (§14.2).
- No CAPTCHA (none is specified).

### 8.2 AUTH-02 — Forgot password (`/forgot-password`)

**Hierarchy**
```text
Card
 ├── CardHeader  h1 "Reset your password"  description "Enter the email address you use for MTI 360. If it matches an account, we'll send a link to choose a new password."
 └── CardBody
      ├── Form: Input Email · Button primary "Send reset link"
      ├── Confirmation (replaces the form after submit)
      └── Button tertiary "Back to sign in" (href /login)
```

**Fields:** Email — same attributes and validation as on AUTH-01.

**States**

| State | Trigger | Presentation |
|---|---|---|
| Default | Load | Form |
| Validation error | Invalid email | Field error; focus to the field |
| Pending | Request in flight | "Sending…" |
| Confirmation | **Any** 2xx | The form is replaced by `Alert tone="info"`, title "Check your email", body "If an account uses **{email}**, we've sent a link to reset the password. The link expires in 30 minutes. Check your spam folder if you don't see it." Actions: "Back to sign in" and "Use a different email" (shows the form again, field cleared). Focus moves to the Alert title. |
| Rate limited | 429 | `Alert tone="warning"` "Too many requests. Wait a few minutes before trying again." |
| Network / server error | No response / 500 | As on AUTH-01. The form stays |

- The confirmation is identical whether or not the account exists, and it appears after the same minimum delay. The UI never says "no account" or "account found".
- The echoed `{email}` is what the person typed (escaped text), not data from the server.
- There is no client-side resend countdown: a second request is simply allowed, and the server rate-limits.

### 8.3 AUTH-03 — Reset password (`/reset-password#token=…`)

**Hierarchy**
```text
Card
 ├── CardHeader  h1 "Choose a new password"  description "Your new password replaces the old one and signs you out everywhere."
 └── CardBody
      ├── Password requirements (description list, see below)
      ├── Form: Input New password (revealable) · Input Confirm new password (revealable)
      │         Button primary "Change password"
      └── Button tertiary "Back to sign in"
```

**Password requirements** (static text linked to the new-password field by `aria-describedby`):
- "Use 12 to 128 characters."
- "Avoid common passwords. Spaces and any characters are allowed."
- "You don't need special characters or numbers."

There are no live check marks and no strength meter: the only rules are length and the blocklist (ADR-0010 §7), and the blocklist is checked by the server.

**Fields**

| Field | Attributes | Client validation | Messages |
|---|---|---|---|
| New password | `autoComplete="new-password"`, `minLength={12}`, `maxLength={128}`, `isRequired` | required, length | "Use at least 12 characters." / "Use 128 characters or fewer." |
| Confirm new password | `autoComplete="new-password"`, `isRequired` | must equal New password (`validate`) | "The passwords don't match." |

**States**

| State | Trigger | Presentation |
|---|---|---|
| Missing token | No `#token=` on load | Replace the card body with `ErrorState kind="error"`, title "This reset link is incomplete", description "Open the link from your email again, or request a new one.", actions "Request a new link" → `/forgot-password`, "Back to sign in" |
| Default | Token present | Form. The token is held in memory and removed from the address bar (§6.1) |
| Validation error | Length or mismatch | Field errors; focus to the first invalid field |
| Common password | `VALIDATION_ERROR` on the password field | Field error "This password is too common. Choose a different one." Both password fields cleared; focus to New password |
| Pending | In flight | "Changing password…" |
| Link not usable | Token invalid, expired or already used | `ErrorState`, title "This reset link can't be used", description "It may have expired or already been used. Reset links work once and expire after 30 minutes.", actions "Request a new link" and "Back to sign in". Separate copy for expired vs used only if the API distinguishes them (OQ-6) |
| Rate limited / network / server error | | As on AUTH-01; the form stays and the passwords are cleared |
| Success | 2xx | Navigate to `/login?reason=password-reset` (the success Alert appears there) |

The page never shows the token. Reloading after the fragment was removed shows "This reset link is incomplete", which is safe.

### 8.4 AUTH-06 — Accept invitation (`/accept-invitation#token=…`)

**Purpose:** a person invited by their institute joins it. A new person also creates their MTI 360 account; an existing account holder keeps their password. The page never signs anyone in.

**API (D19, identity-authentication.md §3):**
- `POST /api/v1/auth/invitations/preview {token}` → `{institute_name, email_masked, account: "new" | "existing"}`, or one generic `404` for any unusable invitation.
- `POST /api/v1/auth/invitations/accept`: `{token, display_name, password}` for `new`, `{token}` only for `existing`.

**Hierarchy**
```text
Card
 ├── CardHeader  h1 "Join {institute_name} on MTI 360"      (after a successful preview)
 │               description "Invitation for {email_masked}"
 └── CardBody
      ├── LoadingRegion "Checking your invitation"          (while the preview runs)
      ├── Already signed in notice (Alert info)              (only when a session exists)
      ├── account = "new":
      │     Password requirements (as AUTH-03)
      │     Form: Input Your name · Input Create password (revealable) · Input Confirm password (revealable)
      │           Button primary "Create account and join"
      ├── account = "existing":
      │     Text "You already have an MTI 360 account for this email. Accept the invitation, then sign in with your current password."
      │     Button primary "Accept invitation"
      └── Button tertiary "Back to sign in"
```

Before the preview has answered, the card title is "Accept your invitation" (no institute name).

**Fields (new account only)**

| Field | Attributes | Client validation | Messages |
|---|---|---|---|
| Your name | `Input`, `name="display_name"`, `autoComplete="name"`, `isRequired`, `maxLength={200}` | required, not blank after trimming | "Enter your name." |
| Create password | as AUTH-03 New password | as AUTH-03 | as AUTH-03 |
| Confirm password | as AUTH-03 Confirm | must match | "The passwords don't match." |

**States**

| State | Trigger | Presentation |
|---|---|---|
| Missing token | No `#token=` on load | `ErrorState` "This invitation link is incomplete" — "Open the link from your invitation email again." Action "Back to sign in". No request is sent |
| Loading | Preview in flight | `LoadingRegion label="Checking your invitation"` with `SkeletonText lines={3}` in the card body. Card title "Accept your invitation" |
| Valid, new account | Preview `account: "new"` | New-account form. Focus is not moved; the h1 now names the institute |
| Valid, existing account | Preview `account: "existing"` | Explanation and one button. **No password or name field**, and no copy suggesting the password is set, changed or reset |
| Already signed in | `GET /session` shows a session (any user) | `Alert tone="info"` above the content: "You're signed in as {display name}. Accepting this invitation doesn't change who is signed in." Acceptance works as usual |
| Invitation can't be used | Preview or accept returns `NOT_FOUND` | `ErrorState` replaces the card body: "This invitation can't be used" — "It may have expired, been withdrawn or already been accepted. Ask your institute administrator to send a new invitation." Action "Back to sign in". One message for every reason (D19) |
| Validation error | Client rules, or `VALIDATION_ERROR` with field details | Field errors; focus to the first invalid field. "Common password" as AUTH-03 (both password fields cleared) |
| Pending | Accept in flight | Button pending ("Creating account…" / "Accepting…"); fields read-only |
| Rate limited | `429` on preview or accept | `Alert tone="warning"` "Too many requests. Wait a few minutes, then reload this page." If it happened on the preview, no form is shown yet |
| Network / server error | Preview | `ErrorState` "We couldn't check your invitation" with "Try again" (re-runs the preview with the token still in memory) and "Back to sign in" |
| Network / server error | Accept | `Alert tone="error"` as on AUTH-01; values kept, passwords cleared |
| Success, not signed in | Accept `2xx`, no session | Navigate to `/login?reason=invitation-accepted` |
| Success, already signed in | Accept `2xx`, a session exists | Replace the card body with `Alert tone="success"` "Invitation accepted. You can now open {institute_name}." Actions: "Switch institute" → `/select-institute` (full document navigation), and "Sign out" (signs out and goes to `/login?reason=invitation-accepted`, for when the invitation was for a different account) |

**Rules**
- The token is read from the fragment, removed from the address bar on load, kept in memory only, and sent only in the two POST bodies (§6.1, S10). A reload after removal shows "This invitation link is incomplete".
- The preview is run once per page load; it has no side effects, so "Try again" may repeat it.
- The UI never compares the invitee with the signed-in user: the preview does not return the invitee's identity (D19 §3.3), so a mismatch cannot be detected. The "Already signed in" notice and the success actions cover that case.
- `email_masked` and `institute_name` are shown exactly as returned (escaped text). The full email is never shown, and the page never mentions other institutes the email belongs to.

### 8.5 AUTH-07 — Choose institute (`/select-institute`)

**Purpose:** a signed-in person with access to several institutes picks one.

**Hierarchy**
```text
Card
 ├── CardHeader  h1 "Choose an institute"  description "You have access to more than one institute. You can switch later from the top bar."
 └── CardBody
      ├── Search (only when there are more than 8 institutes) label "Find an institute"
      ├── Form
      │    ├── RadioGroup label "Institutes" (visually hidden label; the h1 names the task)
      │    │     option label = institute name; description = "Trial" when on trial (OQ-8)
      │    └── Button primary "Continue"
      └── Inline: signed-in identity "Signed in as {email}" · Button tertiary "Sign out"
```

- The options are **exactly** the institutes returned by the server session (§15). Nothing is cached from earlier sessions, and there is no free-text entry.
- The institute already active (when arriving from the shell) is preselected.
- The list is sorted by name (locale-aware, from the server or `Intl.Collator`).
- Search filters the list client-side by name. When no name matches: text "No institutes match '{query}'." and "Clear search".

**States**

| State | Trigger | Presentation |
|---|---|---|
| Loading | Session in flight | `LoadingRegion label="Loading your institutes"` with three skeleton rows (`Skeleton height="control"`) |
| Default | 2+ institutes | RadioGroup; Continue enabled once one is selected (`isRequired`) |
| Validation | Continue with no selection | RadioGroup error "Choose an institute to continue." |
| Pending | Switch in flight | "Opening…"; RadioGroup disabled |
| No longer available | Switch answers `NOT_FOUND` | `Alert tone="warning"` "That institute is no longer available to you." The list is refetched; the option disappears |
| No institutes | Session has none | `EmptyState` (icon `InstituteIcon`), title "No institute available", description "Your account isn't active in any institute right now. Contact your institute administrator.", primary action "Sign out" |
| Session ended | 401 at any time | Navigate to `/session-ended?reason=ended` |
| Network / server error | | `ErrorState` with "Try again" (refetches the session) and "Sign out" |

**Responsive:** RadioGroup rows are 44px below tablet and stack full width. Long names wrap; nothing truncates in the chooser.

### 8.6 AUTH-08 — Choose campus (`/select-campus`)

**Purpose:** a person whose access is limited to some campuses (`SELECTED` scope) and who has two or more of them picks the campus to work in. This is the only case with a mandatory campus step (D04, identity-authentication.md §2).

**When it appears** (`campus_selection_required` from the session read):

| Membership | Permitted campuses | At sign-in or institute switch | AUTH-08? |
|---|---|---|---|
| All campuses (`ALL`) | 2 or more | Active campus = "All campuses" | No (optional change through the campus switcher) |
| All campuses (`ALL`) | 1 | That campus, automatically | No |
| Selected campuses (`SELECTED`) | 1 | That campus, automatically | No |
| Selected campuses (`SELECTED`) | 2 or more | Not chosen | **Yes** |
| Selected campuses (`SELECTED`) | 0 | The institute is not offered at all (membership not usable) | No |

It also appears later, inside the application, if the active campus stops being permitted and the server sets `campus_selection_required` again (§6.2).

**Hierarchy**
```text
Card
 ├── CardHeader  h1 "Choose a campus"  description "{Institute name}. You can change campus later from the top bar."
 └── CardBody
      ├── Form
      │    ├── RadioGroup label "Campuses" (visually hidden)
      │    │     one option per entry of campus_options: label = campus name, description = campus code
      │    └── Button primary "Continue"
      └── Inline: Button tertiary "Choose a different institute" (only with 2+ institutes) · Button tertiary "Sign out"
```

- The options are exactly `campus_options` from the session read: the permitted campuses of the active membership, in the active institute only, sorted by name. There is **no "All campuses" option** on this screen: a `SELECTED` membership never has an all-campus state (D04 rule 5).
- When the person arrived because their previous campus was withdrawn, a notice `Alert tone="info"` reads "The campus you were using is no longer available to you. Choose another to continue."
- "Continue" sends `PUT /api/v1/session/campus {campus_id}` and, on success, navigates to `next` or `/app`.

**States**

| State | Trigger | Presentation |
|---|---|---|
| Loading | Session read in flight | `LoadingRegion label="Loading your campuses"` with three skeleton rows |
| Default | `campus_selection_required` true | RadioGroup with no preselection; Continue |
| Not needed | `campus_selection_required` false (server entry check) | Redirect to `next` or `/app` (§6) |
| Validation | Continue without a choice | RadioGroup error "Choose a campus to continue." |
| Pending | Request in flight | Button "Opening…"; RadioGroup disabled |
| No longer available | `404 NOT_FOUND` from the switch | `Alert tone="warning"` "That campus is no longer available to you." The session is re-read and the option list replaced |
| Session ended | `401` | Navigate to `/session-ended?reason=ended` |
| Network / server error | Session read | `ErrorState` "We couldn't load your campuses" with "Try again" and "Sign out" |
| Network / server error | Switch | `Alert tone="error"` as on AUTH-01; the selection is kept |

There is no "No campuses" state: a membership without permitted campuses is not usable, so the server never reaches this screen with an empty list. If `campus_options` is nevertheless empty, the screen shows the AUTH-07 "No institute available" `EmptyState` (defensive).

**Responsive and accessibility:** as AUTH-07 (44px rows below tablet, names and codes wrap, one Tab stop with arrow-key selection).

### 8.7 AUTH-05 — Session ended (`/session-ended`)

**Purpose:** a single, calm place to land when the session ends for any reason, with a clear way back.

**Hierarchy**
```text
Card
 └── CardBody
      └── EmptyState icon LockIcon, titleAs h1
           title / description by reason (below)
           primaryAction "Sign in" → /login (carrying a valid next)
```

| `reason` | Title | Description |
|---|---|---|
| `signed-out` | "You've signed out" | "Sign in again whenever you're ready." |
| `ended` (default, also unknown values) | "Your session has ended" | "For your security, you've been signed out. Sign in again to continue. Changes you hadn't saved may need to be entered again." |

- The page does not distinguish "expired" from "revoked" (password changed elsewhere, access removed): the API does not report the difference, and the person cannot act on it differently.
- "Insufficient permissions" (UI-SCREENS.md AUTH-05) belongs to T01-05 and will be added there as a permission-restricted `ErrorState`, not on this route.

### 8.8 In-shell session controls (`/app/*`)

These complete the `UserMenu` and the specification components `TenantContext` and `CampusSwitcher` (CLAUDE.md §26; application-shell.md §3 notes they need authentication). They replace the demo account data in `UserMenu`.

**Institute context (`TenantContext`)**
- **Tablet and up:** in `AppHeader` utilities, before notifications. A secondary-style trigger showing `InstituteIcon` + the institute name (truncated with a tooltip at 24ch) + `ChevronDownIcon`.
  - Accessible name: "Institute: {name}. Switch institute".
  - With **one** institute it renders as plain text (no button, no chevron).
- **Mobile:** not in the header. The `UserMenu` gains an item "Institute" with description = the institute name.
- **Action:** opens a `Dialog` titled "Switch institute" containing the AUTH-07 chooser (same component, current institute preselected, Search when more than 8). Its actions are "Switch" (primary) and "Cancel".
- On success: full document navigation to `/app` (§6.2). Unsaved work: if the current page registers unsaved changes (a future form-level hook), an `AlertDialog` "Leave this page?" ("You have unsaved changes. Switching institute will discard them.", confirm "Switch institute", Cancel focused) precedes the switch.

**Campus switcher (`CampusSwitcher`)** (D04)
- **Shown** only when `campus_options` has two or more entries. With one permitted campus it renders as plain text (the campus name, no button). With none it is absent.
- **Tablet and up:** next to the institute context. The trigger shows `active_campus.name`, or "All campuses" when `active_campus` is `null` and `all_campuses_allowed` is true, plus a `ChevronDownIcon`. Accessible name "Campus: {value}. Switch campus".
- **Mobile:** `UserMenu` item "Campus" with description = the current value.
- **Action:** opens a `Dialog` "Switch campus" with a RadioGroup:
  - first option "All campuses" (description "Every campus of {institute name}") **only when `all_campuses_allowed`**;
  - then one option per `campus_options` entry (name; code as the description), with the current value preselected.
  - Actions "Switch" (primary) and "Cancel".
- **Request:** `PUT /api/v1/session/campus {campus_id}`, with `null` for "All campuses".
- **On success:**
  - the session read is replaced by the response;
  - all server-state queries are invalidated, so the page re-fetches its data (the new campus applies from these next requests; the request that switched did not change context, D04 rule 9);
  - the Dialog closes and focus returns to the trigger;
  - `toast.success` "Showing {campus name}" or "Showing all campuses".
- **On `404`:** inside the Dialog, `Alert tone="warning"` "That campus is no longer available to you." The session is re-read and the options replaced; the Dialog stays open.
- **On `401`:** J10 (session ended).
- **Unsaved changes:** the same `AlertDialog` rule as the institute switch ("Switching campus will discard them.").
- The campus switch does not rotate the session, so it needs no reload (D04 rule 10).

**Signed-in identity and sign out (`UserMenu`)**
- The menu trigger shows the monogram (from `display_name`); the menu header shows the display name and email (wrapped, not truncated).
- **"Sign out"**: no confirmation (it is not destructive). It shows a full-page `LoadingRegion label="Signing out"`, sends the request, and navigates to `/session-ended?reason=signed-out` **whatever the response** (sign-out is idempotent; a failure still clears the local state).

**Other tabs.** When a tab regains visibility (`visibilitychange`), it re-reads the session.
- If the session ended: navigate as J10.
- If `campus_selection_required` became true: navigate to `/select-campus?next=<path>`.
- If the active institute or campus differs from what the page shows: a non-dismissible `Alert tone="info"` at the top of `main`: "You switched institute or campus in another tab." with action "Reload".

## 9. Authentication state model

The UI state is **derived from the server** (the session read and the responses of authentication calls). It is never stored as authority on the client and never written to `localStorage` or `sessionStorage`.

### 9.1 States

| State | Meaning | Where it is shown |
|---|---|---|
| `UNKNOWN` | Session not read yet | Server render or `LoadingRegion` |
| `UNAUTHENTICATED` | No valid session | AUTH-01 / 02 / 03 / 05 / 06 |
| `AUTHENTICATING` | Login request in flight | AUTH-01 pending |
| `AUTHENTICATION_FAILED` | Login refused (generic; includes locked) | AUTH-01 error |
| `RATE_LIMITED` | 429 from an authentication call | Warning on the current screen |
| `AUTHENTICATED_WITHOUT_TENANT` | Session, no institute selected | AUTH-07 |
| `TENANT_SELECTED` | Institute selected; `campus_selection_required` (SELECTED scope, 2+ campuses, none chosen) | AUTH-08 |
| `CAMPUS_SELECTED` / `ALL_CAMPUS_SCOPE` | A campus is active (chosen or the only one), or "All campuses" (`ALL` scope, `active_campus` null) | (transient) |
| `ACTIVE_SESSION` | Ready to use the application | `/app/*` |
| `SESSION_ENDED` | 401 from any session-backed call (expired, revoked, user or membership deactivated) | AUTH-05 `reason=ended` |
| `SIGNED_OUT` | The person signed out | AUTH-05 `reason=signed-out` |
| `SERVER_ERROR` | Unexpected failure or no network | ErrorState / Alert on the current screen |

**Not modelled:**
- `ACCOUNT_LOCKED` as a separate state: the API returns the generic failure (OQ-3).
- `PASSWORD_RESET_REQUIRED`: the T01-04 architecture has no forced-reset state.
- `SESSION_REVOKED` separate from `SESSION_ENDED`: the API does not report the difference (§8.7).

### 9.2 Transitions

```text
UNKNOWN ──read session──► UNAUTHENTICATED | AUTHENTICATED_WITHOUT_TENANT | TENANT_SELECTED | ACTIVE_SESSION

UNAUTHENTICATED ──submit──► AUTHENTICATING
AUTHENTICATING ──401──► AUTHENTICATION_FAILED ──edit/submit──► AUTHENTICATING
AUTHENTICATING ──429──► RATE_LIMITED ──wait/submit──► AUTHENTICATING
AUTHENTICATING ──ok: institute selection required──► AUTHENTICATED_WITHOUT_TENANT
AUTHENTICATING ──ok: campus selection required──► TENANT_SELECTED
AUTHENTICATING ──ok: ready──► ACTIVE_SESSION

AUTHENTICATED_WITHOUT_TENANT ──choose institute ok──► TENANT_SELECTED | ACTIVE_SESSION
TENANT_SELECTED ──choose campus ok──► CAMPUS_SELECTED | ALL_CAMPUS_SCOPE ──► ACTIVE_SESSION

ACTIVE_SESSION ──switch institute ok──► (full reload) TENANT_SELECTED | ACTIVE_SESSION
ACTIVE_SESSION ──switch campus ok──► ACTIVE_SESSION
ACTIVE_SESSION ──active campus withdrawn (server re-validation)──► TENANT_SELECTED
ACTIVE_SESSION ──sign out──► SIGNED_OUT
any authenticated state ──401──► SESSION_ENDED
any state ──5xx / network──► SERVER_ERROR ──retry──► previous state
```

## 10. Error specification

### 10.1 Categories

| Category | Presentation | Focus | Recovery |
|---|---|---|---|
| Field validation (client or `VALIDATION_ERROR` with field details) | `FieldErrorMessage` under the field (icon + text + border) | First invalid field | Edit the field |
| Form-level outcome (authentication failed, rate limited, session refresh) | One `Alert` at the top of the card body | Stated per screen | Edit and resubmit, wait, or reload |
| Unusable link or token | `ErrorState` replaces the card body | `ErrorState` title (`titleAs="h1"` when it replaces the content) | Navigation actions |
| Recoverable load failure | `ErrorState` with `onRetry` | Unchanged | "Try again" |
| Session ended | Route change to AUTH-05 | Destination h1 | "Sign in" |
| Non-recoverable | `ErrorState` "Something went wrong" with `reference` = the response's `request_id` | — | "Back to sign in" |

### 10.2 Mapping

The API envelope is `{"error": {"code", "message", "details", "request_id"}}` (backend-foundation.md §7). **The UI never displays `message` from the server.** It maps `code` (and the field in `details`) to the copy in §8.

| Code (HTTP) | Login | Forgot | Reset / Invitation | Choose institute / campus | Inside `/app` |
|---|---|---|---|---|---|
| `VALIDATION_ERROR` (422) | Field errors | Field errors | Field errors | Selection error | Per feature |
| `AUTHENTICATION_REQUIRED` (401) | Authentication failed | — | — (OQ-6) | Session ended | Session ended (J10) |
| `NOT_FOUND` (404) | — | — | Invitation: "can't be used" (D19). Reset: "can't be used" (OQ-6) | "No longer available" | Per feature; campus switch: "no longer available" |
| `PERMISSION_DENIED` (403) | Session refresh needed if the API uses it for CSRF (OQ-5) | same | same | same | T01-05 permission state; CSRF per OQ-5 |
| `RATE_LIMITED` (429) | Too many attempts | Too many requests | Too many requests | Too many requests | Per feature |
| `CONFLICT` (409) | — | — | — | Refetch and show "no longer available" | Per feature |
| `INTERNAL_ERROR` (500) and others | Server error | Server error | Server error | ErrorState + retry | Shell error |
| No response | Network error | Network error | Network error | ErrorState + retry | Per feature |

### 10.3 Never displayed

Server `message` text, stack traces, SQL, exception names, HTTP status numbers, internal identifiers of users, sessions, memberships or tenants, token values, cookies, CSRF tokens, password hashes, Redis or rate-limit internals, provider or SMTP details, and whether an email exists or which institutes it belongs to (before authentication).

The only identifier ever shown is the `request_id` as "Reference: …" in a non-recoverable `ErrorState`. It is a correlation ID for support (components.md, ErrorState `reference`), not a record identifier.

## 11. Security UX rules

| # | Rule | How the UI implements it |
|---|---|---|
| S1 | No tenant from user input establishes context | The institute and campus choosers offer only server-provided options. The chosen value is sent to `PUT /session/tenant` / `/campus`, which decide. There are no URL parameters, no free text and no stored "last institute" used as authority |
| S2 | No account enumeration | One failure message for every login refusal (§8.1). Identical forgot-password confirmation. No "email not found" anywhere. Sign-in does not prefill or remember emails beyond the browser's own autofill |
| S3 | Generic password-reset responses | §8.2 confirmation for any 2xx; same timing |
| S4 | Invitation errors leak nothing more | One `404` and one message for unknown, expired, withdrawn and accepted invitations (D19). The preview returns only the institute name, the server-masked email and `new`/`existing`. The full email, IDs and other memberships are never returned or shown |
| S5 | Session expiry redirects safely | J10. `next` is restricted to `/app` paths (§6.1); no open redirects |
| S6 | CSRF failures recover safely | "Reload page" recovery (§8.1). Non-idempotent requests are never retried automatically; a `PUT` to `/session/*` may be retried **once** after re-reading the session (fresh CSRF token) |
| S7 | Rate limits reveal nothing internal | Fixed copy; only a rounded retry time if the API supplies one |
| S8 | Locked-account messaging follows the backend | Generic failure; no "locked" wording unless the API decides to expose it (OQ-3) |
| S9 | Tokens are never displayed | Not in copy, the DOM, the title or the console. Reset and invitation tokens are kept in memory only |
| S10 | No secrets in URLs | Tokens in the fragment, removed on load. Emails are never put in URLs (not even from sign-in to forgot password). Passwords are only in POST bodies |
| S11 | No telemetry of secrets | Frontend logging and error reporting must never capture field values, request bodies of `/auth/*` or `/session/*`, fragments, or cookies. Error reporting uses the route name without the fragment |
| S12 | No client-side authorization | Hidden or disabled UI is cosmetic. Every switch is server-validated, and the UI reacts to server answers |
| S13 | Server-authorized visibility | Institute and campus names and lists come only from the session read (`campus_options`, `all_campuses_allowed`, D04). "All campuses" is offered only when the server allows it. Nothing is cached across sign-outs: sign-out and institute switch use full document navigation, and the server-state cache is cleared |
| S14 | No tenant branding before sign-in | §7.1 |
| S15 | Password fields stay private | `type="password"` by default. Reveal is explicit and reverts to hidden after submit and on navigation. `autoComplete` values allow password managers. Paste is never blocked |
| S16 | Shared devices | No "remember me" (out of scope). The session-ended copy reminds people that unsaved changes may be lost |

## 12. Responsive behaviour

| Aspect | Mobile 390–767 | Tablet 768–1023 | Desktop 1024–1439 | Large 1440+ |
|---|---|---|---|---|
| Layout | One column, brand panel hidden | One column, centred | Form + brand panel 1:1 | Same, vertically centred |
| Form width | Full width minus 16px gutters | 28rem | 28rem | 28rem |
| Controls | 44px inputs and buttons (component tokens) | 40/44px per component | same | same |
| Primary action | Full width, first in its group | Full width in the card | same | same |
| Secondary links | Below the primary action, 44px targets | same | same | same |
| Alerts and errors | Full width of the card; text wraps; action moves below the text (Alert) | Alert action inline | same | same |
| Password requirements | Wrap; list items stack | same | same | same |
| Choosers | RadioGroup rows full width, 44px; Search above the list | same | same | same |
| In-shell controls | Inside the UserMenu | Header triggers (names truncate at 24ch with a tooltip) | same | same |
| Keyboard | Virtual keyboard: `inputMode="email"` on email; the page scrolls the focused field into view; Enter submits | Physical keyboard as desktop | Enter submits; Tab order = visual order | same |

- No horizontal page scroll at 390px in any state, including the longest error copy, a 200-character institute name and a 254-character email.
- Mobile action order: primary on top (layout.md §5).
- No separate mobile design language.

## 13. Accessibility

Everything in accessibility.md applies (§14 screen checklist). The rules below are the authentication specifics.

| Topic | Rule |
|---|---|
| Landmarks | `banner`, `main#main-content`, `contentinfo`; skip link first (T16) |
| Headings | One `h1` per screen (card title, or the ErrorState/EmptyState title when it replaces the content). No other heading levels in a card except `h2` inside Dialogs (their title) |
| Labels | Visible labels on every field. The choosers' RadioGroup label is visually hidden because the h1 names the task. Placeholders are not used for labels |
| Descriptions | Password requirements and the Caps Lock notice are linked with `aria-describedby` |
| Errors | Field: `aria-invalid`, linked error, icon + text + border. Form-level: `Alert tone="error"` (`role="alert"`), warning/info `role="status"`. Live containers are mounted before the text changes |
| Focus order | DOM order = visual order: notice → form-level alert → fields → primary → secondary links → footer |
| Focus on load | None moved (no autofocus) |
| Focus after errors | §8: first invalid field, or the password field after a failed sign-in |
| Focus after success | Route change; the destination title is announced |
| Focus after replacing content | Confirmation / ErrorState / EmptyState title (`tabIndex=-1`) |
| Focus restoration | Dialogs return focus to their trigger (React Aria) |
| Keyboard | Enter submits every form; Space toggles the reveal button; arrow keys move in RadioGroups; Escape closes the switch Dialogs; nothing needs a pointer |
| Announcements | Loading: `LoadingRegion` label once. Pending: `Button isPending`. Success: route change, or toast for the campus switch. Session ended: page title "Session ended · MTI 360" |
| Reveal toggle | `IconButton` inside the field, `label` "Show password" / "Hide password", `aria-pressed`, `aria-controls` = the input. Focus stays on the toggle; the value and caret are kept |
| Reduced motion | No motion beyond component defaults (already paired with `motion-reduce`) |
| Colour | Status always icon + text; never colour alone. Light and Dark contrast via semantic tokens only |
| Touch targets | 44px below tablet for inputs, buttons and radio rows. The reveal toggle is an in-field auxiliary button (at least 24px, accessibility.md §12); give it a 44px hit area |
| Timing | No time limits on these forms other than the server's. Confirmations do not auto-dismiss |
| Language | `lang="en"`; copy is plain, short and free of jargon ("institute", not "tenant") |

## 14. Design-system mapping

### 14.1 Reused as is

| Need | Component (`@/design-system/components`, `/layout`, `@/shells`) |
|---|---|
| Skip link | `SkipNavigation` |
| Page columns | `SplitLayout`, `Container`, `Show` |
| Vertical rhythm | `Stack`, `Inline`, `ActionBar` |
| Card | `Card`, `CardHeader`, `CardBody` |
| Forms | `Form`, `Input`, `RadioGroup`, `Search`, Field error/description pieces |
| Actions | `Button` (primary, tertiary), `IconButton` |
| Messages | `Alert`, `toast` / `ToastRegion` |
| Replace-content states | `ErrorState`, `EmptyState` |
| Loading | `LoadingRegion`, `Skeleton`, `SkeletonText` |
| Switch dialogs | `Dialog`, `AlertDialog` |
| Truncated names | `Tooltip` |
| Account menu | `UserMenu` (`DropdownMenu`), `AppHeader` utilities slot |
| Theme | `ThemeSelector` |
| Icons | `CompassIcon`, `InstituteIcon`, `LockIcon`, `ChevronDownIcon`, `SignOutIcon`, `ViewIcon` |

### 14.2 Missing, to be added in T01-09 (not implemented here)

| Addition | Why it is needed | Shape |
|---|---|---|
| **`AuthenticationTemplate` (T16)** | Every AUTH screen shares one frame (§7). Template T16 is listed in DESIGN-SYSTEM.md §68 and planned in `design-system/templates/` (repository-structure.md), but not built | Props: `title`, `description`, `notice?`, `children`, `footer?`. Composes the components in §7.1. No new tokens |
| **Revealable password on `Input`** | Show/hide password is required (§8.1) and `Input` has no in-field action | Extend `Input` with `isRevealable` (only with `type="password"`): an in-field `IconButton` (§13). One implementation, no separate component |
| **Two icons** | Hidden-state icon for the reveal toggle; "check your email" confirmation | `HideIcon` (Lucide `EyeOff`) and optionally `MailIcon` (Lucide `Mail`) added to `design-system/icons` |
| **`TenantContext`, `CampusSwitcher`** | Core components in CLAUDE.md §26, not built because they need authentication (application-shell.md §3) | Shell components using `Button`, `Dialog`, `RadioGroup`, `Search`, and a shared chooser body also used by AUTH-07 / AUTH-08 |

No other new components are needed. Everything else is composition.

## 15. Data the UI needs from the T01-04 API

The UI reads only the fields below. The contract for the decided parts is in [identity-authentication.md](../architecture/identity-authentication.md). The rest is planned T01-04 behaviour: T01-04 fixes the field names, and this table then follows them.

| Need | Used by | Source |
|---|---|---|
| Login result names the next step: ready, institute selection required, or `campus_selection_required` | AUTH-01 routing | T01-04 login (planned) |
| Session read `GET /api/v1/session`: user display name and email; active institute (id, name) or none; the institutes the person may choose (id, name, trial flag); the CSRF token | Shell, AUTH-07, guards | T01-04 (planned) |
| Session read, campus fields: `active_campus` `{id, name, code}` or null; `campus_options` (permitted campuses of the active membership, sorted); `all_campuses_allowed`; `campus_selection_required` | AUTH-08, CampusSwitcher, guards | **Locked: D04** (identity-authentication.md §2.3) |
| `PUT /api/v1/session/campus` with `{campus_id}` (a UUID or null) → 200 with the session read; any value outside the options → `404` | AUTH-08, CampusSwitcher | **Locked: D04** (§2.4) |
| `POST /api/v1/auth/invitations/preview {token}` → `{institute_name, email_masked, account}` or one generic `404` | AUTH-06 | **Locked: D19** (§3.2) |
| `POST /api/v1/auth/invitations/accept`: `{token, display_name, password}` for `new`, `{token}` for `existing`; not signed in afterwards | AUTH-06 | **Locked: D19** (§3.4) |
| Retry time on 429 | Rate-limit copy | Optional (OQ-2); the copy works without it |
| A distinct error code for a failed CSRF or Origin check | S6 recovery | OQ-5; until decided, the UI treats a `403` from `/auth/*` and `/session/*` as "session refresh needed" |
| Reset and invitation links in the form `https://<app host>/reset-password#token=…` and `/accept-invitation#token=…` | AUTH-03, AUTH-06 | OQ-7 (part of T01-04 link building, D15) |

## 16. Acceptance criteria

The T01-09 implementation of this specification is accepted when:

1. **Screens:** AUTH-01, 02, 03, 05, 06, 07 and 08 and the three in-shell controls exist at the routes in §6, built on `AuthenticationTemplate`, with every state in their tables reachable in tests.
2. **Copy:** the copy matches §8 (changes go through this document). No screen shows a server `message`, an internal ID other than the reference, a token or the word "tenant".
3. **Enumeration:** for an unknown email, a wrong password, a locked account and an account with no institute, AUTH-01 renders identical DOM after the response. AUTH-02 renders identical DOM for existing and unknown emails.
4. **Routing:** `next` accepts only `/app` paths (tested with absolute URLs, `//host`, backslashes and encoded forms). Tokens are read from the fragment and removed from the address bar. Institute switch and sign-out use full document navigation.
5. **Tenant isolation:** the choosers render only server-provided options. A forged option value is rejected by the server and shown as "no longer available". No institute or campus value is persisted in browser storage.
6. **Campus semantics (D04):**
   - AUTH-08 appears only when `campus_selection_required` is true, and it offers no "All campuses" option.
   - The campus switcher offers "All campuses" only when `all_campuses_allowed` is true.
   - With one campus the switcher is plain text.
   - After a switch, page data is re-fetched without a reload.
   - A withdrawn campus leads to AUTH-08 with its notice.
7. **Invitation (D19):**
   - The preview runs once from the in-memory token, and the token is sent only in POST bodies.
   - `existing` accounts never see a password field.
   - Every `404` from preview or accept shows the same "can't be used" state.
   - Acceptance never signs the person in. When a session is present, the success state offers "Switch institute" and "Sign out".
8. **Accessibility:** accessibility.md §14 checklist passes for every screen and state. axe has 0 violations in Light and Dark at 390, 768, 1024 and 1440. A keyboard-only walk completes J1–J10.
9. **Responsive:** no horizontal overflow at 390px with the longest copy and names; 44px targets below tablet; brand panel only from desktop.
10. **Theme:** every state verified in Light, Dark and System.
11. **Telemetry:** a test asserts that the error reporter receives no field values, fragments or `/auth/*` bodies.
12. **No scope creep:** no MFA, permission, administration, student or platform sign-in UI.

## 17. Open questions

### 17.1 Resolved

| ID | Question | Resolution |
|---|---|---|
| OQ-1 | Invitation preview | **D19:** `POST /api/v1/auth/invitations/preview` with the token in the body, not `GET /…/{token}`, because the request log records URL paths. Returns `institute_name`, `email_masked` and `account`; one generic `404` otherwise. AUTH-06 rewritten (§8.4) |
| OQ-4 | Campus selection semantics | **D04:** `ALL` scope uses "All campuses" with no mandatory step. One permitted campus is selected automatically. `SELECTED` with two or more requires AUTH-08 and has no "all" option. `SELECTED` with none is unusable. Options come from the session read; a value outside them is a `404`; the switch applies from the next request. AUTH-08 and the campus switcher rewritten (§8.6, §8.8) |
| OQ-3 | Locked accounts | Indistinguishable from other sign-in failures (ADR-0010 §6), as specified in §8.1 |

### 17.2 Open, not blocking

Each has a working default in this specification.

| ID | Question | Default in this specification |
|---|---|---|
| OQ-2 | Will 429 responses carry a retry time? | Copy without a time ("Wait a few minutes…") |
| OQ-5 | Which code does a failed CSRF or Origin check return? | Any `403` from `/auth/*` or `/session/*` shows "session refresh needed" |
| OQ-6 | Do reset-token failures distinguish expired, used and invalid? | One "This reset link can't be used" message (invitations are already one message under D19) |
| OQ-7 | Do email links use the fragment form and the frontend origin? | The UI reads the token from the fragment only |
| OQ-8 | Show institute status in the chooser? | "Trial" only; never PAST_DUE |
| OQ-9 | A Deep Ocean brand panel? | Existing tokens (§7.2) |
| OQ-10 | Warn before the idle timeout? | Deferred; out of scope |

## 18. Change log

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-10-02 | First specification (design only; no implementation). Adds AUTH-06 … AUTH-08 to UI-SCREENS.md §14 |
| 1.1 | 2026-10-02 | OQ-1 resolved by D19 (invitation preview, `POST`), OQ-4 by D04 (campus semantics). Updated: AUTH-06, AUTH-08, the campus switcher, routes, state model, error mapping, security rules, API data (§15) and acceptance criteria. "All my campuses" removed. The "signed in as someone else" state is replaced by "already signed in", because the preview does not return the invitee's identity. Ready for freeze |
