# scripts/

**Status:** One script (T00-04).

| Script | Command | Purpose |
|---|---|---|
| `check-env.mjs` | `pnpm check:env` (part of `pnpm check`) | Environment template and secret hygiene: no tracked real `.env` files, placeholders only in secret-like template variables and URL credentials, no secret-like `NEXT_PUBLIC_*` names, and `backend/.env.example` ↔ `Settings` consistency. Node built-ins only; prints names, never values. |

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
| T00-05 | CI check helpers |
