#!/usr/bin/env bash
# =============================================================================
# MTI 360 — PostgreSQL for the backend integration tests in CI (T01-01, D5)
#
#   bash scripts/ci/start-test-database.sh
#
# 1. Writes a throw-away root .env from .env.example, replacing every
#    `change-me` placeholder with a fresh random hex value (never printed,
#    never committed; the runner is discarded after the job).
# 2. Starts ONLY the compose `postgres` service (profile infra) on a fresh
#    volume, so database/init creates the three roles and the test database
#    exactly as in local development.
# 3. Exports TEST_DATABASE_URL, TEST_MIGRATIONS_DATABASE_URL and
#    TEST_READONLY_DATABASE_URL (masked) and REQUIRE_DATABASE_TESTS=1 to the
#    following steps, so missing database tests fail instead of skipping.
#
# CI only: refuses to run outside GitHub Actions or when a .env already exists,
# so it can never overwrite a developer's local configuration.
# =============================================================================
set -euo pipefail

[ "${GITHUB_ACTIONS:-}" = "true" ] || { echo "CI only (GITHUB_ACTIONS is not true)" >&2; exit 2; }
[ -n "${GITHUB_ENV:-}" ] || { echo "GITHUB_ENV is not set" >&2; exit 2; }
[ ! -e .env ] || { echo ".env already exists; refusing to overwrite it" >&2; exit 2; }

random_hex() { od -An -tx1 -N24 /dev/urandom | tr -d ' \n'; }

umask 077
while IFS= read -r line; do
  if [[ "${line}" == *=change-me ]]; then
    value="$(random_hex)"
    echo "::add-mask::${value}"
    printf '%s=%s\n' "${line%%=*}" "${value}"
  else
    printf '%s\n' "${line}"
  fi
done < .env.example > .env

docker compose --profile infra up --detach --wait postgres

set -a
# shellcheck disable=SC1091 # generated above
. ./.env
set +a

base="127.0.0.1:${POSTGRES_PORT:-5432}/${POSTGRES_DB:-mti360}_test"
{
  echo "TEST_DATABASE_URL=postgresql+asyncpg://mti_app:${MTI_APP_PASSWORD}@${base}"
  echo "TEST_MIGRATIONS_DATABASE_URL=postgresql+asyncpg://mti_owner:${MTI_OWNER_PASSWORD}@${base}"
  echo "TEST_READONLY_DATABASE_URL=postgresql+asyncpg://mti_readonly:${MTI_READONLY_PASSWORD}@${base}"
  echo "REQUIRE_DATABASE_TESTS=1"
} >> "${GITHUB_ENV}"

echo "PostgreSQL test database ready (${POSTGRES_DB:-mti360}_test)."
