# MTI 360 Documentation

## Purpose

Supporting documentation for MTI 360: architecture decision records, architecture notes and (later) runbooks.

The **primary specifications stay at the repository root** and remain the source of truth (see [ADR-0002](adr/0002-monorepo-layout.md)).

## Ownership

All engineering. Architecture changes require an ADR (`docs/adr/`) and an update to the affected specification in the same change.

## Specifications (repository root)

Recommended reading order (CLAUDE.md §2):

| # | Document | Role |
|---|---|---|
| 0 | [CLAUDE.md](../CLAUDE.md) | Engineering constitution |
| 1 | [PRD.md](../PRD.md) | Product requirements |
| 2 | [APP-FLOW.md](../APP-FLOW.md) | Application flows |
| 3 | [ARCHITECTURE.md](../ARCHITECTURE.md) | System architecture |
| 4 | [PLATFORM-ADMIN.md](../PLATFORM-ADMIN.md) | SaaS control plane |
| 5 | [DESIGN-SYSTEM.md](../DESIGN-SYSTEM.md) | Visual tokens and components |
| 6 | [UI-SCREENS.md](../UI-SCREENS.md) | Screen inventory |
| 7 | [TASKS.md](../TASKS.md) | Implementation roadmap |
| 8 | [DEVELOPMENT-STATUS.md](../DEVELOPMENT-STATUS.md) | Live implementation status |
| — | [MASTER-CLAUDE-DESIGN-PROMPT.md](../MASTER-CLAUDE-DESIGN-PROMPT.md) | Design-tool brief (not an engineering spec) |

## Architecture Decision Records

| ADR | Title | Status |
|---|---|---|
| [0001](adr/0001-stack.md) | Technology stack | Accepted |
| [0002](adr/0002-monorepo-layout.md) | Monorepo layout | Accepted |
| [0003](adr/0003-marketing-vs-tenant-public-website.md) | MTI 360 marketing website vs tenant public website | Accepted |
| [0004](adr/0004-tenant-isolation.md) | Tenant isolation | Accepted |
| [0005](adr/0005-identity-and-session-realms.md) | Identity and session realms | Accepted |
| [0006](adr/0006-api-prefixes.md) | API prefixes | Accepted |
| [0007](adr/0007-styling-tailwind-semantic-tokens.md) | Styling: Tailwind CSS v4 with semantic design tokens | Accepted |
| [0008](adr/0008-headless-primitives-and-icons.md) | Headless accessible primitives (React Aria Components) and icons (Lucide) | Accepted |
| 0009 | Reserved: marketing website hosting (INC-26) | — |
| [0010](adr/0010-sessions-credentials-and-csrf.md) | Sessions, credentials (identity separated from credentials) and CSRF | Accepted |
| [0011](adr/0011-rbac-model.md) | Role-based access control model | Accepted |
| [0012](adr/0012-application-level-encryption.md) | Application-level encryption of secrets at rest | Accepted |

ADR format: Status, Context, Decision, Consequences, Alternatives considered. ADRs are immutable once accepted; a change is made by a new ADR that supersedes the old one.

## Architecture notes

| Document | Contents |
|---|---|
| [repository-structure.md](architecture/repository-structure.md) | Repository tree, frontend and backend architecture, testing layout, environment files, local infrastructure, Git workflow |
| [tenancy.md](architecture/tenancy.md) | Tenant identification, enforcement layers, leakage vectors, isolation test gate, database conventions |
| [backend-foundation.md](architecture/backend-foundation.md) | Backend foundation: layers and import contracts, database access and transactions, migrations, post-commit side effects, realm routers, API conventions, logging, testing, T01-00 decision record (T01-01) |
| [security.md](architecture/security.md) | Realm boundaries, authentication, authorization, secrets, files, audit, AI tool authorization |
| [environments.md](architecture/environments.md) | Environment matrix: configuration sources, per-environment rules, secret handling, `pnpm check:env` (T00-04) |
| [toolchain.md](architecture/toolchain.md) | Exact runtime and dependency versions, version holds, supply-chain controls, commands, update policy (T00-02) |
| [design-tokens.md](architecture/design-tokens.md) | Token architecture, primitive and derived colours, semantic Light/Dark mapping, type/spacing/radius/elevation/breakpoints, contrast, theme runtime, fonts (T00-06) |
| [components.md](architecture/components.md) | Component library: delivery slices, rules and guards, §73/§74 contract per component, showcase (T00-07) |
| [application-shell.md](architecture/application-shell.md) | Application shell, experience framework and route boundaries (T00-08) |
| [layout.md](architecture/layout.md) | Responsive layout primitives, breakpoints, spacing, content widths and page patterns (T00-09) |
| [accessibility.md](architecture/accessibility.md) | WCAG 2.2 AA contract: keyboard, focus, names, forms, live regions, overlays, tables, motion, contrast, landmarks/headings, testing, screen checklist, known exceptions (T00-10) |
| [ci.md](architecture/ci.md) | CI workflows, required `ci-ok` status, security model, pinned versions, Dependabot scope, local reproduction, future branch protection (T00-05) |
| [spec-inconsistencies.md](architecture/spec-inconsistencies.md) | Known inconsistencies between specifications, recorded for future resolution |

## What does NOT belong here

- Product requirements that belong in the root specifications
- Secrets, credentials or real customer data
- Generated API documentation (produced by the build, not committed)
