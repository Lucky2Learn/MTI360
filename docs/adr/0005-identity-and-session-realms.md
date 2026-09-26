# ADR-0005 — Identity and Session Realms

- **Status:** Accepted (implementation in Phase 01: T01-01 … T01-04, T01-07)
- **Date:** 2026-09-26
- **Task:** T00-01
- **Related:** CLAUDE.md §7–§9, §11; ARCHITECTURE.md §10; PLATFORM-ADMIN.md §15–§16, §65–§67, §88; [security.md](../architecture/security.md)

## Context

- ARCHITECTURE.md §10 left the session mechanism open ("Session / JWT").
- ARCHITECTURE.md §32 lists `users` and `tenant_users` but does not say whether platform administrators share the `users` table.
- PLATFORM-ADMIN.md §15 requires a separate platform authentication experience (`/platform/login`) and §16 mandatory MFA for privileged platform roles.
- CLAUDE.md §7 requires that a tenant administrator can never gain platform access, and §8 that support access is explicit, visible and audited.

## Decision

**Four realms**, each with its own route tree, API prefix (ADR-0006) and session cookie:

| Realm | Principal | Identity store |
|---|---|---|
| `platform` | MTI 360 platform administrator | **`platform_users`** — separate from tenant identity |
| `tenant` | Institute staff | `users` + tenant membership + tenant roles (+ campus scope) |
| `student` | Student | `users` + student account linked to a student record |
| `public` | Anonymous visitor | none |

1. **Separate platform identity.** Platform administrators are stored in `platform_users` with platform roles only. A tenant principal can never hold a `platform.*` permission and a platform principal never holds a tenant role; the permission registry rejects such assignments.
2. **Opaque server-side sessions** (stored server-side, revocable) instead of browser-held JWTs. Cookies are `__Host-` prefixed, `HttpOnly`, `Secure`, `SameSite=Lax`, with **distinct cookie names per realm**. Session identifiers rotate on login, privilege change and MFA. Idle and absolute timeouts apply; platform sessions are shorter.
3. **Active tenant and campus are held in the server-side session**, not in tenant-application URLs. Switching tenant or campus is an explicit, server-validated API call.
4. **CSRF protection** via SameSite cookies plus a CSRF token / required header on unsafe methods.
5. **MFA readiness:** the identity model supports TOTP, hashed recovery codes and trusted devices from Phase 01. MFA is mandatory for platform roles; tenants may require it; high-risk actions require step-up authentication.
6. **Support sessions:** a platform principal with the support permission starts a session bound to one tenant, with reason, mode (read-only or limited write) and expiry. Effective permissions are the intersection of the mode allow-list and the operator's platform role. Every request carries and audits the `support_session_id`; the UI banner is driven by server state; sessions end on exit, expiry or revocation. There is no silent impersonation.

## Consequences

- A compromised or misconfigured tenant role cannot escalate to platform access by design.
- Server-side sessions add a session store lookup per request (Redis/Postgres) but allow immediate revocation, context switching and support-session tracking.
- A person who is both a platform administrator and a tenant user has two separate identities and logins. This is intentional.
- Students and staff share the `users` identity table but are distinguished by realm and membership type.

## Alternatives considered

- **Shared `users` table with platform roles** — simpler, but one role-assignment bug could grant platform access. Rejected.
- **Stateless JWTs stored in the browser** — no server lookup, but hard to revoke, larger XSS exposure if stored in JavaScript-readable storage, and awkward for support-session and tenant switching. Rejected.
- **Tenant slug in every tenant-application URL** — convenient for multi-tenant users with several tabs, but invites treating a URL value as tenant authority. Rejected for v1.
