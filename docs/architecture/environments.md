# Environments and configuration (T00-04)

**Status:** Implemented in T00-04. Backend: [`backend/app/core/config.py`](../../backend/app/core/config.py). Frontend: [`frontend/src/lib/env.ts`](../../frontend/src/lib/env.ts). Repository check: [`scripts/check-env.mjs`](../../scripts/check-env.mjs) (`pnpm check:env`).

MTI 360 has four environments, selected by `APP_ENV`:

| `APP_ENV` | Purpose | Where it runs |
|---|---|---|
| `development` | Local development | Developer machines (`pnpm dev`, `pnpm stack:up`) |
| `test` | Automated tests | Developer machines and CI |
| `staging` | Pre-production verification | Shared infrastructure (Phase 17) |
| `production` | Live service | Shared infrastructure (Phase 17) |

Settings are validated when the process starts. An invalid configuration stops startup with a `ConfigurationError` (backend) or an `EnvironmentError` (frontend). The error lists **variable names and broken rules only, never values**.

## 1. Where values come from

| Source | development | test | staging | production |
|---|---|---|---|---|
| Built-in local defaults (T00-03 infrastructure) | yes | yes, except session/CSRF secrets | **no** for infrastructure settings (must be explicit) | **no** for infrastructure settings (must be explicit) |
| `backend/.env` | yes (optional) | **never** | **never** | **never** |
| Process environment | yes (overrides `.env`) | yes | **only source** (secret manager / CI) | **only source** (secret manager / CI) |
| Explicit constructor values | — | yes (test fixtures) | — | — |

- **Development needs no configuration.** With no `backend/.env` and no variables set, the backend starts with local defaults that match the T00-03 infrastructure. A `backend/.env` (copied from `backend/.env.example`) overrides them.
- **`APP_ENV` never comes from `backend/.env`.** It is resolved from the process environment (default `development`) before any file is read, so a stray `.env` file can neither switch a server into development nor weaken a deployed configuration. If `backend/.env` contains `APP_ENV` other than `development`, startup fails.
- **Tests** construct settings from explicit values ([`backend/tests/conftest.py`](../../backend/tests/conftest.py)) and remove every settings variable from the process environment first, so local configuration cannot change results.
- The root `.env` configures Docker Compose for local development only. It is not an application settings file.

## 2. Backend rules

| Rule | development | test | staging | production |
|---|---|---|---|---|
| Reads `backend/.env` | yes | no | no | no |
| `APP_DEBUG=true` allowed | yes | no | no | no |
| `LOG_LEVEL=DEBUG` allowed | yes | yes | yes | **no** |
| `AI_PROVIDER=fake` allowed | yes | yes | no | no |
| `SESSION_SECRET`, `CSRF_SECRET`: non-placeholder, ≥ 32 characters, different from each other | not enforced | enforced | enforced | enforced |
| Other secrets (`S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `SMTP_PASSWORD`, `AI_PROVIDER_API_KEY`) must be non-empty and not a placeholder | no | no | yes | yes |
| Infrastructure settings must be set explicitly (no local defaults) | no | no | yes | yes |
| Database URLs: `postgresql+asyncpg`, with user, host and database | yes | yes | yes | yes |
| Database URLs: three **different** users (runtime, migrations, read-only) | yes | yes | yes | yes |
| Database URLs: non-placeholder password, no bootstrap superuser (`postgres`, `mti360_superuser`), TLS `ssl=require` / `verify-ca` / `verify-full` | no | no | yes | yes |
| `CORS_ALLOWED_ORIGINS` contains `*` | rejected | rejected | rejected | rejected |
| `CORS_ALLOWED_ORIGINS` must be `https://` | no | no | yes | yes |
| `S3_ENDPOINT_URL` must be empty (provider default) or `https://` | no | no | yes | yes |
| `APP_BASE_URL` must be an origin (no path); `https://` | origin: yes; https: no | origin: yes; https: no | yes | yes |
| Session idle timeout ≤ absolute timeout (tenant and platform realms) | yes | yes | yes | yes |
| OpenAPI `/docs` and `/openapi.json` exposed | yes | no | no | no |

Placeholders are empty values and template values such as `change-me` (case-insensitive). Staging is exactly as strict as production except that `LOG_LEVEL=DEBUG` is allowed (decision D3).

**Settings that must be explicit in staging/production:** `DATABASE_URL`, `MIGRATIONS_DATABASE_URL`, `READONLY_DATABASE_URL`, `REDIS_URL`, `S3_ENDPOINT_URL` (may be explicitly empty), `S3_REGION`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `SESSION_SECRET`, `CSRF_SECRET`, `CORS_ALLOWED_ORIGINS`, `APP_BASE_URL`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `EMAIL_FROM_ADDRESS`, `AI_PROVIDER`, `AI_PROVIDER_API_KEY`. `APP_DEBUG` and `LOG_LEVEL` have secure defaults (`false`, `INFO`). The session timeouts, `S3_PRESIGNED_URL_TTL_SECONDS`, `TRUSTED_PROXY_HOPS` (0), `ARGON2_TIME_COST` / `ARGON2_MEMORY_COST_KIB` / `ARGON2_PARALLELISM` (argon2-cffi defaults) and `SMTP_TIMEOUT_SECONDS` (10) have safe defaults (T01-04).

### Database connection settings

T00-04 validates connection settings only. There is **no engine, connection, schema or migration yet**.

| Variable | T00-03 role | Purpose |
|---|---|---|
| `DATABASE_URL` | `mti_app` | Application runtime (DML only, subject to RLS) |
| `MIGRATIONS_DATABASE_URL` | `mti_owner` | Migrations only; never used by the running application |
| `READONLY_DATABASE_URL` | `mti_readonly` | Reporting and the governed SQL/Data Agent (SELECT only) |

Requiring three different users means the application can never run as the schema owner.

### Validated but not yet used

Redis, S3, SMTP, session/CSRF, CORS and AI settings are typed and validated, but their clients and middleware arrive with later tasks (the first task that uses each one). T00-04 adds no Redis, S3 or SMTP client, no session or CSRF code and no CORS middleware. Since T01-04, Redis (authentication rate limits), SMTP (password-reset email), the session and CSRF secrets and `CORS_ALLOWED_ORIGINS` (allow-list of the same-origin check) are used; S3 and AI are not yet.

## 3. Frontend rules

`frontend/src/lib/env.ts` starts with `import "server-only"`: importing it from a Client Component fails `next build`.

| Variable | Class | Rule |
|---|---|---|
| `APP_ENV` | server-only | One of the four environments; default `development` |
| `API_BASE_URL` | server-only | `http(s)` URL without credentials, query or fragment. Default `http://localhost:8000` in development and test; **required in staging/production** |
| `NEXT_PUBLIC_APP_NAME` | **browser-public** | Display name (default `MTI 360`). The only public value |

The frontend holds no secrets. Any `NEXT_PUBLIC_*` value is embedded in JavaScript shipped to every browser.

## 4. Secret handling

- Backend secrets are `SecretStr`: masked in `repr`, `str`, JSON dumps and logs. Validation errors hide their input (`hide_input_in_errors`). Tests assert that no secret value appears in any error or log output.
- Only `*.env.example` templates are committed. They hold placeholders only (`change-me` or empty).
- `pnpm check:env` (part of `pnpm check`) fails when:
  - a real environment file (`.env`, `.env.local`, `*.env`, `.envrc` …) is tracked;
  - a template holds a non-placeholder value in a secret-like variable (`*SECRET*`, `*PASSWORD*`, `*TOKEN*`, `*_KEY`) or in URL credentials;
  - a `NEXT_PUBLIC_*` name is secret-like (in templates or frontend source);
  - `backend/.env.example` and the `Settings` fields drift apart (also covered by `backend/tests/unit/test_env_template.py`).
- Staging and production secrets come from the secret manager as process environment variables; `.env` files are never read there (decision D4). Secret-manager integration and staging/production infrastructure are Phase 17. Full secret scanning (gitleaks) is T00-05.

## 5. Adding a variable

1. Add a typed field to `Settings` (use `SecretStr` for anything secret) with a local development default.
2. Add it to `backend/.env.example` with a comment; mark it `[staging/production]` if it must be explicit there, and add it to the explicit/secret lists in `config.py`.
3. Add a passing and a failing test for any new rule in `backend/tests/unit/test_settings_environments.py`.
4. Update this document. `pnpm check:env` and the template test fail until the template and `Settings` match.

## 6. Decisions (T00-04)

| # | Decision |
|---|---|
| D1 | Database connections require TLS (`ssl=require` or stricter) in staging and production. Revisit when hosting is chosen. |
| D2 | The frontend uses the official `server-only` marker package so server configuration cannot reach the browser bundle. |
| D3 | Staging is as strict as production, except `LOG_LEVEL=DEBUG` is allowed. |
| D4 | Staging and production never read `.env` files; the process environment (secret manager) is the only source. |
| D5 | Repository hygiene is a dependency-free Node script in `pnpm check`; gitleaks follows in CI (T00-05). |
