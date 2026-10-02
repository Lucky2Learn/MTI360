# T01-05 Authorization & RBAC — UI/UX Specification

- **Status:** Ready for freeze (§17).
- **Version:** 1.0 (2026-10-02)
- **Designs for:** T01-05 Authorization & RBAC (backend). **Implemented in:** T01-09 Frontend Authentication & Session Integration.
- **Builds on:** the frozen T01-04 UI contract [T01-04-IDENTITY-AUTHENTICATION-UI.md](T01-04-IDENTITY-AUTHENTICATION-UI.md). This document **amends** it only where §15 says so.
- **Locked decisions:** D-B1, D-B2, D-B3 and D-B4 of the T01-05 architecture review (§1.1). They are recorded in `docs/architecture/authorization.md` and ADR-0016 when T01-05 is implemented.
- **Related:** CLAUDE.md §10, §57, §62; DESIGN-SYSTEM.md §57, §59, §60; [security.md](../architecture/security.md) §5; ADR-0011; [accessibility.md](../architecture/accessibility.md); [application-shell.md](../architecture/application-shell.md); [layout.md](../architecture/layout.md).

---

## 1. Purpose

T01-05 gives every signed-in staff member a set of **permissions** in their active institute. This specification defines how the Tenant Application uses them:

- what people see (navigation, actions, dashboard sections);
- what happens when they are not allowed something (access denied versus not found);
- how the UI stays correct when permissions, institute or campus change.

### 1.1 Locked decisions

These T01-05 architecture decisions are **locked**. This contract depends on them and does not reopen them.

| ID | Decision (locked) | Effect on this contract |
|---|---|---|
| **D-B1** | Campus authorization semantics: each permission has a `tenant` or `campus` scope; tenant-wide permissions require all-campus access; campus permissions check the resource's campus against the member's permitted campuses; the active campus is a view filter, not an authorization boundary; a resource on a campus outside the member's access answers `404` | CAMPUS-01 (§8.7), RESOURCE-02 (§8.2) |
| **D-B2** | System roles (`INSTITUTE_OWNER`, `ADMIN`) are linked to their code templates and cannot be changed, renamed or deleted by tenants; custom roles are managed in T01-08 | Roles are display data only (§8.5); no role administration here |
| **D-B3** | Permission identity is `(realm, code)`; the T01 tenant baseline is `tenant.profile.read`, `campus.*`, `member.*`, `role.*`, `audit.read` | Requirement map (§6) |
| **D-B4** | Permissions are synchronized by migrations, with a registry-versus-database drift test | None for the UI (the session simply returns the codes) |

**The UI is never the security boundary.** Hiding or showing something is a usability decision. The backend authorizes every request, and PostgreSQL Row-Level Security protects every row. The UI must behave correctly when the backend refuses something the UI showed.

## 2. Scope

### 2.1 In scope (T01-05 foundation)

- Permission-aware navigation (sidebar, rail, mobile drawer, command search).
- Permission-aware page access, including direct URLs and bookmarks.
- The convention for hiding versus disabling actions.
- The access-denied page (AUTHZ-01) and the in-shell not-found state (RESOURCE-02).
- Action-level denial (RESOURCE-01).
- Campus-aware resource access (CAMPUS-01).
- The permission-filtered dashboard convention (DASH-01).
- Roles shown in the account menu (SESSION-01).
- Session refresh and permission changes during a session.
- Errors, accessibility, responsive behaviour and the frontend test contract.

### 2.2 Out of scope

| Item | Owner |
|---|---|
| Role and permission administration (ADMIN-07 Roles & Permissions), custom roles, assigning roles to members | T01-08 (API) and Phase 03 (screens) |
| Members, campuses and institute profile screens | T01-08 and Phase 03 |
| Platform authorization UI, platform roles, platform sign-in | T01-06 and Phase 02 |
| Student portal authorization | Phase 04 and 13 |
| Support sessions | Phase 02 |
| Feature-entitlement or upgrade prompts | Phase 02 subscriptions |
| Business-module permissions and templates | Each business module |

T01-05 adds **no new API**. It adds two fields to the session read (§5).

## 3. Principles

1. **Advisory checks.** UI checks only decide what to show. Every action still goes to the API, and the UI handles the API's answer.
2. **Permissions, never roles, decide.** Roles are tenant data: system roles are fixed per institute, and custom roles can be named anything. The UI **never** gates anything on a role name; it gates only on permission codes.
3. **Server-provided only.** Permissions and roles come only from the session read of the current request. They are never read from `localStorage`, `sessionStorage`, cookies the client can read, URL parameters or earlier sessions.
4. **Decide before rendering.** Protected pages make the access decision on the server, during the request, before any protected content is rendered. There is no flash of content followed by a denial.
5. **No information leaks.** Denials never name a permission, a role, an institute, a campus or any internal identifier.
6. **One mechanism per concern.** Sign-in, session lifetime, institute switching and campus switching stay exactly as in T01-04. This document adds no second session mechanism.

## 4. Screen and state inventory

| ID | Name | Kind | Where |
|---|---|---|---|
| AUTHZ-01 | Access denied | **NEW SCREEN** (state rendered at the requested URL) | Any `/app/*` page |
| RESOURCE-01 | Action denied | **STATE ONLY** | Any action control in `/app/*` |
| RESOURCE-02 | Not found (in the shell) | **NEW SCREEN** (state; the in-shell not-found view of `/app`) | Any `/app/*` page or resource |
| NAV-01 | Permission-aware application navigation | **EXISTING SCREEN MODIFICATION** (`AppSidebar` / `AppNavigation`, `CommandSearch`) | Desktop and tablet shell |
| NAV-02 | Permission-aware mobile navigation | **EXISTING SCREEN MODIFICATION** (`MobileNavigation`) | Mobile shell |
| SESSION-01 | Session, role and permission context | **EXISTING SCREEN MODIFICATION** (`UserMenu`, session state) | Shell header |
| CAMPUS-01 | Campus-aware resource access | **STATE ONLY** (behaviour rules) | Lists and detail pages with campus data |
| DASH-01 | Permission-filtered dashboard | **EXISTING SCREEN MODIFICATION** (convention) | `/app` (Dashboard) and any multi-section page |

UI-SCREENS.md AUTH-05 ("Session / Access Denied") keeps its session states (T01-04 `/session-ended`). Its "insufficient permissions" part is AUTHZ-01.

## 5. Session contract (consumed, not designed)

The T01-04 session read (`GET /api/v1/session`, and the same body in the login and institute-switch responses) gains two fields in T01-05:

| Field | Type | Meaning |
|---|---|---|
| `permissions` | `string[]`, sorted | Permission codes in the **active institute**, tenant realm only. Empty when no institute is active |
| `roles` | `{ name: string, is_system: boolean }[]` | The member's roles in the active institute, for display only. There are no role IDs |

Client session state, derived from that one response and owned by the session helper (§12):

```text
Session
├── user              { displayName, email }
├── activeInstitute   { id, name } | null
├── institutes        [...]                    (T01-04)
├── activeCampus      { id, name, code } | null (T01-04)
├── campusOptions, allCampusesAllowed, campusSelectionRequired   (T01-04, D04)
├── permissions       Set<string>              (T01-05)
├── roles             [{ name, isSystem }]     (T01-05)
└── csrfToken                                  (T01-04)
```

- The state is replaced as a whole on every session read. It is never merged with an earlier one.
- It is never persisted.
- Permission codes are opaque strings such as `campus.read`. The UI compares them for equality only and never parses them for meaning (no wildcard matching).

## 6. Requirement map: navigation and pages

Every tenant navigation item and every tenant page declares **one** requirement:

| Requirement | Meaning |
|---|---|
| `{ permission: "<code>" }` | Shown and reachable only when the session has that code |
| `ALWAYS` | Any signed-in member with an active institute (only the Dashboard, `/app`) |
| `UNRELEASED` | The module has no permission yet. Hidden and unreachable in **staging and production**; visible in **development** builds only, as the T00-08 placeholder pages are today |

The requirement is part of the navigation configuration (`shells/experiences/tenant.ts`); a page not in the navigation declares its own. An item **without** a requirement is a build error: the frontend test in §16 fails.

T01 requirements (the Institute → Administration group; routes from the existing configuration):

| Navigation item | Route | Requirement |
|---|---|---|
| Dashboard | `/app` | `ALWAYS` |
| Institute | `/app/administration/institute` | `tenant.profile.read` |
| Campuses | `/app/administration/campuses` | `campus.read` |
| Users | `/app/administration/users` | `member.read` |
| Roles | `/app/administration/roles` | `role.read` |
| Audit Logs | `/app/administration/audit-logs` | `audit.read` |
| Integrations, AI Config, Notifications, Billing, Settings | `/app/administration/…` | `UNRELEASED` |
| Every Operations, Engagement & Intelligence and Analytics item | `/app/…` | `UNRELEASED` |

Later modules replace `UNRELEASED` with their own permission when they ship. No other change to this document is needed.

The same map drives navigation filtering (NAV-01, NAV-02), command search and page access (§7). One source, no divergence.

## 7. Page access (direct URLs, bookmarks, navigation)

For every request to an `/app/*` page, in this order, on the server (the experience layout, a server component; repository-structure.md §2):

1. **Session.** Read the session server-side (T01-04).
   - No valid session → `/session-ended?reason=ended&next=<path>` (T01-04 J10).
   - No institute → `/select-institute?next=<path>`.
   - Campus selection required → `/select-campus?next=<path>`.
2. **Requirement.** Find the page's requirement (§6).
   - Unknown route, or `UNRELEASED` outside development → RESOURCE-02 (not found).
   - Permission absent → **AUTHZ-01** (access denied).
   - Otherwise render the page shell.
3. **Data.** The page loads its data from the API with `LoadingRegion` and skeletons (the existing pattern).
   - `404` → RESOURCE-02.
   - `403 PERMISSION_DENIED` → AUTHZ-01, replacing the page body (the session changed between steps 2 and 3).
   - Other errors → §11.

No protected page content reaches the browser before step 2 has passed; the shell (header, navigation) may render. The **URL stays as requested** for AUTHZ-01 and RESOURCE-02 (no redirect), so a reload after access is granted shows the page.

## 8. Screen specifications

### 8.1 AUTHZ-01 — Access denied

| Aspect | Specification |
|---|---|
| Purpose | Tell a signed-in member that the page exists for their institute but their access does not include it, without revealing why |
| Route | The requested `/app/*` URL (rendered in place; no `/forbidden` route) |
| Audience | Signed-in staff with an active institute |
| Preconditions | A valid session with an active institute; the requirement is not met (§7 step 2), or the API answered `403 PERMISSION_DENIED` while loading the page |
| Entry points | Navigation from a stale link or bookmark, a typed URL, permission removed during the session |
| Layout | Inside `ApplicationShell` → `PageContainer` (default width) → a visually hidden `h1` "Access denied" (`sr-only`, `tabIndex=-1`; the existing `ShellError` pattern) → `ErrorState` (its title is an `h2`). No breadcrumbs |
| Components | `ErrorState kind="permission"` (lock icon, neutral surface: not an error colour) |
| Content | ErrorState title (`h2`): **"You don't have access to this page"**. Description: **"Your access in this institute doesn't include this page. If you need it, ask your institute administrator."** |
| Primary action | "Go to dashboard" → `/app` (`backHref`, rendered as a secondary button by ErrorState; this is the only navigation action) |
| Secondary actions | None. No "Request access" in T01 (no backend) |
| Loading | The decision is made on the server before rendering, so there is no loading state of its own. If the denial comes from step 3, the page's `LoadingRegion` is replaced by AUTHZ-01 |
| Empty / error | Not applicable |
| 401 | Not shown; the T01-04 session flow applies first (§7 step 1) |
| 404 | Not shown; RESOURCE-02 applies |
| Responsive | ErrorState's own rules: centred, `max-w-lg`; the action is full width on mobile, inline from tablet. The navigation stays available |
| Accessibility | `<title>` "Access denied · Tenant Application · MTI 360" (announced by the route announcer). On client-side navigation, focus moves to the hidden `h1`; the ErrorState title and description follow in reading order. The meaning is carried by text, the lock icon is decorative. The action is a real link |
| Permission requirement | None (it is the denial) |
| Security | Never shows the permission code, role names, the requirement, the institute's other pages or why access is missing. The same page for every denied page, so it cannot be used to discover features |
| Acceptance | Rendered for a denied page in development, staging and production; no protected content in the HTML; URL unchanged; focus on the `h1`; one `h1`; identical content for every denied route |

### 8.2 RESOURCE-02 — Not found (in the shell)

| Aspect | Specification |
|---|---|
| Purpose | One answer for "does not exist", "belongs to another institute" and "belongs to a campus outside your access", so none of these can be told apart (IDOR protection, D-B1) |
| Route | The requested URL. Implemented as the `/app` boundary's not-found view, so it renders **inside the shell** (today a 404 below `/app` falls back to the global page) |
| Preconditions | Unknown `/app` path; `UNRELEASED` outside development; or the API answered `404` for the page's resource |
| Layout | `ApplicationShell` → `PageContainer` → a visually hidden `h1` "Not found" (`tabIndex=-1`) → `EmptyState` (`titleAs="h2"`, icon `CompassIcon`) |
| Content | Title: **"Page not found"**. Description: **"This page or item doesn't exist, or it's no longer available."** |
| Actions | Primary "Go to dashboard" (`/app`). Secondary "Go back" (browser history; shown only when there is a previous entry in this tab) |
| Accessibility | `<title>` "Not found · Tenant Application · MTI 360"; focus moves to the hidden `h1` on client-side navigation; no colour-only meaning |
| Security | The wording never says "you don't have access", "another institute" or "another campus". It is the **same** view for all three causes |
| Acceptance | Cross-tenant ID, cross-campus ID (outside the member's scope) and a random ID all render identical HTML (except the request ID in logs) |

### 8.3 RESOURCE-01 — Action denied

An action the UI offered was refused with `403 PERMISSION_DENIED`, because permissions changed after the page was rendered.

| Where the action was started | Presentation |
|---|---|
| Inside a form or `Dialog` | `Alert tone="error"` at the top of the form or dialog body: title **"You can't do this"**, body **"Your access changed. This action is no longer available to you."** The form keeps its values. The submit button is removed (not disabled) once the session has been re-read (below) |
| From a page action, row action, menu item or button without a form | `toast.error("You can't do this", { description: "Your access changed. This action is no longer available to you." })`. One toast per denied action: a second 403 within 5 seconds for the same action does not add another toast (dedupe by action key) |

After **any** RESOURCE-01, the session is re-read once in the background. The navigation, the page's action visibility and the role list update from the new session. If the page itself is no longer allowed, the page is replaced by AUTHZ-01.

- Focus: inside forms, focus moves to the Alert (`role="alert"` announces it). For a toast, focus stays on the triggering control, or on the page heading if the control was removed.
- The action is never retried automatically.

### 8.4 NAV-01 and NAV-02 — Permission-aware navigation

- **Authorization data is server-authoritative. The frontend filters navigation using the current session permissions, while backend authorization remains authoritative for every protected route and action.** Navigation is filtered from the requirement map (§6) and the permissions of the current session, before the navigation is rendered. Showing or hiding an item is a usability decision only.
- **Rules:**
  - An item is shown when its requirement is met.
  - A group (for example Administration) is shown when at least one child is shown, and its own link goes to its first visible child.
  - A section is shown when at least one item is shown; its heading is never rendered over an empty list.
  - Removed items leave no gap, divider or placeholder.
- **Badges** (counts) are shown only on visible items.
- **Rail (tablet):** only visible top-level items appear; the rule is the same.
- **Mobile drawer (NAV-02):** identical filtered navigation. There is no separate mobile list.
- **Command search** (Ctrl+K): searches only the visible items. A hidden page can never appear in results.
- **Minimum navigation:** a member with no permissions still sees Dashboard. The navigation is never empty.
- **Permission removed during a session:** the navigation updates on the next page navigation (server layout) or the next session re-read (§10). The current page is not interrupted until it next talks to the API or navigates.
- **Accessibility:** the existing `AppNavigation` semantics (labelled `nav`, `aria-current`, disclosure buttons) are unchanged. Filtering changes the content, not the structure.

### 8.5 SESSION-01 — Role and permission context in the account menu

- **UserMenu header** (all widths; on mobile the menu is the same DropdownMenu):
  1. the display name;
  2. the email (wraps);
  3. the active institute name;
  4. a line **"Roles: {names}"**, listing `roles[].name` in the order received, comma-separated and wrapping, as plain text (`text-body-sm text-text-secondary`). There are no badges and no colour coding.
- **No role** (empty list): the line reads **"No role assigned in this institute"**. The member still sees the Dashboard (§8.6).
- **`is_system`** is not shown as a label in T01. It is used only by later administration screens (T01-08).
- **Never shown:** permission codes, role IDs or other institutes' roles. There is no "My permissions" view in T01.
- The roles line updates whenever the session is re-read. After an institute switch it shows the new institute's roles only (full reload, T01-04).

### 8.6 DASH-01 — Permission-filtered dashboard

- **A section the member lacks permission for is hidden, not shown as unavailable.** Locked or empty cards for unavailable modules confuse people and advertise features.
- The dashboard grid reflows. Layout primitives handle the column count (layout.md §5), with no gaps.
- **When no section is visible** (T01: every business section is `UNRELEASED`, so this is the T01 dashboard), the content area shows `EmptyState` (`titleAs="h2"`, icon `CompassIcon`):
  - title **"Your dashboard is empty for now"**;
  - description **"Sections appear here as your institute uses MTI 360 and your access includes them."**;
  - no action.
- **Each visible section** handles its own loading (skeleton) and errors (ErrorState in the section) independently. One failing or denied section never blanks the page.
- **A section denied at load time** (`403` from its API) is **removed** from the page and RESOURCE-01's session re-read runs. No toast for a section the member did not act on.

### 8.7 CAMPUS-01 — Campus-aware resource access (D-B1)

- **The active campus is a view filter.** Lists show the active campus by default (or all campuses when "All campuses" is active). It is **not** an access boundary: a member whose access covers several campuses may open a record from another permitted campus through a direct link or search. The UI shows it normally.
- **The record's campus is shown** on detail pages that have campus data (name, as text). It tells the user which campus the record belongs to, not whether access is restricted.
- **Never imply** "you can only see your current campus". There is no message about campus restrictions in lists.
- **A campus outside the member's access** answers `404` → RESOURCE-02. The UI never says that the record belongs to another campus.
- **Tenant-wide pages** (members, roles, audit, institute profile, creating campuses) need all-campus access (D-B1). A member with restricted campuses does not have these permissions, so the items are hidden. If such a page is reached directly, the server answers with AUTHZ-01. No campus-specific wording is needed.
- **Campus switching** follows T01-04 §8.8 unchanged: the page data is re-fetched and the permissions stay the same. A campus switch never re-reads or changes navigation visibility.

## 9. Hide, disable or handle 403

| Situation | Convention |
|---|---|
| Navigation item or page the member lacks permission for | **Hide** (§8.4) |
| Primary page action (Create, Invite, Assign), row action, menu item, destructive action the member lacks permission for | **Hide.** An action bar or menu left with no actions is not rendered. A row-actions menu with no items is not rendered |
| Action the member has permission for but which is unavailable for a **non-permission** reason (a record state, a validation precondition) | **Disable**: `isDisabled`, with the reason as visible text next to the control (`text-body-sm text-text-muted`), never only in a Tooltip. Disabled controls are not focusable, so a tooltip on them would be unreachable by keyboard |
| Action the UI showed but the API refuses | **Handle 403** (RESOURCE-01) |

**Disabled controls are never used to express a missing permission in T01.** If a later screen needs "discoverable but not permitted", it must be specified in that screen's contract with visible explanatory text (not a tooltip), and the text must not name the permission or a role.

Section headers, empty states and helper text must stay meaningful when their actions are hidden. For example, an EmptyState whose only action is hidden shows title and description only. It never says "Click Create to…" when Create is hidden.

## 10. Permission changes during a session

The backend recomputes permissions on every request (T01-05). The UI re-reads the session:

1. on every page navigation (server layout, §7);
2. when the tab becomes visible again (T01-04 §8.8 "Other tabs");
3. after any `403 PERMISSION_DENIED` (RESOURCE-01);
4. after any `403 SESSION_REFRESH_REQUIRED` (§11).

It never polls.

| Change | What the member experiences |
|---|---|
| A. Permission remains | Nothing |
| B. Permission removed | The next action needing it → RESOURCE-01, then session re-read: the navigation and actions update. The next navigation to the page → AUTHZ-01 |
| C. Role removed (some permissions lost) | As B for each lost permission. The roles line updates on re-read |
| D. Membership suspended | The API answers `401` (session resolution drops the institute) → T01-04 handling: the session read shows no active institute → `/select-institute`, or `/session-ended` if the session is gone |
| E. Membership revoked | As D |
| F. Institute becomes inaccessible | As D (T01-04 §8.5 "No longer available" when choosing) |
| G. `SESSION_REFRESH_REQUIRED` | §11 |

No cached permission set ever outlives a session re-read.

## 11. Error matrix inside the Tenant Application (`/app/*`)

This applies to every API call made by tenant pages. The session routes (`/auth/*`, `/session/*`) keep T01-04 §10.2.

| Response | Page load (data for the page) | Action (form, dialog, button) |
|---|---|---|
| `401 AUTHENTICATION_REQUIRED` | Re-read the session. No session → `/session-ended?reason=ended&next=<path>`. No institute → `/select-institute`. Campus selection required → `/select-campus` (T01-04) | Same |
| `403 PERMISSION_DENIED` | AUTHZ-01 replaces the page body, then session re-read | RESOURCE-01 (Alert in forms, otherwise toast), then session re-read |
| `403 SESSION_REFRESH_REQUIRED` | Re-read the session (gets a fresh CSRF token). Session valid → retry the **GET** once automatically. Invalid → `401` handling | Re-read the session. Valid → `Alert tone="warning"` in the form or dialog (or a toast outside forms): **"Your session was refreshed. Try again."** with a **"Try again"** button that resends the same request **once** with the new token. Unsafe requests are never resent automatically. Invalid → `401` handling |
| `404 NOT_FOUND` | RESOURCE-02 | `toast.info("This item is no longer available.")`, close the dialog, re-fetch the list |
| `409 CONFLICT` | Not applicable | `Alert tone="warning"`: "This was changed by someone else. Reload it and try again." with "Reload" (re-fetch the record; the form is reset) |
| `422 VALIDATION_ERROR` | Not applicable | Field errors through `Form validationErrors`; focus on the first invalid field (accessibility.md §5) |
| `429 RATE_LIMITED` | `ErrorState` "Too many requests" — "Wait a moment and try again." with Retry (enabled after `Retry-After` seconds when present, otherwise immediately) | `Alert tone="warning"` "Too many attempts. Wait a few minutes before trying again." (T01-04 wording) |
| `503 SERVICE_UNAVAILABLE` | `ErrorState` "This service is temporarily unavailable" — "Please try again shortly." with Retry | `toast.error("This service is temporarily unavailable. Please try again shortly.")` |
| `500` or other, network failure | `ShellError` (existing: fixed text, Retry, reference = request ID) | `toast.error("Something went wrong. Try again in a moment.")` |

- Never displayed: the server `message`, permission codes, role names, IDs other than the support reference, or any wording that refers to another institute or campus.
- Toasts: error toasts persist until dismissed (existing Toast contract). One toast per failed action; repeated identical failures within 5 seconds are deduplicated.

## 12. Frontend authorization abstraction (behaviour, not code)

Home: `frontend/src/lib/` (repository-structure.md: "api client, session helpers, PermissionGate (UX only)"). There is no new state library; the session is server state.

| Piece | Behaviour |
|---|---|
| Server session helper | Reads the session for the request (server components and the experience layout). It is the only source for §7 and the navigation filter |
| Client session context | Provided by the tenant layout from the server read, and replaced on every re-read (§10). It exposes the state in §5 |
| `can(code)`, `canAny(codes)`, `canAll(codes)` | Pure selectors over `permissions`. Unknown codes → `false`. No wildcard or prefix matching |
| `PermissionGate` (**NEW COMPONENT**, `lib/`, UX only; listed in DESIGN-SYSTEM.md §69 and deferred since T00-07) | Renders its children when the requirement is met and **nothing** otherwise (§9: hide). It has no "disabled" mode and no fallback content in T01 |
| Route requirement check | Uses the same requirement map as the navigation (§6), on the server |
| No `hasRole` | Role names are for display (§8.5). There is deliberately no role-based gating helper |

**NEW COMPONENT summary:** only `PermissionGate`. AUTHZ-01 uses `ErrorState`, RESOURCE-02 uses `EmptyState`, and the experience not-found view is a route file, not a component.

## 13. Security requirements

| # | Requirement |
|---|---|
| S1 | Frontend checks are advisory; the API and RLS are authoritative (§3) |
| S2 | Permissions and roles come only from the current session read; they are never stored in or read from `localStorage`, `sessionStorage`, URL parameters, or client-readable cookies |
| S3 | No tenant, campus or role ID from browser input is ever treated as authority (T01-04 S1) |
| S4 | Permission codes, role names and requirements never appear in URLs, page titles or error messages |
| S5 | Denials and not-found states never reveal another institute or campus (§8.1, §8.2) |
| S6 | Client state cannot escalate: changing the client permission set at most reveals controls whose requests the API refuses |
| S7 | Institute switch is a full document navigation (T01-04); no permission, role or data state of the previous institute survives |
| S8 | Navigation filtering uses the current session permissions only and is a usability measure; every protected route and action is authorized by the backend regardless of what the navigation shows (§8.4) |
| S9 | Protected page content is not rendered before the server-side requirement check (§7) |

## 14. Accessibility and responsive contract

**Accessibility (WCAG 2.2 AA, accessibility.md §14 applies to every state):**
- AUTHZ-01 and RESOURCE-02:
  - exactly one `h1` (visually hidden, as in `ShellError`); the visible state title is an `h2`;
  - a unique `<title>`, announced by the route announcer;
  - on client navigation, focus moves to the `h1`;
  - actions are real links or buttons with visible focus.
- RESOURCE-01: in forms, `Alert role="alert"` receives focus. Toasts use the existing landmark region (F6) and announce politely.
- Hidden items are removed from the DOM (not `display: none` with focusable children), so the tab order and the screen-reader reading order have no gaps.
- Disabled-for-reason controls (§9) carry their reason as visible text associated with `aria-describedby`.
- No colour-only meaning: the lock icon is decorative, and text carries the meaning.
- Reduced motion: no new motion.

**Responsive** (layout.md breakpoints; the tenant application is desktop-first):

| Width | Behaviour |
|---|---|
| 390–767 | Filtered drawer navigation (NAV-02). AUTHZ-01 and RESOURCE-02 actions are full width. The UserMenu roles line wraps |
| 768–1023 | Filtered rail plus drawer |
| 1024+ | Filtered sidebar. A group with all children hidden is absent, and sections close up without gaps |

No horizontal overflow at 390px with long role names (they wrap) or long institute names.

## 15. Amendments to the frozen T01-04 UI contract

1. **Session read (T01-04 §15):** add `permissions` and `roles` (§5). They are additive; every existing field is unchanged.
2. **Error mapping (T01-04 §10.2, column "Inside `/app`"):**
   - `403 PERMISSION_DENIED` → AUTHZ-01 or RESOURCE-01 (§11).
   - `403 SESSION_REFRESH_REQUIRED` (the code T01-04 introduced for OQ-5) → §11.
   - The `/auth/*` and `/session/*` columns are unchanged.
3. **UserMenu (T01-04 §8.8):** the header gains the active institute and the roles line (§8.5).

Nothing else in T01-04 changes.

## 16. Frontend test contract (T01-09)

| Area | Tests |
|---|---|
| Requirement map | Every tenant navigation item and page declares exactly one requirement (fails otherwise). `UNRELEASED` items are hidden in a production build and visible in development |
| Navigation | With `campus.read` only: Campuses visible, Users/Roles/Audit/Institute hidden, Administration group shown, empty sections absent. With no permissions: only Dashboard. The rail and mobile drawer show the same items. Command search returns only visible pages. Hidden items are not rendered in the navigation (desktop, rail, drawer) |
| Routes | An allowed route renders the page. A denied route renders AUTHZ-01 with the URL unchanged and no protected markup in the response. An unknown route, an `UNRELEASED` route in production, and an API `404` all render the identical RESOURCE-02. A typed URL cannot bypass the check |
| Actions | `PermissionGate` hides actions without the permission. An action bar with no actions is not rendered. A `403` on a form action shows the Alert and keeps the values. A `403` on a row action shows one toast (deduplicated). Both trigger a session re-read |
| Session | Login and session reads populate `permissions` and `roles`. An institute switch replaces them (full reload; nothing from institute A remains). A campus switch re-fetches page data without changing permissions. After a permission is removed on the server, the next action shows RESOURCE-01 and the navigation updates. `SESSION_REFRESH_REQUIRED` on a GET retries once; on a POST it shows "Try again" and resends only on click |
| Errors | Each row of §11 for page loads and actions. No server message, permission code or role name in the DOM |
| Security | Permissions are never read from `localStorage` or URL (tests set them there and assert no effect). No role-name gating exists (static check) |
| Accessibility | axe has 0 violations on AUTHZ-01, RESOURCE-02 and the filtered navigation in Light and Dark. Focus is on the `h1` after client navigation. One `h1`. Keyboard walk of the filtered navigation. Alert focus on form denial |
| Responsive | 390, 768, 1024 and 1440: no overflow, no empty gaps, wrapped roles line |

## 17. Open questions

| ID | Question | Classification | Default in this specification |
|---|---|---|---|
| OQ-1 | Human names of the system roles shown in the roles line (template names chosen by the T01-05 implementation, for example "Institute owner", "Administrator") | Non-blocking | Show `name` exactly as returned |
| OQ-2 | Should a future "request access" action exist on AUTHZ-01? | Non-blocking (no backend in T01) | No action |
| OQ-3 | Should a member without any role be warned more prominently than by the roles line? | Non-blocking | The roles line and the empty dashboard are enough |
| OQ-4 | Detail-page requirements for pages not in the navigation (record detail pages) | Non-blocking | Each future page declares its requirement in its own screen contract, using §6 |

There are no blocking questions: every behaviour depends only on the locked decisions D-B1 to D-B4, the session fields in §5 and the existing error envelope.

## 18. Acceptance criteria (for freezing and for T01-09)

1. Every state in §4 is implemented as specified in §8, with the exact copy.
2. The requirement map (§6) is the single source for navigation, command search and page access. `UNRELEASED` items are unreachable outside development.
3. No protected page content is rendered before the server-side requirement check (§7, S9); navigation filtering follows §8.4 and S8, with the backend authorizing every protected route and action.
4. AUTHZ-01 and RESOURCE-02 are distinct, and RESOURCE-02 is identical for missing, cross-tenant and out-of-scope-campus resources.
5. The UI never gates on role names, and never reads permissions from browser storage or URLs.
6. Permission changes, institute switches and campus switches behave as in §8.7, §10 and §15.
7. The §11 error matrix is implemented for page loads and actions.
8. The accessibility and responsive contract (§14) and the test contract (§16) pass.
9. No T01-08 administration screen, platform UI or student UI is introduced.

## 19. Change log

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-10-02 | First specification (design only). Adds AUTHZ-01, RESOURCE-01, RESOURCE-02, NAV-01, NAV-02, SESSION-01, CAMPUS-01 and DASH-01; amends T01-04 §8.8, §10.2 and §15 (additive) |
