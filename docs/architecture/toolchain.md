# Development Toolchain

- **Status:** Implemented in T00-02 (2026-09-26)
- **Decision basis:** [ADR-0001](../adr/0001-stack.md) ("exact runtime versions are pinned in T00-02"); T00-02 proposal decisions D1–D8
- **Related:** [repository-structure.md](repository-structure.md), [security.md](security.md)

This document records the exact toolchain versions, why each was chosen, which newer versions are deliberately held back, and how versions are pinned and updated. Version choices within ADR-0001 do not need a new ADR; replacing a technology does.

## 1. Runtimes and package managers

| Tool | Pinned | Where pinned | Notes |
|---|---|---|---|
| Node.js | **24.21.0** (Active LTS "Krypton") | `.nvmrc` (exact, CI/Docker); `engines` `>=24.15.0 <25` (root and frontend) | Node 26 becomes LTS on 2026-10-28; move in a later task. `engineStrict` is on. |
| pnpm | **11.28.0** | `packageManager` in root `package.json` | Activated with Corepack (bundled with Node 24). Corepack is not bundled from Node 25, so the Node 26 move must install pnpm another way. |
| Python | **3.14** (resolved 3.14.7, uv-managed) | `backend/.python-version`; `requires-python = ">=3.14,<3.15"` | The system Python is never used or modified. |
| uv | **0.12.19** | `[tool.uv] required-version = ">=0.12.19,<0.13"` | Installed per-user with the official installer. |

## 2. Locked versions (at T00-02)

### Frontend (`frontend/package.json`, exact pins; `pnpm-lock.yaml`)

| Package | Version | Package | Version |
|---|---|---|---|
| next | 16.3.5 | eslint | 9.39.5 |
| react / react-dom | 19.2.8 | eslint-config-next | 16.3.5 |
| typescript | 6.0.3 | typescript-eslint | 8.70.0 |
| @types/node | 24.13.6 | eslint-plugin-jsx-a11y | 6.10.2 |
| @types/react / -dom | 19.2.18 / 19.2.7 | prettier | 3.9.8 |
| vitest | 4.1.11 | vite | 8.3.0 |
| @vitejs/plugin-react | 6.1.1 | jsdom | 30.1.0 |
| @testing-library/react | 16.3.3 | @testing-library/dom | 10.4.2 |
| @testing-library/jest-dom | 7.0.1 | server-only (T00-04) | 0.0.1 |
| tailwindcss (T00-06) | 4.3.3 | @tailwindcss/postcss (T00-06) | 4.3.3 |
| @fontsource-variable/inter (T00-06) | 5.3.0 | react-aria-components (T00-07) | 1.21.1 |
| @internationalized/date (T00-07) | 3.12.4 | lucide-react (T00-07) | 1.47.0 |
| @testing-library/user-event (T00-07) | 14.6.7 | axe-core (T00-07) | 4.13.0 |

### Backend (`backend/pyproject.toml` ranges; exact in `uv.lock`, 36 packages)

| Package | Locked | Package | Locked |
|---|---|---|---|
| fastapi | 0.141.1 | starlette (via FastAPI) | 1.6.0 |
| uvicorn[standard] | 0.53.0 | anyio (via Starlette) | 4.15.1 |
| pydantic | 2.13.5 | pydantic-settings | 2.15.0 |
| pytest (dev) | 9.1.1 | httpx (dev) | 0.28.1 |
| ruff (dev) | 0.16.8 | mypy (dev) | 2.3.1 |

`uvicorn[standard]` adds httptools, watchfiles and — on Linux only — uvloop.

**Not installed yet (decision D5):** SQLAlchemy (target 2.0.x), Alembic, asyncpg, Redis client, S3 client. They are added by the task that first uses them.

### Docker images (T00-03)

| Service | Image | Notes |
|---|---|---|
| PostgreSQL | `pgvector/pgvector:0.8.6-pg18-trixie` (PostgreSQL 18.6) | PG 18: stable, supported to 2030, native `uuidv7()`. pgvector image avoids an image swap later; extension **not enabled**. |
| Redis | `redis:8.8-alpine` (8.8.3) | Matches the architecture ("Redis"); local use only. |
| Object storage | `chrislusf/seaweedfs:4.47` | Apache-2.0 S3-compatible emulator. MinIO's community repository was archived (2026) and its Docker Hub image is no longer available; RustFS 1.0 was too new; Garage is AGPL with extra setup. |
| Mail | `axllent/mailpit:v1.31` (1.31.2) | |
| Backend base | `python:3.14.7-slim-trixie` + `ghcr.io/astral-sh/uv:0.12.19` | Image `mti360-api:local` (~234 MB) |
| Frontend base | `node:24.21.0-trixie-slim` (Corepack → pnpm 11.28.0) | Image `mti360-frontend:local` (~387 MB), Next.js standalone output |

Verified with Docker Engine 29.8.0 and Docker Compose v5.5.1 (Docker Desktop, WSL 2). Images are pinned to patch-level tags; digest pinning remains out of scope (considered and deferred in T00-05). Dependabot proposes base-image updates monthly ([ci.md §6](ci.md#6-dependabot-decision-d7)).

**Deferred (T00-03 decision D4):** the Alembic `migrate` service and the background `worker` (with its queue library) are added by the first task that needs them. This moves the queue-library choice that ADR-0001 placed in T00-03.

## 3. Deliberate version holds

| Held at | Newer available | Reason | Lift when |
|---|---|---|---|
| TypeScript 6.0.3 | 7.0.x | `typescript-eslint` 8.x declares `typescript <6.1.0` (hard constraint). | typescript-eslint supports TS 7. |
| ESLint 9.39.5 | 10.x | `eslint-plugin-react`, `eslint-plugin-import`, `eslint-plugin-jsx-a11y` (used by `eslint-config-next`) declare ESLint ≤ 9 (hard constraint). **Note:** npm marks ESLint 9 as no longer supported. Dev-only tool; no runtime exposure. | The three plugins support ESLint 10. |
| pnpm 11.28.0 | 12.x | pnpm 12.0.0 was ~4 weeks old at T00-02. | A planned upgrade task. |
| Vitest 4.1.11 | 5.x | Vitest 5.0.0 was ~3 weeks old. | A planned upgrade task. |
| React 19.2.8 | 19.3.x | 19.3.0 was ~2.5 weeks old; the App Router renders with Next.js's vendored React. | A planned upgrade task. |
| SQLAlchemy 2.0.x (target) | 2.1.x | 2.1.0 was released 2 days before T00-02. | Re-evaluate when database work starts. |

## 4. Supply-chain controls

| Control | Setting |
|---|---|
| 7-day release cooldown (npm) | `minimumReleaseAge: 10080` (minutes) in `pnpm-workspace.yaml`; strict by default when set explicitly. |
| 7-day release cooldown (PyPI) | `exclude-newer = "7 days"` in `[tool.uv]` (recorded in `uv.lock` as `exclude-newer-span = "P7D"`). |
| Dependency install scripts | Blocked by default. `strictDepBuilds: true` fails the install on any unreviewed script. Reviewed entries live in `allowBuilds` with a justification (currently: `unrs-resolver: false`). |
| Exact frontend pins | `saveExact: true`; exact versions in `package.json`. |
| Frozen installs | `pnpm install --frozen-lockfile`, `uv sync --locked`, and `uv run --locked` in every script. |
| Pinned package managers | `packageManager` (pnpm), `required-version` (uv). |

Because of the cooldown, T00-02 resolved to the newest version that was at least 7 days old (for example next 16.3.5 instead of 16.3.6, uvicorn 0.53.0 instead of 0.54.0). The pnpm version itself (11.28.0) was approved explicitly and is not subject to the dependency cooldown.

## 5. Commands

Run from the repository root.

| Command | Purpose | Scope |
|---|---|---|
| `pnpm bootstrap` | `pnpm install --frozen-lockfile` + `uv sync --locked` | both |
| `pnpm dev` | Frontend and backend in parallel | both |
| `pnpm dev:frontend` / `pnpm dev:backend` | One side only | one |
| `pnpm build` | `next build` | frontend |
| `pnpm lint` | ESLint (`--max-warnings=0`) + `ruff check` | both |
| `pnpm typecheck` | `next typegen && tsc --noEmit` + `mypy` (strict) | both |
| `pnpm test` | `vitest run` + `pytest` | both |
| `pnpm format` / `pnpm format:check` | Prettier (frontend/ only) + `ruff format` (backend/ only); `format:check:frontend` / `format:check:backend` run one side (T00-05) | both |
| `pnpm check:lock` | `uv lock --check`: `uv.lock` matches `pyproject.toml` (T00-05) | backend |
| `pnpm check:landing` | Fails if `index.html`, `app.js` or `styles.css` differ from tag `marketing-site-v1` | repo |
| `pnpm check:env` | Environment template and secret hygiene (T00-04, [environments.md](environments.md)) | repo |
| `pnpm check` | `check:landing` → `check:env` → `check:lock` → `format:check` → `lint` → `typecheck` → `test` → `build` | repo |
| `pnpm infra:up` / `infra:down` / `infra:reset` / `infra:logs` | Local Docker infrastructure (T00-03) — see [local-development.md](../runbooks/local-development.md) | Docker |
| `pnpm stack:up` | Build and run infrastructure + api + frontend images (T00-03) | Docker |

**Ports:** `FRONTEND_PORT` (default 3000) and `API_PORT` (default 8000) are read from the shell environment, e.g. `FRONTEND_PORT=3100 API_PORT=8100 pnpm dev`. pnpm's `shellEmulator` makes this syntax work identically on Windows, macOS, Linux and CI. Dev servers bind to `localhost` / `127.0.0.1` only.

The backend has no build step: it is not packaged, and import correctness is covered by `mypy` and the tests.

## 6. Tool scopes (marketing-site protection)

- ESLint and Prettier run **only inside `frontend/`**; Ruff runs **only inside `backend/`**. No formatter or linter is configured at the repository root, so the root marketing website and the specification documents are never linted or reformatted.
- `pnpm check:landing` is part of `pnpm check`. It compares git content, so it is unaffected by local line-ending conversion; it requires the `marketing-site-v1` tag to be present (CI must fetch tags).

## 7. Environment variables

| Class | Examples | Where |
|---|---|---|
| Browser-public | `NEXT_PUBLIC_APP_NAME` | `frontend/.env.local` — **never a secret** |
| Server-only, non-secret | `APP_ENV`, `APP_DEBUG`, `LOG_LEVEL`, `API_BASE_URL`, `FRONTEND_PORT`, `API_PORT` | `backend/.env`, `frontend/.env.local`, shell |
| Secrets | session/CSRF secrets, database passwords, provider keys | local ignored files only; secret manager in staging/production |

Since T00-04 the backend types and validates every variable in `backend/.env.example`, and the frontend validates `APP_ENV` and `API_BASE_URL` in the server-only `src/lib/env.ts`. `backend/.env` is read only in development; tests never read it. Rules per environment: [environments.md](environments.md). `NEXT_TELEMETRY_DISABLED=1` is recommended for CI and Docker.

## 8. Update policy

- **Security patches:** immediately.
- **Routine updates:** monthly batch, respecting the cooldown.
- **Major versions and lifting a hold (§3):** a dedicated task each; an ADR only if the change affects architecture.
- **Automated update PRs (T00-05, decision D7):** Dependabot for GitHub Actions, Dockerfile base images and `compose.yaml` images only — monthly, grouped, 7-day cooldown, no majors. npm (pnpm 11) and uv are **not** enabled because compatibility could not be established; frontend and backend dependencies stay on the manual monthly batch above. See [ci.md §6](ci.md#6-dependabot-decision-d7).
- **CI (T00-05):** every PR and push to `main` runs the commands in §5 on `ubuntu-24.04`; the single required status is `ci-ok`. See [ci.md](ci.md).

## 9. Local setup notes

- **Windows without administrator rights:** `corepack enable` fails when Node is installed under `C:\Program Files`. Use `corepack enable --install-directory "%APPDATA%\npm" pnpm`.
- **uv:** install with the official installer (`https://astral.sh/uv/<version>/install.ps1` or `install.sh`); run `uv python install 3.14` or let `uv sync` fetch it.
- **Port conflicts:** if 3000/8000 are taken (for example by another project's Docker containers), set `FRONTEND_PORT` / `API_PORT`.
- **AI coding agents:** when `next dev` detects an AI agent, it writes `frontend/AGENTS.md` and `frontend/CLAUDE.md` (a Next.js documentation pointer). These are not committed; whether to commit or ignore them is an open decision.
