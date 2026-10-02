# Security Foundation

- **Status:** Approved design (T00-01), refined by ADR-0010 … ADR-0012 (T01-00). Implemented in T01-01: realm guards (deny by default), the error envelope without internals (§8), `extra="forbid"` request schemas and bounded pagination (§8), and redacted structured logging (§13); see [backend-foundation.md](backend-foundation.md). The audit foundation followed in T01-02 (§11) and the tenancy core in T01-03 (§1a, [ADR-0014](../adr/0014-tenancy-core.md)). Authentication, CSRF, RBAC and rate limiting follow in T01-04 … T01-06.
- **Decisions:** [ADR-0004](../adr/0004-tenant-isolation.md), [ADR-0005](../adr/0005-identity-and-session-realms.md), [ADR-0006](../adr/0006-api-prefixes.md)
- **Related:** CLAUDE.md §5–§11, §42–§51, §65, §94; ARCHITECTURE.md §48–§52; PLATFORM-ADMIN.md §15–§16, §65–§67, §93

## 1. Realm boundaries

| Capability | PLATFORM (`/platform`, `/api/v1/platform`) | TENANT (`/app`, `/api/v1`) | STUDENT (`/student`, `/api/v1/student`) | PUBLIC SITE (`/sites`, `/api/v1/public`) |
|---|---|---|---|---|
| Tenants and lifecycle | create, suspend, reactivate, deactivate, provision | — | — | tenant resolution by domain (internal) |
| Plans, subscriptions, entitlements, overrides | **own and manage** | read own plan and usage (ADMIN-11) | — | — |
| SaaS billing (MTI 360 → institute) | **own** | read own invoices, pay | — | — |
| Student fees (institute → student) | — | **own** (`finance`) | view and pay own fees | — |
| AI providers, models, keys, global guardrails, cost | **own** | — (never sees credentials) | — | — |
| Tenant AI configuration | view via support session | **own** (ADMIN-09) | uses assigned assistants | public enquiry agent (later) |
| Communication providers | platform provider accounts | tenant channels and templates (ADMIN-08) | receives messages | — |
| Support | tickets, **support sessions** | raise tickets; sees banner and support audit | — | — |
| Audit | platform audit; cross-tenant only via audited access | own tenant audit (ADMIN-12) | — | — |
| Feature flags | **own** | effect only | effect only | effect only |
| Tenant configuration (profile, branding, campuses, roles, settings) | view via support session; set at provisioning | **own** | — | published branding and content only |
| Identity | `platform_users`, separate login, mandatory MFA | `users` + membership + roles | `users` + student account link | anonymous |

A platform principal never holds a tenant role; a tenant principal can never hold a `platform.*` permission. Entitlements are enforced server-side in the authorization dependency.

## 1a. Tenant isolation (T01-03)

- **Implemented:** layers 2–5 of [tenancy.md §4](tenancy.md#4-enforcement-layers) ([ADR-0014](../adr/0014-tenancy-core.md)). The authorization layer follows in T01-05.
- **Trusted tenant.** The tenant comes only from the server-side `RequestContext`, published by `context_transaction` with `SET LOCAL` and recorded in `session.info`. It never comes from a request body, query, header or frontend state.
- **Defence in depth.** Three independent layers each prevent cross-tenant access, and the tests prove each one alone:
  - the tenant-scoped repository (`id AND tenant_id`; another tenant's row is a 404);
  - the ORM filter, which fails closed without a tenant;
  - Row-Level Security.
- **Row-Level Security.** Tenant-owned tables use `tenant_id = app.tenant_id` for reads and writes in every realm. `tenants` is readable in full only by the platform and system realms, which are also the only realms that write it.
- **No hard delete.** The runtime roles have no DELETE privilege on `tenants` or `campuses`. Foreign keys use `ON DELETE RESTRICT`, and composite foreign keys reject cross-tenant links.
- **System realm.** `system_context` is the only way to act as the system realm. It is refused inside an HTTP request.
- **Roles.** No database role changed. `mti_app` and `mti_readonly` stay NOBYPASSRLS and own nothing.

## 2. Authentication

- Opaque server-side sessions; `__Host-` prefixed `HttpOnly` `Secure` `SameSite=Lax` cookies; **distinct cookie per realm**.
- Session identifier rotation on login, privilege change and MFA completion.
- Idle and absolute timeouts; shorter for the platform realm.
- Generic responses that never reveal whether an account exists.
- Progressive back-off and rate limiting on authentication endpoints.

## 3. Passwords

- **Argon2id** hashing.
- Minimum length and breached-password checks.
- Password-reset tokens: single-use, short-lived, **stored hashed**.
- Passwords, tokens and secrets are never logged.

## 4. MFA readiness

- Identity model supports TOTP, hashed recovery codes and trusted devices from Phase 01.
- **Mandatory for platform roles**; tenant policy may require it for tenant users.
- **Step-up authentication** for high-risk actions (delete / restore tenant data, subscription changes, credential rotation, AI provider changes, security policy changes — PLATFORM-ADMIN.md §16).

## 5. Authorization and RBAC

- Central **permission registry** in code (`resource.action`, e.g. `lead.read`, `application.approve`), seeded to the database.
- Tenant roles: per-tenant rows cloned from system templates (customizable). Platform roles: fixed set (PRD.md §85).
- Single `authorize(context, permission, resource?)` covering realm, tenant status, feature entitlement, permission, campus scope and resource ownership.
- Applied as FastAPI dependencies on every router/handler.
- `PermissionGate` in the UI is **cosmetic only**; the API independently rejects unauthorized requests.

## 6. CSRF and browser security

- SameSite cookies plus a CSRF token or required custom header on unsafe methods.
- Headers: HSTS, nonce-based CSP, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `Permissions-Policy`, `frame-ancestors` — from the Next.js proxy (`src/proxy.ts`, formerly "middleware") and the API.
- CORS allow-list only; never `*` with credentials.

## 7. Rate limiting

Redis-backed, keyed per IP, account, tenant and endpoint class. Applies to login, OTP, password reset, public forms, AI endpoints, webhooks, uploads and bulk sends (ARCHITECTURE.md §52). Tenant-level limits are configurable.

## 8. API validation and errors

- Pydantic schemas with `extra="forbid"`, bounded lengths and capped pagination.
- Business transitions only via explicit endpoints; no arbitrary status updates.
- Single error envelope (ARCHITECTURE.md §36); no stack traces, SQL, infrastructure details or provider credentials in responses.

## 9. Secrets and configuration

- Settings loaded with pydantic-settings and validated per `APP_ENV` at startup (implemented in T00-04; matrix in [environments.md](environments.md)). Staging and production refuse placeholder or weak secrets, debug mode, wildcard or non-https CORS origins, the fake AI provider, implicit infrastructure settings and database URLs without TLS or with shared/superuser roles; production also refuses `LOG_LEVEL=DEBUG`.
- Staging and production read the process environment only; `.env` files are read only in development. Secrets are `SecretStr`; configuration errors name variables, never values.
- The frontend environment module is `server-only`; `NEXT_PUBLIC_APP_NAME` is its only browser-public value.
- Only `*.example` environment files are committed; real `.env` files are git-ignored.
- **No secret may ever appear in a `NEXT_PUBLIC_*` variable** or anywhere in frontend code.
- Staging and production secrets are injected by the platform secret manager / CI.
- **Must never be committed:** real `.env` files; API keys and provider tokens (WhatsApp, email, SMS, voice, payment, LLM); database passwords; session, CSRF and encryption keys; private keys and certificates; cloud credentials; database dumps or backups; uploaded files.
- `pnpm check:env` (T00-04) blocks tracked `.env` files, non-placeholder values in templates and secret-like `NEXT_PUBLIC_*` names.
- **Secret scanning (T00-05):** CI runs gitleaks over the full history of every ref with the default rules and `--redact`. The allowlist in `.gitleaks.toml` covers only one documented fake test value in two exact files (exact path AND exact value), and a self-test proves detection on every run. CI itself needs no secrets. See [ci.md §3](ci.md#3-security-model).

## 10. File access

- Upload validation: extension, sniffed MIME type, size, sanitized filename, content checks and a malware-scan hook (ARCHITECTURE.md §49).
- Private bucket; tenant-prefixed UUID keys; authorization before issuing short-lived presigned URLs.

## 11. Audit logging

- **Implemented in T01-02** ([ADR-0013](../adr/0013-audit-events.md), [backend-foundation.md §12](backend-foundation.md#12-audit-foundation-t01-02)).
- `app/core/audit` writers are called from services for authentication events, authorization changes, support sessions, tenant/subscription changes, financial and compliance changes, AI actions and data access. In T01-02 they have no producers yet.
  - `write_audit_event` writes in the request transaction.
  - `record_security_event` buffers the event and flushes it in a fresh transaction after the request transaction has released its connection, so security events survive rollbacks.
- One table, `audit_events`, captures the realm, tenant (nullable, no foreign key), principal, category, event type, target (type and ID), `request_id`, timestamp and redacted metadata.
  - `support_session_id`, campus, IP and result are deferred to the tasks that introduce trusted sources for them (INC-35).
  - The request log's `request_id` is the correlation ID.
- Append-only in the database:
  - `mti_app` has SELECT and INSERT only, and `mti_readonly` has no access;
  - triggers reject UPDATE, DELETE and TRUNCATE for every role.
- Row-Level Security:
  - the platform realm reads all rows;
  - the tenant realm reads only its own tenant's rows;
  - inserts must match the trusted tenant and realm context.

## 12. AI tool authorization

- Tools are explicitly registered with input/output schemas, required permission, tenant scope, risk level and audit flag (ARCHITECTURE.md §19).
- A tool executes with the **caller's** context and permissions — never elevated.
- High-risk tools create an **approval request** instead of executing (CLAUDE.md §44).
- Retrieved documents and user messages are untrusted input and cannot change tool permissions (ARCHITECTURE.md §51).
- No direct database access for agents; the SQL/Data Agent uses a read-only, RLS-bound role.
- AI executions are recorded without raw prompts or sensitive payloads by default (ARCHITECTURE.md §45).

## 13. Logging

Structured logs with correlation IDs and redaction. Never log passwords, tokens, API keys, secret credentials, full sensitive documents or unnecessary personal information (CLAUDE.md §67).
