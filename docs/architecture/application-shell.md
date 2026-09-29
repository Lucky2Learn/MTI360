# Application Shell & Experience Routing (T00-08)

- **Status:** `READY_FOR_REVIEW` (T00-08, 2026-09-28)
- **Code:** `frontend/src/shells/` (import from `@/shells`); routes in `frontend/src/app/{platform,app,student,site}/`
- **Related:** CLAUDE.md §4–§8, §13–§19, §25–§26, §38; [repository-structure.md §2](repository-structure.md#2-frontend-architecture); [components.md](components.md); ADR-0003, ADR-0004, ADR-0005; INC-26, INC-27, INC-28

The shell is the structural frame of the four product experiences. It is **structural only**: it does not authenticate, authorize, resolve a tenant, or read any identifier from the browser. Later phases enforce access server-side at the route boundaries described here and replace the demo account and notification data with server-provided data.

## 1. Route boundaries

| Path | Experience | Shell | Pages today |
|---|---|---|---|
| `/` | Neutral root page (unchanged). **Not** the MTI 360 marketing website (INC-26). | — | 1 |
| `/platform/*` | Platform Administration (SaaS control plane) | ApplicationShell, collapsible sidebar | 7 placeholders |
| `/app/*` | Tenant Application (one institute) | ApplicationShell, collapsible sidebar, nested modules | 76 placeholders |
| `/student/*` | Student Portal (mobile-first) | ApplicationShell, fixed desktop sidebar, no command search | 10 placeholders |
| `/site/*` | Tenant Public Website preview (no tenant yet; INC-27) | PublicSiteShell | 5 placeholders |
| `/design-system` | Component showcase | — | development/test only; **404 in production** (gate unchanged) |

- Each experience has `layout.tsx` (server component; `robots: noindex, nofollow`), `[[...slug]]/page.tsx`, `loading.tsx` and `error.tsx`.
- Pages are **exactly** the pages in the experience's navigation configuration (`generateStaticParams`, `dynamicParams = false`); any other path below a boundary is a 404.
- No tenant identifier appears in any route (ADR-0005). No authentication guards, authorization checks, tenant resolution or proxy/middleware exist yet.
- The marketing website (`index.html`, `app.js`, `styles.css`) is not served by Next.js and was not changed; its hosting is an open decision (INC-26).

## 2. Experience framework

`shells/experiences/` holds one typed configuration per experience and a registry:

```text
EXPERIENCE = { PLATFORM: "platform", TENANT: "tenant", STUDENT: "student", PUBLIC_SITE: "public-site" }

ApplicationExperience  label, basePath, navigationLabel, navigation, pageWidth,
                       sidebar ("collapsible" | "fixed"), search, notifications,
                       demo { account, notifications }
PublicExperience       label, basePath, navigationLabel, navigation, pageWidth
```

- `getExperience(id)`, `resolveExperiencePage(id, slug)` (item + breadcrumb trail, or `null` → 404), `experienceStaticParams(id)`.
- Layouts pass only the experience **id** to the client-side `ExperienceFrame`, which resolves the configuration (it contains icon components) and renders `ApplicationShell` or `PublicSiteShell`.
- Navigation is configuration. Later phases filter it **server-side** by role, permission, subscription and feature entitlement; the backend still authorizes every request (CLAUDE.md §10, §62).
- Demo data is generic (for example "Institute administrator · Demo account") and realistic maritime notification text; there is no real identity and no tenant data.

## 3. Components

| Component | Purpose | Built on |
|---|---|---|
| `ApplicationShell` | Skip link → header → sidebar → `main#main-content` → global `ToastRegion` | composition |
| `AppHeader` | Sticky 64px bar: MTI 360 identity (links to the experience home), experience label (hidden on mobile), navigation trigger slot, utilities slot | — |
| `AppSidebar` | Fixed column below the header. `collapsible`: 64px icon rail on tablet; 256px on desktop with Collapse/Expand. `fixed`: desktop only. Exposes `sidebarOffset()` for the main column | AppNavigation, IconButton |
| `AppNavigation` | `<nav aria-label>`; labelled section lists; links with `aria-current="page"`; one nesting level under a disclosure button (`aria-expanded`, `aria-controls`; the branch with the current page opens); badges with a screen-reader description; `full` / `rail` / `auto` display | native links (`next/link`) |
| `MobileNavigation` | Navigation in a left Drawer below the desktop breakpoint; closes when a link is followed | Drawer, IconButton |
| `Breadcrumbs` | `<nav aria-label="Breadcrumb">` + `<ol>`; last item `aria-current="page"` (not a link); middle items collapse to an ellipsis on mobile; labels truncate | `next/link` |
| `PageHeader` | Breadcrumbs → single `h1` + status → description → actions (stacked on mobile, primary on top; from tablet beside the title while it keeps ≥ 24rem, otherwise wrapped below it — T00-09) → secondary content | Breadcrumbs, ActionBar |
| `PageContainer` / `PageContent` | Content column: `narrow` (48rem, T00-09), `standard` (72rem), `wide` (80rem), `full`; padding 16/24/32px; sections 24 → 32px apart. Widths and gutter are the layout conventions in [layout.md](layout.md) | design-system/layout |
| `SkipNavigation` | First tab stop, visible on focus (44px tall), moves focus to `main` without changing the URL | — |
| `UserMenu` | Account menu: Profile, Preferences, Help, Sign out. Preferences opens the existing `ThemeSelector` in a Dialog. Sign out / Profile / Help explain they are not available yet | DropdownMenu, Dialog, ThemeSelector, Toast |
| `NotificationCenter` | Bell with unread count in its name; list with read/unread (dot, weight, "Unread" prefix — not colour alone); mark one/all read; empty state. Static data via props | Popover, EmptyState, IconButton |
| `CommandSearch` | Header entry point and Ctrl+K / ⌘K; Dialog that finds pages of the current experience (with the parent group for repeated labels); announced result count; Enter opens the first match | Dialog, Search |
| `ShellLoading` / `ShellError` | Route `loading.tsx` / `error.tsx` bodies. The error view shows fixed, user-safe text, Try again (`retry`), Go to home and the opaque digest as a reference — never the error message or stack | LoadingRegion, Skeleton, ErrorState |
| `PublicSiteShell` | Public frame: identity, top navigation (desktop), drawer (below desktop), footer with the theme control; no account, notifications or MTI 360 identity | MobileNavigation, ThemeSelector |
| `ExperienceFrame` | Chooses and configures the shell for an experience id; mounts `NavigationProvider` with the Next.js router | NavigationProvider |
| `NavigationProvider` (design system, `components/Router`) | Framework-neutral wrapper of React Aria's `RouterProvider`: `Button href` and menu links navigate client-side | React Aria |
| `ExperiencePlaceholder`, `ToastExample` | Placeholder page body (states the module is not built); example toast on experience home pages. Removed as modules are built | PageHeader, EmptyState, Button |

Mapping to specification names: AppShell = `ApplicationShell`; Sidebar = `AppSidebar` + `AppNavigation`; TopBar = `AppHeader`; Breadcrumb = `Breadcrumbs`; GlobalSearch = `CommandSearch` (entry point only). PlatformShell / TenantShell / StudentShell are `ApplicationShell` configured by `ExperienceFrame`, not separate components (INC-28). TenantContext, CampusSwitcher and the support-session banner slot need authentication and tenancy and are not built.

Rules:

- Shell code uses design-system components; it imports no React Aria or Lucide directly (guards unchanged). Interactive navigation uses native links and buttons.
- Semantic tokens only; no `dark:` variant, no arbitrary values, no new tokens. Tailwind's `not-sr-only` resets padding, so elements that become visible restate their padding (skip link, section headings).
- One global `ToastRegion` per page, mounted by the shell (`toast.*()` works anywhere inside it). The showcase keeps its own queue and region.
- The theme runtime (T00-06) is reused unchanged — same provider, storage key `mti360.theme` and pre-paint script.

## 4. Responsive behaviour

| Width | Platform / Tenant | Student | Public site |
|---|---|---|---|
| 390–767 | Header + drawer navigation; icon-only search; 44px targets | Header + drawer | Header + drawer |
| 768–1023 | 64px icon rail + drawer for full labels | Drawer | Drawer |
| 1024–1439 | 256px sidebar, Collapse/Expand to the rail | 256px sidebar | Top navigation |
| 1440+ | Same; content capped at `wide` (80rem) | Content capped at `standard` (72rem) | Content capped at 72rem |

No horizontal page overflow at any width (verified in Chromium, including with the drawer, search dialog, notification popover and toasts open).

## 5. Accessibility

Landmarks: `banner`, `navigation` (labelled per experience), `main`, `contentinfo` (public site), toast `region`. Skip link first. One `h1` per page. Keyboard: Tab order follows the visual order; Enter/Space operate disclosures; Escape closes drawer, menu, popover and dialogs with focus returned to the trigger; Ctrl+K / ⌘K opens search. Visible focus ring (2px, semantic `focus-ring`) in both themes. Reduced motion removes transitions. Unit tests run axe on every component; Chromium runs axe (WCAG 2.2 AA + best practices, including contrast) on every experience in Light and Dark at 390/768/1024/1440 and with each overlay open — 0 violations, no rules disabled.

## 6. Not in T00-08

Authentication, sessions, RBAC, tenant resolution, impersonation/support sessions, the proxy, real notifications (backend, polling, WebSocket, push), global/tenant/AI search, tenant branding, the public website builder, business modules, and the responsive layout (T00-09, [layout.md](layout.md)) and accessibility foundation (T00-10) tasks.
