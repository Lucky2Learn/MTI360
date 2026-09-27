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

ADR format: Status, Context, Decision, Consequences, Alternatives considered. ADRs are immutable once accepted; a change is made by a new ADR that supersedes the old one.

## Architecture notes

| Document | Contents |
|---|---|
| [repository-structure.md](architecture/repository-structure.md) | Repository tree, frontend and backend architecture, testing layout, environment files, local infrastructure, Git workflow |
| [tenancy.md](architecture/tenancy.md) | Tenant identification, enforcement layers, leakage vectors, isolation test gate, database conventions |
| [security.md](architecture/security.md) | Realm boundaries, authentication, authorization, secrets, files, audit, AI tool authorization |
| [environments.md](architecture/environments.md) | Environment matrix: configuration sources, per-environment rules, secret handling, `pnpm check:env` (T00-04) |
| [toolchain.md](architecture/toolchain.md) | Exact runtime and dependency versions, version holds, supply-chain controls, commands, update policy (T00-02) |
| [ci.md](architecture/ci.md) | CI workflows, required `ci-ok` status, security model, pinned versions, Dependabot scope, local reproduction, future branch protection (T00-05) |
| [spec-inconsistencies.md](architecture/spec-inconsistencies.md) | Known inconsistencies between specifications, recorded for future resolution |

## What does NOT belong here

- Product requirements that belong in the root specifications
- Secrets, credentials or real customer data
- Generated API documentation (produced by the build, not committed)
