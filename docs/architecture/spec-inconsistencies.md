# Specification Inconsistencies

- **Status:** Open register (created in T00-01, 2026-09-26)
- **Rule:** inconsistencies are **recorded here, not silently resolved** (CLAUDE.md §2, §88). Each entry is closed only by an explicit documentation task or ADR, and the closing change is noted in the entry.

| Status legend | Meaning |
|---|---|
| `OPEN` | Not resolved; specifications disagree |
| `DECIDED-BY-ADR` | An ADR sets the engineering direction; the older specification text still needs a documentation update |
| `CLOSED` | Specifications updated and consistent |
| `RESOLVED` | An implementation defect recorded here was fixed in the named task and verified; no specification change was needed |

---

## INC-01 — Screen count

- **Status:** `OPEN`
- **Where:** UI-SCREENS.md §29, DEVELOPMENT-STATUS.md §27, TASKS.md §2, CLAUDE.md §24, PRD.md §96
- **Issue:** Documents state **~222** screens (Platform 53, Tenant ~153, Student 10, Public 6). UI-SCREENS.md actually contains **205** headed screen entries (Platform 53, Tenant 136, Student 10, Public 6).
- **Impact:** Planning and progress metrics.
- **Proposed resolution:** Either add the missing tenant screen specifications or correct the stated totals.

## INC-02 — Superseded phase list in ARCHITECTURE.md

- **Status:** `OPEN` (annotated in T00-01)
- **Where:** ARCHITECTURE.md §60 vs TASKS.md §4, PRD.md §77, CLAUDE.md §81, DEVELOPMENT-STATUS.md §7
- **Issue:** ARCHITECTURE.md §60 lists 13 older phases (Phase 01 Foundation, 03 CRM, 05 Communication, 06 AI Admission, 07 Finance, 08 Academics, …). The other documents use Phases 00–17 in a different order.
- **Current handling:** ARCHITECTURE.md §60 carries a note that TASKS.md is authoritative. The old list is retained.
- **Proposed resolution:** Replace §60's list with a pointer to TASKS.md.

## INC-03 — "Public Website" meaning

- **Status:** `DECIDED-BY-ADR` ([ADR-0003](../adr/0003-marketing-vs-tenant-public-website.md)); specification text still inconsistent
- **Where:** PRD.md §10.4, §60; CLAUDE.md §4.4; UI-SCREENS.md PUB-01…06; TASKS.md Phase 14 (objective and T14-03/T14-05/T14-06); DEVELOPMENT-STATUS.md §22
- **Issue:** PRD/CLAUDE and PUB-01 ("Courses", "Institute credibility") describe a **tenant institute** website. PUB-02 Features, PUB-04 Pricing, PUB-05 Request Demo and the Phase 14 objective ("Create the MTI 360 marketing and acquisition experience") describe **MTI 360's own** marketing site.
- **Direction:** Phase 14 / PUB-* = Tenant Public Website. MTI 360 marketing website = separate Marketing Website Track (`MKT-*`).
- **Proposed resolution:** Rewrite the PUB-* screen list and the Phase 14 objective/tasks for the tenant public website (e.g. institute home, courses, course detail, eligibility & fees, admissions/enquiry, contact) — a **product-scope decision** requiring approval.

## INC-04 — Marketing website status not recorded

- **Status:** `CLOSED` in T00-01
- **Where:** DEVELOPMENT-STATUS.md
- **Issue:** The existing root landing page was not recorded anywhere in the status tracker.
- **Resolution:** Recorded as PROTO-01 (Prototype: YES, Production Ready: NO) in DEVELOPMENT-STATUS.md §47.

## INC-05 — API path conventions

- **Status:** `DECIDED-BY-ADR` ([ADR-0006](../adr/0006-api-prefixes.md))
- **Where:** ARCHITECTURE.md §35 (`/api/v1/*`) vs PLATFORM-ADMIN.md §91 (`/platform/api/*`, `/api/tenant/*`)
- **Direction:** `/api/v1/platform/*`, `/api/v1/*` (tenant), `/api/v1/student/*`, `/api/v1/public/*`, `/api/v1/webhooks/*`.
- **Proposed resolution:** Update PLATFORM-ADMIN.md §91 examples.

## INC-06 — Tenant role names

- **Status:** `OPEN` — must be resolved before business role templates are seeded (Phase 04)
- **Where:** CLAUDE.md §11 vs PRD.md §85
- **Issue:** CLAUDE.md lists Tenant Admin, Admissions Manager, Counsellor, Faculty, Finance User, Compliance User, Placement User, Communication User, AI Manager, Analyst. PRD.md lists INSTITUTE_OWNER, DIRECTOR, PRINCIPAL, ADMIN, ADMISSION_MANAGER, COUNSELLOR, ACCOUNTS, FACULTY, COMPLIANCE, PLACEMENT, MARKETING, **STUDENT**. PRD includes STUDENT as a tenant role although the Student Portal is a separate experience and realm (ADR-0005).
- **Proposed resolution:** Agree one canonical system-role template list; model students as a separate realm rather than a staff role.
- **T01-00 update (still `OPEN`, wider):** The T01-00 prompt adds a third list: Tenant Owner, Tenant Admin, Admissions, Academic, Finance, Compliance, Placement, Communication, Faculty, Staff. Decision D7 (ADR-0011): T01 seeds only the templates `INSTITUTE_OWNER` and `ADMIN`. Roles are per-tenant data cloned from code templates, so business templates can be added later without changing authorization. Students are a separate realm (ADR-0005), never a tenant role.

## INC-07 — Subscription plan names

- **Status:** `OPEN`
- **Where:** PRD.md §71 (Starter / Growth / Professional / Enterprise) vs PLATFORM-ADMIN.md §40 (Starter / Professional / Business / Enterprise)
- **Proposed resolution:** Commercial decision; plans are data, so this blocks seeding only, not architecture.

## INC-08 — Identity model and session mechanism

- **Status:** `DECIDED-BY-ADR` ([ADR-0005](../adr/0005-identity-and-session-realms.md))
- **Where:** ARCHITECTURE.md §10 ("Session / JWT"), §32 (`users`, `tenant_users`); PLATFORM-ADMIN.md §15 (separate platform login)
- **Issue:** Whether platform administrators share the `users` table, and whether sessions or JWTs are used, was unspecified.
- **Direction:** Separate `platform_users`; opaque server-side sessions. ARCHITECTURE.md §10 carries a T00-01 note.
- **Proposed resolution:** Update ARCHITECTURE.md §32 identity table list when Phase 01 models are designed.
- **T01-00 update:** The Phase 01 identity tables are decided: `users` (identity) separated from `user_credentials`; `platform_users` separated from `platform_user_credentials`; `tenant_memberships` replaces `tenant_users`; sessions in `user_sessions` / `platform_sessions` ([ADR-0010](../adr/0010-sessions-credentials-and-csrf.md), D14 amended). ARCHITECTURE.md §32 is updated in T01-10, once the tables exist.

## INC-09 — Status vocabularies

- **Status:** `OPEN`
- **Where:** CLAUDE.md §83 (Specification Ready, Design Ready, Prototype, Implemented, Tested, Verified, Production Ready) vs TASKS.md §5 / DEVELOPMENT-STATUS.md §4 (NOT_STARTED, IN_PROGRESS, BLOCKED, READY_FOR_REVIEW, COMPLETED, DEFERRED)
- **Proposed resolution:** Define how the two vocabularies map (task status vs maturity level), or adopt one.

## INC-10 — T00-01 Definition of Done

- **Status:** `CLOSED` in T00-01
- **Where:** TASKS.md T00-01
- **Issue:** "Repository builds successfully" cannot apply before any buildable project exists.
- **Resolution:** TASKS.md T00-01 amended: criterion not applicable; transfers to T00-02.

## INC-11 — Document priority order

- **Status:** `OPEN`
- **Where:** CLAUDE.md §2 vs MASTER-CLAUDE-DESIGN-PROMPT.md §2
- **Issue:** CLAUDE.md is the engineering constitution with security as highest priority. MASTER-CLAUDE-DESIGN-PROMPT.md lists CLAUDE.md **last** in its interpretation order.
- **Proposed resolution:** Clarify that the design prompt's order applies to design interpretation only, and that security and engineering rules in CLAUDE.md always prevail.

## INC-12 — Typography

- **Status:** `DECIDED-BY-ADR` for the application ([ADR-0007](../adr/0007-styling-tailwind-semantic-tokens.md), T00-06): no monospace font is added; `--font-mono` uses the system monospace stack. The marketing website remains out of scope.
- **Where:** DESIGN-SYSTEM.md §17 (Inter preferred, Plus Jakarta Sans alternative) vs the marketing website (Plus Jakarta Sans + JetBrains Mono)
- **Issue:** JetBrains Mono is not in the design system. The application must follow DESIGN-SYSTEM.md; the marketing site is not changed by T00-01.
- **Proposed resolution:** Decide whether a monospace family is added to the design system (e.g. for identifiers and code) during T00-06.

## INC-13 — Responsive verification widths

- **Status:** `OPEN` (minor)
- **Where:** DESIGN-SYSTEM.md §21 (four tiers: 390–767, 768–1023, 1024–1439, 1440+) vs TASKS.md T00-09 (verify 390, 640, 768, 1024, 1280, 1440+)
- **Issue:** Compatible (TASKS adds intermediate widths) but not stated explicitly.
- **Proposed resolution:** State in DESIGN-SYSTEM.md that 640 and 1280 are intermediate verification widths, not breakpoints.

## INC-14 — "ACRS" reference

- **Status:** `OPEN`
- **Where:** ARCHITECTURE.md §73
- **Issue:** "ACRS" is named as another product reusing the agent platform but is undefined in every other document.
- **Proposed resolution:** Define it or remove the reference; does not affect MTI 360 implementation.

## INC-15 — "Billing" overloaded

- **Status:** `DECIDED-BY-ADR` (naming in [repository-structure.md](repository-structure.md#3-backend-architecture))
- **Where:** PLATFORM-ADMIN.md (PLAT-13 Billing & Invoices), UI-SCREENS.md ADMIN-11 Billing, FIN-* screens, PRD.md §38 Finance
- **Issue:** "Billing" refers both to MTI 360 billing its tenants (SaaS billing) and to institutes charging students (fees).
- **Direction:** Backend module `billing` = SaaS billing; module `finance` = student fees.
- **Proposed resolution:** Use "Subscription billing" and "Student fees / Finance" consistently in screen names.

## INC-16 — README listed as a source document but empty

- **Status:** `CLOSED` in T00-01
- **Where:** README.md (previously a 3-byte UTF-8 BOM)
- **Resolution:** README.md rewritten in T00-01.

## INC-17 — Specification colours below WCAG 2.2 AA text contrast

- **Status:** `DECIDED-BY-ADR` ([ADR-0007](../adr/0007-styling-tailwind-semantic-tokens.md), T00-06); DESIGN-SYSTEM.md not changed
- **Where:** DESIGN-SYSTEM.md §6–§8 (Sea Glass "primary interaction", semantic primaries on their surfaces, Brass) vs §63–§64 and CLAUDE.md §38 (WCAG 2.2 AA)
- **Issue:** Used as text, several specification colours are below 4.5:1: Sea Glass #168F91 on white 3.91:1 (white text on #168F91 also 3.91:1), #1CA7A5 on white 2.95:1; warning #B7791F on #FFF4DD 3.33:1; success #21875A on #E5F4EC 3.95:1; error #C44545 on #FDECEC 4.29:1; info #2774A6 on #E7F2FA 4.47:1; Brass #B88A44 on white 3.11:1. The specification also defines no mid-neutrals, no dark-mode state/AI surfaces and no shadow values.
- **Current handling:** All specification values are kept verbatim as primitives and used for non-text purposes (indicators, borders, focus ring; all ≥ 3:1). Text uses documented derived mixes of palette colours (`*-text`, `link`, neutrals), contrast-tested in Light and Dark. See [design-tokens.md](design-tokens.md).
- **Proposed resolution:** Add the derived text/neutral steps (or equivalent) to DESIGN-SYSTEM.md in a documentation task, and state that Sea Glass #168F91/#1CA7A5 are not for body text or white-on-colour buttons.
- **T00-07A update:** the same rule applies to filled buttons: the specification success colour #21875A with white text is 4.49:1, so the success button uses the derived `success-strong` token.

## INC-18 — Component inventory and Modal vs Dialog

- **Status:** `OPEN` (handled by T00-07 decisions D9 and D12; specifications unchanged)
- **Where:** TASKS.md T00-07 (23 components) vs DESIGN-SYSTEM.md §69 and CLAUDE.md §26 (also IconButton, TimePicker, Checkbox, Radio, Switch, Textarea, Search, PermissionGate, AccessDenied …); TASKS.md lists **Modal** and **Dialog** separately while DESIGN-SYSTEM.md §48 treats "Modals / Dialogs" as one pattern.
- **Current handling:** T00-07 adds IconButton (07A), Textarea and Checkbox (07B) because listed components need them, and defers Radio group, Switch, TimePicker, Search input and PermissionGate/AccessDenied (D12). Modal = generic modal container (sheet on mobile); Dialog = confirmation `alertdialog` built on Modal (D9, 07C).
- **T00-07C update:** the T00-07C implementation prompt set the overlay names used in code: **Dialog** is the generic modal (TASKS.md "Modal"; sizes sm–xl) and **AlertDialog** is the confirmation `alertdialog` (TASKS.md "Dialog"). It also brought Radio group, Switch, TimePicker and Search into 07C and added Popover, Tooltip, DropdownMenu and ContextMenu. Still deferred: PermissionGate / AccessDenied and ChartCard (INC-19).
- **Proposed resolution:** Align the TASKS.md and DESIGN-SYSTEM.md component lists and state the Modal/Dialog distinction in DESIGN-SYSTEM.md.

## INC-19 — Chart palette and chart library undefined

- **Status:** `OPEN` (T00-07 decision D11)
- **Where:** DESIGN-SYSTEM.md §52 ("Charts should use the MTI 360 palette"), §89
- **Issue:** No categorical or sequential chart palette and no chart library are defined.
- **Current handling:** No chart library or chart tokens are added in T00-07. ChartCard, planned for 07C as a frame only (title, legend slot, states, accessible summary and data-table alternative), was not part of the T00-07C implementation scope and is **deferred** to the first chart/dashboard task.
- **Proposed resolution:** Define chart palette tokens (Light/Dark, contrast-checked) and choose a chart library with the first chart screen.

## INC-20 — Locale, date and currency formats unspecified

- **Status:** `OPEN` (T00-07 decision D10)
- **Where:** PRD.md, UI-SCREENS.md (no formats); PLATFORM-ADMIN.md tenant settings (Timezone, Currency); product context India (DGS)
- **Current handling:** Components accept pre-formatted values (KPI, Timeline). DatePicker (07B) formats with locale `en-IN` (DD/MM/YYYY) by default, with a `locale` prop; no timezone conversion in components.
- **T00-07B update — first day of the week:** locale and first day of the week are treated as **separate settings**. The MTI 360 **product default is Monday-first** (T00-07 D10, confirmed by T00-07B D3), even though the CLDR default for `en-IN` is Sunday. DatePicker therefore uses `en-IN` formatting with `firstDayOfWeek="mon"` by default and accepts an explicit `firstDayOfWeek` override. The specifications do not state a first-day convention.
- **T00-07C update — times:** TimePicker uses ISO `"HH:mm"` values (no dates, no time zones) and `en-IN` display, which is 12-hour with leading zeros and lower-case am/pm; `hourCycle` overrides the clock. Pagination formats numbers with `en-IN`. The specifications define no time format and no 12/24-hour convention.
- **Proposed resolution:** Specify default locale, date/time and currency formatting, the 12/24-hour convention, the first day of the week (and whether tenants may change it), and how tenant Timezone/Currency settings apply (Phase 03).

## INC-21 — Button "Tertiary" vs "Ghost" not defined

- **Status:** `OPEN` (T00-07 decision D13)
- **Where:** DESIGN-SYSTEM.md §41 (variants Primary, Secondary, Tertiary, Ghost, Destructive, Success, Icon)
- **Issue:** The difference between Tertiary and Ghost is not described.
- **Current handling:** Tertiary = text-style action (link colour, underline on hover); Ghost = transparent with a hover surface.
- **Proposed resolution:** Describe both variants in DESIGN-SYSTEM.md §41.

## INC-22 — Upload file types and size limits unspecified

- **Status:** `OPEN` (T00-07B decision D7)
- **Where:** CLAUDE.md §50 and ARCHITECTURE.md §49 (server validation pipeline) and §31 (document processing); PRD/UI-SCREENS mention admission documents (CDC, passport, medical certificates) but no allowed types or limits
- **Issue:** No specification defines which file types are accepted or the maximum sizes per document category.
- **Current handling:** FileUpload requires explicit `accept` (MIME + extension pairs) and `maxSize` props with no defaults; a permanent deny list applies regardless. The showcase uses PDF/JPG/PNG up to 5 MB and 2 MB as examples only. Server-side validation remains authoritative.
- **Proposed resolution:** Define accepted types and limits per document category with the document/admissions features.

## INC-23 — Required-indicator and success-state conventions unspecified

- **Status:** `OPEN` (T00-07B decisions D4, D6)
- **Where:** DESIGN-SYSTEM.md §42 (controls need a "Success" state), CLAUDE.md §34 ("required indicators")
- **Issue:** Neither the presentation of the required indicator nor when a success state is shown is defined.
- **Current handling:** a visible `*` after the label (hidden from assistive technology) plus the programmatic required state, and a "* Required field" note on forms; success is opt-in (`successMessage`: icon + text), never automatic.
- **Proposed resolution:** Document both conventions in DESIGN-SYSTEM.md §42.

## INC-24 — Dark error text on elevated surfaces below 4.5:1

- **Status:** `RESOLVED` (T00-10A; found in T00-07C browser verification)
- **Where:** `tokens/semantic.css` (Dark: `error-text` = `error-400` #CF7A7A; `surface-elevated` = `ocean-800` #073B57); DESIGN-SYSTEM.md §8 (semantic colours), CLAUDE.md §38 (WCAG 2.2 AA)
- **Issue:** In Dark mode `error-text` on `surface-elevated` (menus, popovers, dialogs) is 3.79:1 — below 4.5:1 for normal text. It passes on `surface-primary` and on `error-surface` (4.79:1). The other state `*-text` tokens were not assessed on `surface-elevated` in T00-06.
- **Current handling:** No token change (a T00-07C stop condition). Destructive menu items keep the label in `text-primary` at rest with an error-coloured icon (non-text, ≥ 3:1) and show `error-text` only on the `error-surface` focus background. Components must not place `*-text` state text directly on `surface-elevated` in Dark mode.
- **Proposed resolution:** Add a contrast-checked Dark state-text step for elevated surfaces (or lighten `error-text`) in a token task, and extend the token contrast tests to `surface-elevated`.
- **T00-10 update (still `OPEN`, scope wider than first recorded):** The token contrast tests now cover every `*-text` state token on `surface-elevated`. All pass in Light. In Dark **all four** are below 4.5:1 (but ≥ 3:1): `error-text` 3.79, `info-text` 4.03, `success-text` 4.19, `warning-text` 4.22. The four pairs are pinned as documented exceptions in `tokens.test.ts` and must leave the list once fixed. Impact: field error and success messages, or other bare state text, rendered inside a Dialog, Drawer or Popover in Dark mode are below AA until a token task resolves this. Badges and Alerts use their own state surfaces and are not affected. A token change is a T00-10 stop condition, so no token was changed. [accessibility.md](accessibility.md) §10 and §15.
- **T00-10A resolution (`RESOLVED`):** measured again before the change. In Dark, the `*-400` text also failed on `surface-selected` (`seaglass-950`): error 4.00, info 4.25, success 4.42, warning 4.45. `surface-hover` has the same colour as `surface-elevated`. No existing primitive is a lighter step of these hues, so the user approved a narrowly scoped exception: add four derived `*-300` primitives with the documented formula `mix(state-600, ice-100, t)` (success 0.62, warning 0.72, error 0.56, info 0.58; no palette change, no new hue), and remap **only** Dark `success/warning/error/info-text` (Dark block and the no-JavaScript fallback). New Dark ratios on `surface-elevated` / `surface-hover`: error 4.72, info 4.74, success 4.68, warning 4.63; on `surface-selected`: 4.98, 5.00, 4.94, 4.89; every other Dark surface is at least 5.52. Unchanged: every existing primitive and its value, the Light mappings, and the Dark indicators and `success-strong` / `error-strong` fills (still `*-400`). Coverage:
  - `tokens.test.ts` checks every `*-text` against every background and surface in Light and Dark, with no exceptions left, and pins the mappings.
  - `components/state-text.test.tsx` checks the pairs as each component renders them: field error and success, Switch error, Alert, ErrorState, Toast, the destructive menu item, and Dialog, AlertDialog, Drawer and Popover.
  - Chromium measures the computed colours inside a Dialog, Drawer and Popover in Light, Dark and System at 390/768/1024/1440, with axe 0 violations including contrast.

  Details: [design-tokens.md](design-tokens.md) §2, §3, §5 and [accessibility.md](accessibility.md) §10.

## INC-25 — Toast, tooltip and context-menu conventions unspecified

- **Status:** `OPEN` (T00-07C)
- **Where:** DESIGN-SYSTEM.md §49 (notifications), §74; no specification of tooltip or context-menu usage
- **Issue:** The specifications define no toast durations, stacking limit, placement, persistence rules or action behaviour, and no rules for tooltips or context menus.
- **Current handling:** Toasts: success/info 5 s, warning 8 s, error and toasts with an action persist until dismissed (WCAG 2.2.1), at most 3 visible, bottom placement (bottom-end from `tablet`), timers paused on hover/focus. Toasts use React Aria's `UNSTABLE_Toast*` exports (1.21.1 pinned) behind the MTI 360 API. Tooltips: 600 ms hover delay, immediate on keyboard focus, never the only source of information. Context menus: right-click, Shift+F10 and the ContextMenu key; a shortcut only — every action must be reachable another way.
- **Proposed resolution:** Document these conventions in DESIGN-SYSTEM.md §49/§74; re-check the Toast wrapper when React Aria stabilises the toast API.
- **T00-10 update (still `OPEN`; conventions unchanged):** The accessibility conventions for toasts, tooltips and live regions are now documented in [accessibility.md](accessibility.md) §6 and §4. A wrapper defect was fixed along the way: the toast region was not reachable with F6, because React Aria's landmark registration never retried once the region element appeared. The specification gap itself remains.

## INC-26 — Marketing site hosting/integration

- **Status:** `OPEN` (T00-08)
- **Where:** T00-08 implementation prompt (`/` → MTI 360 marketing landing page) vs ADR-0003 (marketing website separate from the application; no code imported into `frontend/`; "convert the landing page to Next.js now" rejected), `frontend/Dockerfile.dockerignore` (the marketing files never enter the frontend build context) and the MKT-01 relocation plan
- **Issue:** Serving the frozen marketing landing page (`index.html`, `app.js`, `styles.css`, tag `marketing-site-v1`) at `/` from the Next.js application would require Docker changes or copies of the files inside `frontend/`, and would contradict ADR-0003.
- **Decision (T00-08, user):** The marketing site remains architecturally separate from the Next.js SaaS application. `/` stays the existing neutral root page. The marketing files and their hashes are unchanged, and the Dockerfile, its ignore file and ADR-0003 are unchanged.
- **Proposed resolution:** A future MKT task and ADR-0009 will determine the marketing site's final hosting/deployment model.

## INC-27 — Tenant Public Website route prefix

- **Status:** `OPEN` (T00-08)
- **Where:** T00-08 implementation prompt and decision (`/site/*`) vs repository-structure.md §2 and ADR-0003 (`/sites/[site]/*`, an internal rewrite target reached through host-based routing, direct access blocked by the proxy)
- **Issue:** T00-08 created the Tenant Public Website structure at `/site/*` as directed. The approved architecture places it at `/sites/[site]/*` with the tenant resolved server-side from a verified domain.
- **Current handling:** `/site/*` is a neutral structural preview (5 placeholder pages, no tenant identity, branding or data, `noindex`). No proxy or rewrite exists.
- **Proposed resolution:** Decide the final route when tenant resolution for public sites is built (Phase 14 / proxy task), then align either the code or repository-structure.md §2.

## INC-28 — Application shell component names

- **Status:** `OPEN` (T00-08)
- **Where:** TASKS.md T00-08 (AppShell, Sidebar, TopBar, PageHeader, Breadcrumb, GlobalSearch, NotificationCenter, UserMenu), CLAUDE.md §26 (also TenantContext, CampusSwitcher), repository-structure.md §2 (PlatformShell, TenantShell + support-session banner slot, StudentShell, PublicSiteShell)
- **Issue:** The documents name the shell pieces differently.
- **Current handling:** One shared `ApplicationShell` (AppShell) configured per experience by `ExperienceFrame` serves as PlatformShell, TenantShell and StudentShell; `AppSidebar`/`AppNavigation` = Sidebar, `AppHeader` = TopBar, `Breadcrumbs` = Breadcrumb, `CommandSearch` = GlobalSearch (entry point only); `PublicSiteShell` as named. TenantContext, CampusSwitcher and the support-session banner slot depend on authentication and tenancy and are not built. Details: [application-shell.md](application-shell.md).
- **Proposed resolution:** Align the names in TASKS.md, CLAUDE.md §26 and repository-structure.md §2 in a documentation task.

## INC-29 — Content widths and layout primitive names

- **Status:** `OPEN` (T00-09)
- **Where:** DESIGN-SYSTEM.md §82 ("typical desktop content width 1200–1440px") vs the T00-08 `PageContainer` widths kept by T00-09 (`standard` 72rem / 1152px, `wide` 80rem / 1280px, `full`); the T00-09 implementation prompt's candidate primitive names (PageLayout, SidebarLayout, ContentLayout, ResponsiveColumns, AspectRatio); TASKS.md T00-09 verification widths (390, 640, 768, 1024, 1280, 1440) vs the prompt's four tiers.
- **Issue:** `standard` is slightly narrower than the §82 range, and the specifications do not name the layout primitives.
- **Current handling:** The widths are unchanged from T00-08 (no visual change to existing pages). A `narrow` (48rem) width was added for focused forms. On desktop the content column also loses 256px to the sidebar, so a wider `standard` would rarely be reached. The layout names are `Container`, `Stack`, `Inline`, `Grid`/`GridItem`, `Section`, `SplitLayout`, `ActionBar` and `Show`. PageLayout is the existing `PageContainer` + `PageHeader` + `PageContent`. SidebarLayout/ContentLayout are covered by `SplitLayout`/`Container`, and AspectRatio is not built (no consumer). Browser verification covers all six TASKS.md widths. Details: [layout.md](layout.md).
- **Proposed resolution:** Confirm or adjust the `standard`/`wide` caps against §82 when the first real pages (T02/T03) are designed, and record the layout names in DESIGN-SYSTEM.md / CLAUDE.md §26 in a documentation task.

## INC-30 — Platform role names

- **Status:** `OPEN` (T01-00)
- **Where:** PRD.md §85 and PLATFORM-ADMIN.md §7 (seven roles: `SUPER_ADMIN`, `PLATFORM_OPERATIONS_ADMIN`, `CUSTOMER_SUCCESS_ADMIN`, `BILLING_ADMIN`, `SUPPORT_ADMIN`, `SECURITY_AUDIT_ADMIN`, `AI_PLATFORM_ADMIN`) vs the T01-00 prompt ("Platform Super Admin", "Platform Admin", "Platform Support")
- **Issue:** Two different platform role sets.
- **Current handling:** Decision D7 (ADR-0011) keeps the seven codes from the specifications. In T01 only `SUPER_ADMIN` and `SECURITY_AUDIT_ADMIN` receive permissions.
- **Proposed resolution:** Confirm the seven-role set in Phase 02, or map the prompt's three roles onto it.

## INC-31 — Phase 01 task breakdown

- **Status:** `CLOSED` in T01-01 (T01-00 decision D1; TASKS.md re-baselined)
- **Where:** TASKS.md Phase 01 (previous T01-01 … T01-12) and ADR-0004 / ADR-0005 status lines, which cite the previous IDs
- **Issue:** The previous breakdown had no database or API foundation task, placed audit after authentication and MFA before platform identity, and had no frontend integration task.
- **Current handling:** Phase 01 is re-sequenced into T01-00 … T01-10. The mapping from the previous IDs is in TASKS.md, Phase 01. The accepted ADRs are not edited.
- **Proposed resolution:** None required; mention the mapping if ADR-0004 or ADR-0005 are ever superseded.

## INC-32 — Tenant lifecycle transitions

- **Status:** `OPEN` (T01-00)
- **Where:** PLATFORM-ADMIN.md §5–§6 and PRD.md §13: a linear diagram plus SUSPENDED → ACTIVE
- **Issue:** The allowed transitions are not specified (for example TRIAL → CANCELLED, PAST_DUE → ACTIVE, or reactivating a CANCELLED tenant).
- **Current handling:** Decision D15: T01 defines all eight states. T01 implements only create, suspend and reactivate. Access is allowed in TRIAL, ACTIVE and PAST_DUE. T01-03 ([ADR-0014](../adr/0014-tenancy-core.md) §5): a new tenant starts in TRIAL; suspend is TRIAL, ACTIVE or PAST_DUE → SUSPENDED; reactivate is SUSPENDED → ACTIVE (so a suspended TRIAL tenant reactivates to ACTIVE).
- **Proposed resolution:** Define the transition matrix in T02-05.

## INC-33 — Login identifier

- **Status:** `OPEN` (T01-00)
- **Where:** APP-FLOW.md §4 ("Enter Email/Mobile") vs security.md and PLATFORM-ADMIN.md §15 (email and password)
- **Issue:** Mobile-number login is mentioned but not specified (verification, uniqueness, OTP delivery).
- **Current handling:** Decision D12: email is the only login identifier in T01 (ADR-0010).
- **Proposed resolution:** Specify mobile or OTP login with the SMS integration (Phase 09) if it is still wanted.

## INC-34 — "institutes" vs "tenants"

- **Status:** `OPEN` (T01-00)
- **Where:** ARCHITECTURE.md §32 (`institutes`, `campuses` under "Institute" and `tenants` under "Identity") vs PRD.md §11 (a tenant **is** a Maritime Training Institute)
- **Issue:** It is unclear whether an institute is a separate entity from the tenant.
- **Current handling:** A tenant is the institute. The institute profile and branding (ADMIN-01, ADMIN-02) will be a 1:1 extension owned by the `institute` module in Phase 03, not a second tenant-like entity.
- **Proposed resolution:** Update ARCHITECTURE.md §32 together with INC-08 in T01-10.

## INC-35 — Audit event fields

- **Status:** `DECIDED-BY-ADR` (T01-02, [ADR-0013](../adr/0013-audit-events.md) §2)
- **Where:** security.md §11 (actor, realm, tenant, action, resource, **result**, timestamp, **`support_session_id`**, **`correlation_id`**, metadata); PRD.md §88 (**campus**, entity, **source**, result); PLATFORM-ADMIN.md §20, §74 (**role**, **IP / session reference**, **reason**, risk, status); tenancy.md §3 (`correlation_id`); T01-02 specification §7 (realm list without `webhook`)
- **Issue:** The specifications list different audit fields. Several fields have no trusted source before support sessions (Phase 02), campus scope (T01-05), sessions (T01-04) or a trusted proxy chain (deployment work). `correlation_id` and `request_id` name the same thing. The `Realm` enum also contains `webhook`, which the T01-02 realm list omits.
- **Current handling:**
  - `audit_events` stores realm, tenant, principal, category, event type, a generic target, `request_id` (the correlation ID, not renamed) and redacted metadata.
  - The result is expressed by the event type (`auth.login_failed`).
  - Support session, campus, role, IP, session reference, reason and risk are not columns yet; a producer may put non-sensitive context in metadata.
  - The realm check uses the complete existing `Realm` vocabulary, including `webhook`, so that a future webhook signature failure can be recorded.
- **Proposed resolution:** Each task that introduces a trusted source adds its column with a migration: `support_session_id` in T02-04 and campus in T01-05 if needed. Align security.md, tenancy.md and PLATFORM-ADMIN.md §74 when PLAT-36 (Platform Audit Logs) is designed.

## INC-36 — Row-Level Security on `tenants`

- **Status:** `CLOSED` in T01-03 ([ADR-0014](../adr/0014-tenancy-core.md) §2; tenancy.md §9 updated)
- **Where:** tenancy.md §9 ("Global tables (no RLS, platform services only)") vs `database/init/01-roles.sh` (the read-only role gets SELECT on every table) and the realm-aware RLS of `audit_events` (ADR-0013)
- **Issue:** Without RLS, any tenant-realm bug, raw query or the read-only role could list every institute.
- **Resolution:** `tenants` has realm-aware RLS: the platform and system realms read every row and are the only realms that insert or update; any other context reads only its trusted tenant's row. The other global tables listed in tenancy.md §9 decide when they are created.

## INC-37 — Accessible tenant statuses differ by surface

- **Status:** `DECIDED-BY-ADR` ([ADR-0014](../adr/0014-tenancy-core.md) §5)
- **Where:** tenancy.md §2 (public host resolution: ACTIVE or TRIAL) vs decision D15 (access in TRIAL, ACTIVE and PAST_DUE)
- **Issue:** The two lists differ, and no document says whether the difference is intended.
- **Current handling:** The status access policy keeps both: the tenant and student realms in TRIAL, ACTIVE and PAST_DUE; the public website in TRIAL and ACTIVE.
- **Proposed resolution:** Confirm with the public-website design (Phase 14).

## INC-38 — `unscoped()` has no consumer

- **Status:** `OPEN` (T01-03)
- **Where:** ADR-0004 layer 3 and tenancy.md §4 (an explicit, platform-only, audited `unscoped()` block) vs ADR-0011 §7 (no platform path to tenant data before support sessions)
- **Issue:** Nothing needs the escape hatch yet, and RLS would return nothing for a platform context without a tenant anyway.
- **Current handling:** T01-03 implements no unscoped path; the ORM filter always fails closed.
- **Proposed resolution:** The first platform consumer (T01-07 or T02-04) adds it, with its audit event and RLS design.

## INC-39 — Platform provisioning cannot write tenant-owned rows

- **Status:** `OPEN` (T01-03)
- **Where:** TASKS.md T01-07 (provisioning creates the primary campus and roles) and security.md §1 ("set at provisioning") vs the realm-agnostic tenant RLS of ADR-0014
- **Issue:** A platform request has no trusted tenant, so RLS rejects its inserts into `campuses` and later tenant tables.
- **Current handling:** No platform write policy on tenant-owned tables in T01-03.
- **Proposed resolution:** T01-07 designs the provisioning write path (for example a named, audited scope that publishes the new tenant in the same transaction) with an ADR.

## INC-40 — Campus status vocabulary

- **Status:** `OPEN` (T01-03)
- **Where:** PLATFORM-ADMIN.md §30 (campus "Status") and UI-SCREENS.md ADMIN-03/04 (no content)
- **Issue:** No campus status values or archival semantics are defined.
- **Current handling:** `campuses` has no status column in T01-03.
- **Proposed resolution:** Define the vocabulary with the campus API (T01-08).

## INC-41 — Campus code uniqueness

- **Status:** `DECIDED-BY-ADR` ([ADR-0014](../adr/0014-tenancy-core.md) §1)
- **Where:** PLATFORM-ADMIN.md §30 lists a campus "Code" without format or uniqueness
- **Issue:** Format, case and uniqueness were unspecified.
- **Current handling:** The code is required, upper case (`^[A-Z0-9][A-Z0-9-]*$`, at most 32 characters) and unique per tenant; the same code may exist in different tenants.
- **Proposed resolution:** Reflect it in PLATFORM-ADMIN.md §30 when the campus screens are specified (ADMIN-03/04).

## INC-42 — Blocklist coverage under the 12-character minimum

- **Status:** `OPEN` (T01-04)
- **Where:** ADR-0010 §7 and T01-04 decision D06 (bundled ~10k common-password list) vs the 12-character minimum of the same policy
- **Issue:** Only 10 of the 10,001 entries of the approved SecLists 10k list are 12 characters or longer, so the length rule rejects almost all of the list on its own. Common long passwords (passphrases, keyboard walks, "password" + digits) are not covered.
- **Current handling:** The approved list is bundled unmodified (identity-authentication.md §5); the file can be replaced without code changes.
- **Proposed resolution:** Choose a larger permissively licensed list filtered to 12+ characters, or an offline breached-password corpus, in a security hardening task (Phase 16), or with the deferred breached-password check.

## INC-43 — Sign-out access level

- **Status:** `DECIDED-BY-ADR` ([ADR-0015](../adr/0015-identity-authentication.md); identity-authentication.md §4.4)
- **Where:** T01-04 decision D12 (sign-out among the `Access.SESSION` routes) vs the frozen UI contract (sign-out answers `204` even without a valid session)
- **Issue:** A session-only route answers `401` when the session has already ended, so sign-out would not be idempotent.
- **Current handling:** `POST /api/v1/auth/logout` is an anonymous route with the same-origin check; it revokes the presented session when there is one and always clears the cookie with `204`.
- **Proposed resolution:** None required.
