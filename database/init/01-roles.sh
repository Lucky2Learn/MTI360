#!/usr/bin/env bash
# =============================================================================
# MTI 360 — local PostgreSQL role bootstrap (T00-03, ADR-0004)
# =============================================================================
#
# Runs ONCE, automatically, when the local Postgres container initialises an
# EMPTY data volume (docker-entrypoint-initdb.d). It never runs again on an
# existing volume; use `pnpm infra:reset` to start from empty volumes.
#
# Creates three LOGIN roles. Passwords come ONLY from environment variables
# (root .env, never committed):
#
#   mti_owner     Owns the application database and the `public` schema.
#                 Future Alembic migrations run as this role.
#   mti_app       Application runtime role: data manipulation (DML) only.
#   mti_readonly  Reporting / governed SQL-Data-Agent role: SELECT only.
#
# None of the roles is SUPERUSER, CREATEDB, CREATEROLE, REPLICATION or
# BYPASSRLS, so PostgreSQL Row-Level Security (added in Phase 01) applies to
# every one of them.
#
# Deliberately NOT done here: tables, application schemas, RLS policies,
# extensions (pgvector is not enabled yet).
# =============================================================================
set -euo pipefail

: "${POSTGRES_DB:?POSTGRES_DB must be set}"
: "${POSTGRES_USER:?POSTGRES_USER must be set}"
: "${MTI_OWNER_PASSWORD:?MTI_OWNER_PASSWORD must be set in .env}"
: "${MTI_APP_PASSWORD:?MTI_APP_PASSWORD must be set in .env}"
: "${MTI_READONLY_PASSWORD:?MTI_READONLY_PASSWORD must be set in .env}"

# Passwords are passed as psql variables and quoted with :'var', so they never
# appear in the SQL text and cannot break quoting.
psql --no-psqlrc -v ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v db_name="$POSTGRES_DB" \
  -v owner_password="$MTI_OWNER_PASSWORD" \
  -v app_password="$MTI_APP_PASSWORD" \
  -v readonly_password="$MTI_READONLY_PASSWORD" <<'SQL'
-- --- Roles ----------------------------------------------------------------
CREATE ROLE mti_owner LOGIN PASSWORD :'owner_password'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

CREATE ROLE mti_app LOGIN PASSWORD :'app_password'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

CREATE ROLE mti_readonly LOGIN PASSWORD :'readonly_password'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

-- --- Database ownership and connect privileges ------------------------------
ALTER DATABASE :"db_name" OWNER TO mti_owner;
REVOKE ALL ON DATABASE :"db_name" FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE :"db_name" TO mti_app;
GRANT CONNECT ON DATABASE :"db_name" TO mti_readonly;

-- --- public schema ----------------------------------------------------------
-- Only the owner may create objects; runtime roles may only use them.
ALTER SCHEMA public OWNER TO mti_owner;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO mti_app, mti_readonly;

-- --- Default privileges for objects that mti_owner creates later -----------
ALTER DEFAULT PRIVILEGES FOR ROLE mti_owner IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO mti_app;
ALTER DEFAULT PRIVILEGES FOR ROLE mti_owner IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO mti_app;
ALTER DEFAULT PRIVILEGES FOR ROLE mti_owner IN SCHEMA public
  GRANT SELECT ON TABLES TO mti_readonly;
ALTER DEFAULT PRIVILEGES FOR ROLE mti_owner IN SCHEMA public
  GRANT SELECT ON SEQUENCES TO mti_readonly;
-- Functions: EXECUTE is revoked from PUBLIC and granted explicitly per role.
ALTER DEFAULT PRIVILEGES FOR ROLE mti_owner IN SCHEMA public
  REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE mti_owner IN SCHEMA public
  GRANT EXECUTE ON FUNCTIONS TO mti_app;
SQL

echo "MTI 360: roles mti_owner, mti_app, mti_readonly created for database ${POSTGRES_DB}."
