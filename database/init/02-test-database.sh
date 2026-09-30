#!/usr/bin/env bash
# =============================================================================
# MTI 360 — local test database (T01-01, decision D5)
# =============================================================================
#
# Creates "${POSTGRES_DB}_test" for the backend integration and security tests,
# with exactly the same ownership, privileges and default privileges as the
# main database created by 01-roles.sh (which must run first). Tests migrate it
# as mti_owner and exercise it as mti_app / mti_readonly, so Row-Level Security
# and grants behave as in the application database.
#
# Runs automatically when the container initialises an EMPTY volume. It is
# idempotent, so an existing local volume can be upgraded without data loss:
#
#   docker compose exec postgres bash /docker-entrypoint-initdb.d/02-test-database.sh
#
# The test database holds no real data; tests create and remove their own
# fixtures.
# =============================================================================
set -euo pipefail

: "${POSTGRES_DB:?POSTGRES_DB must be set}"
: "${POSTGRES_USER:?POSTGRES_USER must be set}"

test_db="${POSTGRES_DB}_test"

psql --no-psqlrc -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v test_db="$test_db" <<'SQL'
SELECT format('CREATE DATABASE %I OWNER mti_owner', :'test_db')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'test_db')
\gexec

SELECT format('REVOKE ALL ON DATABASE %I FROM PUBLIC', :'test_db') \gexec
SELECT format('GRANT CONNECT, TEMPORARY ON DATABASE %I TO mti_app', :'test_db') \gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO mti_readonly', :'test_db') \gexec
SQL

psql --no-psqlrc -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$test_db" <<'SQL'
ALTER SCHEMA public OWNER TO mti_owner;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO mti_app, mti_readonly;

ALTER DEFAULT PRIVILEGES FOR ROLE mti_owner IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO mti_app;
ALTER DEFAULT PRIVILEGES FOR ROLE mti_owner IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO mti_app;
ALTER DEFAULT PRIVILEGES FOR ROLE mti_owner IN SCHEMA public
  GRANT SELECT ON TABLES TO mti_readonly;
ALTER DEFAULT PRIVILEGES FOR ROLE mti_owner IN SCHEMA public
  GRANT SELECT ON SEQUENCES TO mti_readonly;
ALTER DEFAULT PRIVILEGES FOR ROLE mti_owner IN SCHEMA public
  REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE mti_owner IN SCHEMA public
  GRANT EXECUTE ON FUNCTIONS TO mti_app;
SQL

echo "MTI 360: test database ${test_db} ready (owner mti_owner)."
