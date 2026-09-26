# frontend/

**Status:** Toolchain foundation (T00-02). Contains only a root layout, a neutral root page and a smoke test — no product screens, design tokens or experience routes yet.

## Commands

Run from the repository root (`pnpm dev:frontend`, `pnpm lint:frontend`, …) or inside `frontend/`:

| Command | Purpose |
|---|---|
| `pnpm dev` | Next.js dev server on `localhost:${FRONTEND_PORT:-3000}` |
| `pnpm build` / `pnpm start` | Production build / serve |
| `pnpm lint` | ESLint (Next.js core-web-vitals + TypeScript, type-aware rules, jsx-a11y, import order), zero warnings |
| `pnpm typecheck` | `next typegen && tsc --noEmit` |
| `pnpm test` / `pnpm test:watch` | Vitest (jsdom + Testing Library) |
| `pnpm format` / `pnpm format:check` | Prettier (this directory only) |

Toolchain versions and rationale: [docs/architecture/toolchain.md](../docs/architecture/toolchain.md).

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
- `src/proxy.ts` — host → experience rewrite, security headers (never authorization). Next.js 16 renamed "Middleware" (`middleware.ts`) to "Proxy" (`proxy.ts`).
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
| T00-02 ✅ | Next.js scaffold, `package.json`, TypeScript, ESLint, Prettier and Vitest configuration |
| T00-03 | `Dockerfile` (optional dev container) |
| T00-06 | Design tokens and Light/Dark/System theme |
| T00-07 | Core component library |
| T00-08 | Application shells |
| T00-09 / T00-10 | Responsive and accessibility foundations |
