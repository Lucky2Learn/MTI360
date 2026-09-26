# scripts/

**Status:** Reserved. No scripts exist yet.

## Purpose

Thin developer helper scripts that wrap documented commands (for example: start local infrastructure, run migrations, reset the local database, run all checks).

Scripts are provided as POSIX shell (`.sh`) and, where Windows developers need them, PowerShell (`.ps1`). Each script must also be reproducible by running its documented underlying commands directly.

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
| T00-03 | Docker Compose helpers |
| T00-05 | CI check helpers |
