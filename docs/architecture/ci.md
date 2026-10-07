# Continuous Integration

- **Status:** Implemented in T00-05 (2026-09-27); verified locally, GitHub verification after the first push
- **Decision basis:** T00-05 proposal decisions D1–D10 (approved); [ADR-0002](../adr/0002-monorepo-layout.md) ("a single CI pipeline must understand both Python and Node toolchains")
- **Related:** [toolchain.md](toolchain.md), [security.md](security.md), [environments.md](environments.md), [repository-structure.md](repository-structure.md)

CI runs the project's existing quality and security gates on every pull request to `main`, every push to `main` and on demand. It needs no secrets and reports **one required status: `ci-ok`**.

## 1. Workflows

| Workflow | File | Triggers | Role |
|---|---|---|---|
| **CI** | `.github/workflows/ci.yml` | PR → `main`, push → `main`, manual | **Required** gates; aggregated by `ci-ok` |
| **CodeQL** | `.github/workflows/codeql.yml` | PR → `main`, push → `main`, weekly (Mon 03:23 UTC), manual | Reporting only (Security → Code scanning) |
| **Audit** | `.github/workflows/audit.yml` | PR → `main`, push → `main`, weekly (Mon 04:17 UTC), manual | Reporting only; a finding shows as a failed run |
| **Dependabot** | `.github/dependabot.yml` | Monthly | Update PRs for `github-actions`, `docker`, `docker-compose` only (§6) |

All jobs run on `ubuntu-24.04`. Superseded pull request runs are cancelled (`concurrency`, `cancel-in-progress` only for `pull_request`); runs on `main` always complete.

## 2. CI jobs

The five jobs are independent and run in parallel. They call the existing root scripts in `package.json`; no check is implemented a second time in YAML.

```text
PR / push to main / dispatch
 ├─ repo ──────┐
 ├─ frontend ──┤
 ├─ backend ───┼──► ci-ok   (the only required status)
 ├─ secrets ───┤
 └─ docker ────┘
```

| Job | Steps (commands) |
|---|---|
| **repo** | `pnpm run check:landing` (needs full history + the `marketing-site-v1` tag) · `pnpm run check:env` · actionlint (with shellcheck of every `run:` block) |
| **frontend** | `pnpm install --frozen-lockfile` · `pnpm run format:check:frontend` · `lint:frontend` · `typecheck:frontend` · `test:frontend` · `build` |
| **backend** | `bash scripts/ci/start-test-database.sh` (T01-01: compose `postgres` on a fresh volume, generated masked passwords, exports `TEST_*_DATABASE_URL` and `REQUIRE_DATABASE_TESTS=1`) · `uv sync --locked --directory backend` · `pnpm run check:lock` (`uv lock --check`) · `format:check:backend` · `lint:backend` (Ruff + import-linter) · `typecheck:backend` · `test:backend` (including the PostgreSQL integration tests) · `docker compose --profile infra down --volumes` (always) |
| **secrets** | `gitleaks git --log-opts="--all" --redact --config .gitleaks.toml .` (full history, all refs) · `bash scripts/ci/gitleaks-selftest.sh` |
| **docker** | `docker build` of `mti360-api:ci` and `mti360-frontend:ci` (never pushed) · `bash scripts/ci/docker-smoke.sh mti360-api:ci` · `docker compose --env-file .env.example --profile infra --profile app config --quiet` |
| **ci-ok** | `needs` all five, `if: always()`; fails unless every result is `success` (failure, cancelled or skipped all fail it) |

Toolchain on the runner: `actions/setup-node` reads `.nvmrc` (24.21.0); `corepack enable pnpm` activates pnpm 11.28.0 from `packageManager`; `astral-sh/setup-uv` installs uv 0.12.19 with a pinned SHA-256; uv provides Python 3.14 from `backend/.python-version`. Only the uv cache is enabled (keyed on `backend/uv.lock`); there is no pnpm store cache (D4). `NEXT_TELEMETRY_DISABLED=1`.

**Docker smoke test** (`scripts/ci/docker-smoke.sh`): the API image runs with the compose hardening (read-only root filesystem, tmpfs `/tmp`, all capabilities dropped, `no-new-privileges`) on a random `127.0.0.1` port; `GET /health` must return `200` with `{"status":"ok"}` and the image `HEALTHCHECK` must report `healthy`. Then `APP_ENV=production` with no other configuration must exit non-zero with a `ConfigurationError` that names variables and prints no values. Only containers named `mti360-ci-*` are created, and they are always removed. The frontend image is built but not started (D6). `compose config` only renders the configuration; it creates no containers, networks or volumes.

## 3. Security model

| Control | Implementation |
|---|---|
| Least privilege | Workflow-level `permissions: contents: read`; `ci-ok` has `permissions: {}`; CodeQL adds only `security-events: write` |
| No secrets | No `secrets.*`, no GitHub Environments, no registry login; CI needs no credentials |
| No privileged triggers | No `pull_request_target` or `workflow_run` |
| Credentials not persisted | Every `actions/checkout` uses `persist-credentials: false` |
| No script injection | No `${{ github.event.* }}` or other untrusted value inside `run:`; dynamic values go through `env:`. actionlint enforces this |
| Pinned actions | Full 40-character commit SHAs with a version comment; release ≥ 7 days old when pinned (§4) |
| Pinned tools | gitleaks and actionlint via `scripts/ci/install-tool.sh`: pinned version, SHA-256 recorded in the script, mismatch aborts before extraction; uv via `setup-uv` with a pinned checksum |
| Images | Built locally on the runner and never pushed |

### Secret scanning (gitleaks)

- **Scope:** the full history of every ref (`--log-opts="--all"` after a `fetch-depth: 0` checkout), with the default gitleaks rules. `--redact` keeps values out of logs.
- **Allowlist (`.gitleaks.toml`):** three entries, each found by a real scan, each with `condition = "AND"` (exact path **and** exact value):
  - the documented fake T00-04 `TEST_CSRF_SECRET` value (`mti360-test-csrf-secret-0123456789abcdef`) **only** in `backend/tests/conftest.py` and `backend/tests/unit/test_settings_environments.py` (baseline scan);
  - the fake TOTP setup key `KRSXG5CTMVRXEZLUKRSXG5CTMVRXEZLU` **only** in `frontend/src/features/platform-identity/security.test.tsx` (T01-09B leak-check fixture, found by the T01-10 gate);
  - the fake password `Halyard-Mizzen-Leeward-8` **only** in `frontend/src/features/identity/TenantMfa.test.tsx` (T01-09C leak-check fixture, found by the T01-10 gate).

  The two frontend values were already committed when the gate found them; history is not rewritten, so they are allowlisted rather than replaced. There are no directory globs, disabled rules or stopwords. The other fake test values are not flagged by the default rules and are not allowlisted.
- **Self-test (`scripts/ci/gitleaks-selftest.sh`):** runs in CI every time. In throwaway repositories under `mktemp`, with values generated at runtime and never committed, it proves that (1) a credential-shaped value is detected; (2) a different value in an allowlisted file is still detected; (3) the documented fake value outside its allowlisted files is still detected; (4) the documented fake value in its allowlisted file is not reported. Cases (2)–(4) run for every allowlist entry (T01-10 added them for the two frontend fixtures).
- **Adding an allowlist entry** requires a real finding of a documented fake value, the exact path and exact value, and a self-test case. A real secret is never allowlisted: rotate it and remove it from history instead.

## 4. Pinned versions

Pinned on 2026-09-27; each release was at least 7 days old.

| Action | Version | Commit SHA | Released |
|---|---|---|---|
| `actions/checkout` | v7.0.1 | `3d3c42e5aac5ba805825da76410c181273ba90b1` | 2026-07-20 |
| `actions/setup-node` | v7.0.0 | `820762786026740c76f36085b0efc47a31fe5020` | 2026-07-14 |
| `astral-sh/setup-uv` | v10.1.0 | `bec219d24cd3e171d82865faccec33120bb574f4` | 2026-09-10 |
| `github/codeql-action` (`init`, `analyze`) | v4.38.1 | `1c5b675653bb5c22dbe9b12b556ec555138e09fd` | 2026-09-18 |

| Tool | Version | Released | Verification |
|---|---|---|---|
| gitleaks | 8.30.1 | 2026-03-21 | SHA-256 in `install-tool.sh` (linux-x64, windows-x64, darwin-arm64), cross-checked against the release checksums file and the downloaded archives |
| actionlint | 1.7.12 | 2026-03-30 | Same as gitleaks |
| uv | 0.12.19 | 2026-09-25 | Pinned by T00-02 (`required-version`); `setup-uv` checksum `23bf5552…d8c8` (linux x86_64). Like pnpm, the tool version is an explicit toolchain pin, not a dependency subject to the cooldown |
| pip-audit | 2.10.1 | 2026-06-10 | Installed with `uv tool run --exclude-newer "7 days"` |

**Updating a pin:** choose a release at least 7 days old; resolve the tag to its commit SHA (dereference annotated tags: `git ls-remote <repo> 'refs/tags/<tag>^{}'`); update the `uses:` line and the version comment together (Dependabot does both for actions); for binaries, update the version and every platform hash in `install-tool.sh` from the release checksums file; update this table.

## 5. CodeQL and dependency audits (reporting only)

- **CodeQL:** `python` and `javascript-typescript` with `build-mode: none`. Results appear under Security → Code scanning.
- **Audit:** `pnpm audit` (locked frontend dependencies) and `pip-audit --strict --require-hashes --disable-pip` against a hashed `uv export --locked --all-groups` of the backend.
- Neither is part of `ci-ok` or a required check. Making them required is a later, explicit decision.

### Audit exceptions

Exceptions live in `pnpm-workspace.yaml` under `audit.ignore` (pnpm 11; the older
`auditConfig.ignoreGhsas` is deprecated). One advisory ID per entry, each with a
justification and the condition for removing it. Never ignore a package name, a
severity level or the audit itself — those would hide unrelated findings.

| Advisory | Package | Severity | Path | Why excepted | Revisit when |
|---|---|---|---|---|---|
| [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) | `braces@3.0.3` (stack-exhaustion denial of service through deeply nested patterns) | high | `@mti360/frontend` → `eslint-config-next@16.3.6` → `@next/eslint-plugin-next@16.3.6` → `fast-glob@3.3.1` → `micromatch@4.0.8` → `braces@3.0.3` | **No patched braces release currently exists** upstream (advisory: “Patched versions: None”), and updating the chain does not remove it. It is a development/tooling dependency and is not included in the production frontend bundle or runtime image. Pinning or overriding braces is therefore not an option, and the hold mirrors the ESLint 9 hold in [toolchain.md §3](toolchain.md#3-deliberate-version-holds). | A patched `braces` is published — remove the entry and re-run `pnpm audit`. Re-checked with the monthly dependency batch ([toolchain.md §8](toolchain.md#8-update-policy)). |

## 6. Dependabot (decision D7)

| Ecosystem | Enabled | Notes |
|---|---|---|
| `github-actions` | Yes | Updates the SHA and version comment together |
| `docker` | Yes | `backend/`, `frontend/` Dockerfiles. Base images are declared through `ARG` defaults (`FROM ${PYTHON_IMAGE}`); whether Dependabot detects them is confirmed on GitHub after the first run |
| `docker-compose` | Yes | `compose.yaml` infrastructure images |
| `npm` (pnpm) | **No** | Dependabot documents pnpm v7–v10; MTI 360 pins pnpm 11.28.0. Compatibility could not be established |
| `uv` | **No** | `[tool.uv] required-version = ">=0.12.19,<0.13"` makes uv refuse to run under a Dependabot-bundled uv outside that range; Dependabot does not manage `required-version` (dependabot-core #14376) |

Every enabled ecosystem is monthly, grouped (one PR per ecosystem) and uses a 7-day cooldown. Major versions are not proposed (each is a dedicated task, [toolchain.md §8](toolchain.md#8-update-policy)); explicit holds: uv image `>=0.13`, Python `>=3.15`, Node `>=25`.

Frontend (pnpm) and backend (uv) dependencies follow the manual monthly update policy in toolchain.md §8. **Revisit** when Dependabot documents pnpm 11 support and when its uv support can satisfy `required-version`.

## 7. Reproducing CI locally

Run from the repository root (Git Bash on Windows).

```bash
# repo + frontend + backend jobs (plus the Next.js build)
pnpm bootstrap
pnpm check          # check:landing, check:env, check:lock, format, lint, typecheck, test, build

# Tools, outside the repository (pinned and checksum-verified)
TOOLS="${TMPDIR:-/tmp}/mti360-ci-bin"
bash scripts/ci/install-tool.sh actionlint "$TOOLS"
bash scripts/ci/install-tool.sh gitleaks "$TOOLS"
export PATH="$TOOLS:$PATH"

# repo job: workflow linting (run blocks are shellchecked when shellcheck is installed)
actionlint

# secrets job
gitleaks git --log-opts="--all" --redact --config .gitleaks.toml .
bash scripts/ci/gitleaks-selftest.sh

# docker job (creates only mti360-*:ci images and mti360-ci-* containers)
docker build --tag mti360-api:ci backend
docker build --file frontend/Dockerfile --tag mti360-frontend:ci .
bash scripts/ci/docker-smoke.sh mti360-api:ci
docker compose --env-file .env.example --profile infra --profile app config --quiet

# Audit workflow
pnpm audit
uv export --locked --directory backend --format requirements-txt --all-groups --quiet --output-file "$TOOLS/requirements.txt"
uv tool run --exclude-newer "7 days" --from pip-audit==2.10.1 pip-audit --strict --require-hashes --disable-pip -r "$TOOLS/requirements.txt"
```

- The checks need the `marketing-site-v1` tag locally (`git fetch --tags`).
- Other Docker projects on the same machine (for example ACRS) are never touched: the commands above build and run only `mti360-*:ci` / `mti360-ci-*` resources, and `compose config` creates nothing. Never run `docker compose` with `-p` or `COMPOSE_PROJECT_NAME`.
- Remove the local CI images afterwards with `docker image rm mti360-api:ci mti360-frontend:ci`.

## 8. Branch protection (future configuration — not applied in T00-05)

Apply after the first green CI run on `main` (the `ci-ok` check must have run once to be selectable). Git workflow: **feature branch → pull request → Create a merge commit → `main`**.

**Repository ruleset** for `main` (Settings → Rules → Rulesets, or `POST /repos/Lucky2Learn/MTI360/rulesets`):

```json
{
  "name": "main",
  "target": "branch",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["refs/heads/main"], "exclude": [] } },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": false,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": true,
        "allowed_merge_methods": ["merge"]
      }
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": true,
        "required_status_checks": [{ "context": "ci-ok", "integration_id": 15368 }]
      }
    }
  ]
}
```

| Setting | Value |
|---|---|
| Pull request required | Yes, **0 approvals** |
| Conversations resolved before merging | Yes |
| Allowed merge method | **Merge commit only** (squash is not required and not allowed) |
| Required status check | **`ci-ok`** from GitHub Actions (app ID 15368), branch **must be up to date** with `main` |
| Force push | Blocked (`non_fast_forward`) |
| Branch deletion | Blocked (`deletion`) |
| Require linear history | **Not enabled** (it would block merge commits) |

Also set, under Settings → General → Pull Requests: **Allow merge commits** on; **Allow squash merging** and **Allow rebase merging** off.

CodeQL and the Audit workflow are not required checks.

## 9. Out of scope (T00-05)

Deployment/CD; staging and production infrastructure; registry pushes; GitHub Environments and secrets; Playwright/E2E; coverage thresholds; SBOM, signing and provenance; digest pinning of base images; merge queue; Dependabot for npm/pnpm and uv; applying branch protection.

## 10. Decisions (T00-05)

| # | Decision |
|---|---|
| D1 | Three workflows: `ci.yml` (required via `ci-ok`), `codeql.yml` and `audit.yml` (reporting only) |
| D2 | Minimal action set (checkout, setup-node, setup-uv, codeql-action); Docker and Corepack used natively; gitleaks and actionlint as checksum-pinned binaries |
| D3 | Root scripts `format:check:frontend`, `format:check:backend`, `check:lock`; `format:check` composes the first two and `check:lock` is part of `pnpm check` |
| D4 | Cache only uv; no pnpm store cache |
| D5 | gitleaks over all refs with `--redact`; allowlist only for real findings, exact path AND exact value |
| D6 | Docker smoke test starts the API only; the frontend image is built |
| D7 | Dependabot for `github-actions`, `docker`, `docker-compose` only |
| D8 | CodeQL and audits visible (red on findings) but not required |
| D9 | ACRS confirmed unchanged by comparing container, volume and network listings only |
| D10 | Future branch protection as in §8: PR, 0 approvals, conversations resolved, merge commit only, `ci-ok` required and up to date, no force push, no deletion, no linear-history rule |
