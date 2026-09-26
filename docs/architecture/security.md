# Security Foundation

- **Status:** Approved design (T00-01). Nothing in this document is implemented yet.
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
- Headers: HSTS, nonce-based CSP, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `Permissions-Policy`, `frame-ancestors` — from Next.js middleware and the API.
- CORS allow-list only; never `*` with credentials.

## 7. Rate limiting

Redis-backed, keyed per IP, account, tenant and endpoint class. Applies to login, OTP, password reset, public forms, AI endpoints, webhooks, uploads and bulk sends (ARCHITECTURE.md §52). Tenant-level limits are configurable.

## 8. API validation and errors

- Pydantic schemas with `extra="forbid"`, bounded lengths and capped pagination.
- Business transitions only via explicit endpoints; no arbitrary status updates.
- Single error envelope (ARCHITECTURE.md §36); no stack traces, SQL, infrastructure details or provider credentials in responses.

## 9. Secrets and configuration

- Settings loaded with pydantic-settings and validated per `APP_ENV` (T00-04). Production refuses placeholder secrets, debug mode, permissive CORS and the fake AI provider.
- Only `*.example` environment files are committed; real `.env` files are git-ignored.
- **No secret may ever appear in a `NEXT_PUBLIC_*` variable** or anywhere in frontend code.
- Staging and production secrets are injected by the platform secret manager / CI.
- **Must never be committed:** real `.env` files; API keys and provider tokens (WhatsApp, email, SMS, voice, payment, LLM); database passwords; session, CSRF and encryption keys; private keys and certificates; cloud credentials; database dumps or backups; uploaded files.
- Secret scanning is added to CI in T00-05.

## 10. File access

- Upload validation: extension, sniffed MIME type, size, sanitized filename, content checks and a malware-scan hook (ARCHITECTURE.md §49).
- Private bucket; tenant-prefixed UUID keys; authorization before issuing short-lived presigned URLs.

## 11. Audit logging

- `core/audit` writer called from services for authentication events, authorization changes, support sessions, tenant/subscription changes, financial and compliance changes, AI actions and data access.
- Captures actor, realm, tenant, action, resource, result, timestamp, `support_session_id`, `correlation_id` and redacted metadata.
- Append-only at the database-grant level.

## 12. AI tool authorization

- Tools are explicitly registered with input/output schemas, required permission, tenant scope, risk level and audit flag (ARCHITECTURE.md §19).
- A tool executes with the **caller's** context and permissions — never elevated.
- High-risk tools create an **approval request** instead of executing (CLAUDE.md §44).
- Retrieved documents and user messages are untrusted input and cannot change tool permissions (ARCHITECTURE.md §51).
- No direct database access for agents; the SQL/Data Agent uses a read-only, RLS-bound role.
- AI executions are recorded without raw prompts or sensitive payloads by default (ARCHITECTURE.md §45).

## 13. Logging

Structured logs with correlation IDs and redaction. Never log passwords, tokens, API keys, secret credentials, full sensitive documents or unnecessary personal information (CLAUDE.md §67).
