# scripts/

**Status:** `check-env.mjs` (T00-04); CI helpers in `ci/` (T00-05).

| Script | Command | Purpose |
|---|---|---|
| `check-env.mjs` | `pnpm check:env` (part of `pnpm check`) | Environment template and secret hygiene: no tracked real `.env` files, placeholders only in secret-like template variables and URL credentials, no secret-like `NEXT_PUBLIC_*` names, and `backend/.env.example` ↔ `Settings` consistency. Node built-ins only; prints names, never values. |
| `ci/install-tool.sh` | `bash scripts/ci/install-tool.sh <gitleaks\|actionlint> <dir>` | Installs a pinned CI tool after verifying the SHA-256 recorded in the script; a mismatch aborts before extraction (linux-x64, windows-x64, darwin-arm64). |
| `ci/gitleaks-selftest.sh` | `bash scripts/ci/gitleaks-selftest.sh` | Proves gitleaks detects runtime-generated secrets and that the `.gitleaks.toml` allowlist is value- and path-specific; fixtures live under `mktemp` and are never committed. |
| `ci/docker-smoke.sh` | `bash scripts/ci/docker-smoke.sh mti360-api:ci` | API image smoke test (`/health` 200, HEALTHCHECK healthy) and production fail-fast check; touches only `mti360-ci-*` containers. |

CI usage and local reproduction: [docs/architecture/ci.md](../docs/architecture/ci.md).

## Purpose

Thin developer helper scripts that wrap documented commands (for example: start local infrastructure, run migrations, reset the local database, run all checks).

Scripts are provided as POSIX shell (`.sh`) and, where Windows developers need them, PowerShell (`.ps1`). Cross-platform checks may be dependency-free Node.js (`.mjs`, built-ins only). Each script must also be reproducible by running its documented underlying commands directly.

## Ownership

Shared by all engineering.

## What belongs here

- Small, idempotent, documented helpers for local development and CI
- Scripts that read configuration from environment variables

## What does NOT belong here

- Business logic or application code
- Hard-coded credentials, tokens or hostnames of real environments
- Destructive operations against non-local environments
- Anything that silently downloads and executes remote code

## Populated by

| Task | Adds |
|---|---|
| T00-02 | Local development helpers |
| T00-03 | Docker Compose helpers (implemented as root `package.json` scripts) |
| T00-04 ✅ | `check-env.mjs` |
| T00-05 ✅ | `ci/install-tool.sh`, `ci/gitleaks-selftest.sh`, `ci/docker-smoke.sh` |
