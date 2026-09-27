#!/usr/bin/env bash
# =============================================================================
# MTI 360 — API container smoke test (T00-05)
#
#   bash scripts/ci/docker-smoke.sh <api-image>      e.g. mti360-api:ci
#
# 1. Starts the API image with the same hardening as compose.yaml (read-only
#    root filesystem, tmpfs /tmp, all capabilities dropped, no-new-privileges)
#    on a random 127.0.0.1 port, and asserts GET /health returns HTTP 200 with
#    {"status":"ok"} and that the image HEALTHCHECK reports "healthy".
# 2. Starts the image with APP_ENV=production and no other configuration and
#    asserts the process fails fast with a ConfigurationError that names
#    variables but never prints values.
#
# Touches only containers named mti360-ci-*, which are always removed on exit.
# Never uses docker compose, prune or any other project's resources.
# =============================================================================
set -euo pipefail

# Git Bash on Windows would rewrite container paths such as /tmp; no effect elsewhere.
export MSYS_NO_PATHCONV=1

[ "$#" -eq 1 ] || { echo "usage: $0 <api-image>" >&2; exit 2; }
image="$1"

suffix="$(od -An -tx1 -N4 /dev/urandom | tr -d ' \n')"
api_name="mti360-ci-api-${suffix}"
failfast_name="mti360-ci-failfast-${suffix}"
hardening=(--read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges:true)

cleanup() {
  docker rm -f "${api_name}" "${failfast_name}" > /dev/null 2>&1 || true
}
trap cleanup EXIT

fail() {
  echo "::error::$1" >&2
  if docker container inspect "${api_name}" > /dev/null 2>&1; then
    echo "--- ${api_name} logs ---" >&2
    docker logs "${api_name}" >&2 || true
  fi
  exit 1
}

# --- 1. Liveness ------------------------------------------------------------------
echo "Starting ${image} as ${api_name}"
docker run --detach --name "${api_name}" "${hardening[@]}" \
  --env APP_ENV=development --env LOG_LEVEL=INFO \
  --publish 127.0.0.1::8000 "${image}" > /dev/null

port="$(docker port "${api_name}" 8000/tcp | head -n 1 | sed 's/.*://')"
[ -n "${port}" ] || fail "could not determine the published API port"
url="http://127.0.0.1:${port}/health"

body=""
status=""
for _ in $(seq 1 30); do
  if body="$(curl --silent --show-error --max-time 2 --write-out '\n%{http_code}' "${url}" 2> /dev/null)"; then
    status="${body##*$'\n'}"
    body="${body%$'\n'*}"
    [ "${status}" = "200" ] && break
  fi
  sleep 1
done
[ "${status}" = "200" ] || fail "GET /health did not return 200 (last status: ${status:-none})"
[ "${body}" = '{"status":"ok"}' ] || fail "unexpected /health body: ${body}"
echo "PASS GET /health -> 200 ${body}"

health=""
for _ in $(seq 1 60); do
  health="$(docker inspect --format '{{.State.Health.Status}}' "${api_name}")"
  [ "${health}" = "healthy" ] && break
  sleep 1
done
[ "${health}" = "healthy" ] || fail "image HEALTHCHECK did not report healthy (last: ${health})"
echo "PASS image HEALTHCHECK -> healthy"

# --- 2. Production fails fast without configuration --------------------------------
echo "Starting ${image} with APP_ENV=production and no configuration"
output=""
exit_code=0
output="$(timeout 60 docker run --name "${failfast_name}" "${hardening[@]}" \
  --env APP_ENV=production "${image}" 2>&1)" || exit_code=$?

[ "${exit_code}" -ne 0 ] || fail "production start without configuration did not fail"
[ "${exit_code}" -ne 124 ] || fail "production start without configuration did not exit (timeout)"
grep -q "ConfigurationError" <<< "${output}" \
  || fail "production start failed, but not with a ConfigurationError"
grep -q "SESSION_SECRET" <<< "${output}" \
  || fail "ConfigurationError does not name the missing variables"
if grep -q "change-me" <<< "${output}"; then
  fail "ConfigurationError output contains a configuration value"
fi
echo "PASS production without configuration -> exit ${exit_code} (ConfigurationError, names only)"

echo "API smoke test passed."
