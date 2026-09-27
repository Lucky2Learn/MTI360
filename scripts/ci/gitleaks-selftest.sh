#!/usr/bin/env bash
# =============================================================================
# MTI 360 — gitleaks detection self-test (T00-05)
#
#   bash scripts/ci/gitleaks-selftest.sh        (gitleaks must be on PATH)
#
# Proves, against the repository's own .gitleaks.toml, that:
#   1. a credential-shaped value is detected;
#   2. a DIFFERENT value in an allowlisted file is still detected
#      (the allowlist is value-specific, not file-wide);
#   3. the documented fake value is still detected OUTSIDE its allowlisted files
#      (the allowlist is path-specific, not value-wide);
#   4. the documented fake value in its allowlisted file is not reported.
#
# Every fixture lives in a throwaway git repository under mktemp and is deleted
# on exit. Test secrets are generated at runtime and never committed.
# =============================================================================
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
config="${repo_root}/.gitleaks.toml"
leak_exit=42
failures=0

# The one documented fake value allowlisted in .gitleaks.toml.
documented_fake="mti360-test-csrf-secret-0123456789abcdef"

random_hex() {
  local hex
  hex="$(od -An -tx1 -N32 /dev/urandom | tr -d ' \n')"
  printf '%s' "${hex:0:$1}"
}

work_dir="$(mktemp -d)"
trap 'rm -rf "${work_dir}"' EXIT

# run_case <name> <expected: detected|clean> <file path> <file content>
run_case() {
  local name="$1" expected="$2" file="$3" content="$4"
  local repo="${work_dir}/${name}"
  local status=0 actual

  mkdir -p "${repo}/$(dirname "${file}")"
  git -C "${repo}" init --quiet
  printf '%s\n' "${content}" > "${repo}/${file}"
  git -C "${repo}" add -A
  # Throwaway fixture repository: local identity, no signing, no hooks.
  git -C "${repo}" -c user.name="gitleaks selftest" -c user.email="selftest@invalid" \
    -c commit.gpgsign=false -c core.hooksPath=/dev/null commit --quiet -m fixture

  gitleaks git --no-banner --redact --log-level error --exit-code "${leak_exit}" \
    --config "${config}" "${repo}" > /dev/null 2>&1 || status=$?

  case "${status}" in
    0) actual=clean ;;
    "${leak_exit}") actual=detected ;;
    *) echo "FAIL ${name}: gitleaks error (exit ${status})"; failures=$((failures + 1)); return ;;
  esac

  if [ "${actual}" = "${expected}" ]; then
    echo "PASS ${name}: ${actual}"
  else
    echo "FAIL ${name}: expected ${expected}, got ${actual}"
    failures=$((failures + 1))
  fi
}

run_case credential-detected detected "config/service.txt" \
  "token: ghp_$(random_hex 36)"

run_case allowlisted-file-other-value detected "backend/tests/conftest.py" \
  "TEST_CSRF_SECRET = \"mti360-$(random_hex 40)\""

run_case documented-value-other-file detected "backend/app/settings_copy.py" \
  "TEST_CSRF_SECRET = \"${documented_fake}\""

run_case documented-value-allowlisted-file clean "backend/tests/conftest.py" \
  "TEST_CSRF_SECRET = \"${documented_fake}\""

if [ "${failures}" -ne 0 ]; then
  echo "::error::gitleaks self-test failed (${failures} case(s))."
  exit 1
fi
echo "gitleaks self-test passed."
