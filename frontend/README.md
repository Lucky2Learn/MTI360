# frontend/

**Status:** Reserved. No application code exists yet.

## Purpose

The MTI 360 web application: a single **Next.js + React + TypeScript** (App Router) application serving three authenticated experiences and one public experience:

| Experience | Route tree (planned) | Notes |
|---|---|---|
| Platform Control Plane | `/platform/*` | MTI 360 platform administrators. Separate login, separate session realm. |
| Tenant Application | `/login`, `/app/*` | Maritime Training Institute staff. |
| Student Portal | `/student/*` | Mobile-first student experience. |
| Tenant Public Website | `/sites/[site]/*` | Tenant-branded public institute website, reached only through host-based rewrite. Phase 14. |

See [ADR-0002](../docs/adr/0002-monorepo-layout.md), [ADR-0003](../docs/adr/0003-marketing-vs-tenant-public-website.md) and [repository-structure.md](../docs/architecture/repository-structure.md).

## Ownership

Frontend engineering. Design-token and component changes must follow `DESIGN-SYSTEM.md`.

## What belongs here

- Next.js routes (`src/app/`), kept thin — they compose shells and feature modules
- `src/middleware.ts` — host → experience rewrite, security headers (never authorization)
- `src/design-system/` — semantic tokens, Light/Dark/System theme, core components, page templates T01–T18
- `src/shells/` — PlatformShell, TenantShell, StudentShell, PublicSiteShell
- `src/features/` — UI feature modules that mirror backend modules
- `src/lib/` — typed API client, session helpers, `PermissionGate` (UX only)
- Unit, component and integration tests colocated with the code

## What does NOT belong here

- **The MTI 360 marketing website** (root `index.html`, `app.js`, `styles.css`) — see ADR-0003
- Business rules, authorization decisions or tenant resolution — these are server-side in `backend/`
- Direct database access of any kind
- Secrets. Anything prefixed `NEXT_PUBLIC_` is shipped to browsers and must never contain a secret
- Cross-stack end-to-end suites (those live in `/tests`)

## Populated by

| Task | Adds |
|---|---|
| T00-02 | Next.js scaffold, `package.json`, TypeScript and lint configuration |
| T00-03 | `Dockerfile` (optional dev container) |
| T00-06 | Design tokens and Light/Dark/System theme |
| T00-07 | Core component library |
| T00-08 | Application shells |
| T00-09 / T00-10 | Responsive and accessibility foundations |
