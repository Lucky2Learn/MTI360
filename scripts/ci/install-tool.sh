#!/usr/bin/env bash
# =============================================================================
# MTI 360 — install a pinned, checksum-verified CI tool (T00-05)
#
#   bash scripts/ci/install-tool.sh <gitleaks|actionlint> <install-dir>
#
# Downloads the pinned release archive from GitHub, verifies its SHA-256
# against the value recorded IN THIS FILE, and only then extracts the binary
# into <install-dir>. A checksum mismatch aborts before anything is extracted.
#
# The recorded hashes were cross-checked against each release's published
# checksums file. To upgrade a tool: pick a release at least 7 days old,
# update VERSION and every hash below from its checksums file, and record the
# change in docs/architecture/ci.md.
#
# Supported platforms: linux-x64 (CI), windows-x64 (Git Bash), darwin-arm64.
# =============================================================================
set -euo pipefail

usage() {
  echo "usage: $0 <gitleaks|actionlint> <install-dir>" >&2
  exit 2
}

[ "$#" -eq 2 ] || usage
tool="$1"
install_dir="$2"

case "$(uname -s)" in
  Linux) os=linux ;;
  Darwin) os=darwin ;;
  MINGW* | MSYS* | CYGWIN*) os=windows ;;
  *) echo "Unsupported OS: $(uname -s)" >&2; exit 1 ;;
esac
case "$(uname -m)" in
  x86_64 | amd64) arch=x64 ;;
  arm64 | aarch64) arch=arm64 ;;
  *) echo "Unsupported architecture: $(uname -m)" >&2; exit 1 ;;
esac
platform="${os}-${arch}"

case "${tool}" in
  gitleaks)
    version="8.30.1"
    case "${platform}" in
      linux-x64)
        asset="gitleaks_${version}_linux_x64.tar.gz"
        sha256="551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb" ;;
      windows-x64)
        asset="gitleaks_${version}_windows_x64.zip"
        sha256="d29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e" ;;
      darwin-arm64)
        asset="gitleaks_${version}_darwin_arm64.tar.gz"
        sha256="b40ab0ae55c505963e365f271a8d3846efbc170aa17f2607f13df610a9aeb6a5" ;;
      *) echo "gitleaks: unsupported platform ${platform}" >&2; exit 1 ;;
    esac
    url="https://github.com/gitleaks/gitleaks/releases/download/v${version}/${asset}"
    ;;
  actionlint)
    version="1.7.12"
    case "${platform}" in
      linux-x64)
        asset="actionlint_${version}_linux_amd64.tar.gz"
        sha256="8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8" ;;
      windows-x64)
        asset="actionlint_${version}_windows_amd64.zip"
        sha256="6e7241b51e6817ea6a047693d8e6fed13b31819c9a0dd6c5a726e1592d22f6e9" ;;
      darwin-arm64)
        asset="actionlint_${version}_darwin_arm64.tar.gz"
        sha256="aba9ced2dee8d27fecca3dc7feb1a7f9a52caefa1eb46f3271ea66b6e0e6953f" ;;
      *) echo "actionlint: unsupported platform ${platform}" >&2; exit 1 ;;
    esac
    url="https://github.com/rhysd/actionlint/releases/download/v${version}/${asset}"
    ;;
  *) usage ;;
esac

sha256_of() {
  if command -v sha256sum > /dev/null 2>&1; then
    sha256sum "$1" | cut -d' ' -f1
  else
    shasum -a 256 "$1" | cut -d' ' -f1
  fi
}

work_dir="$(mktemp -d)"
trap 'rm -rf "${work_dir}"' EXIT

echo "Downloading ${tool} ${version} (${platform})"
curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
  --retry 3 --output "${work_dir}/${asset}" "${url}"

actual="$(sha256_of "${work_dir}/${asset}")"
if [ "${actual}" != "${sha256}" ]; then
  echo "::error::${tool} ${version}: SHA-256 mismatch for ${asset}" >&2
  echo "  expected ${sha256}" >&2
  echo "  actual   ${actual}" >&2
  exit 1
fi
echo "SHA-256 verified: ${actual}"

binary="${tool}"
[ "${os}" = windows ] && binary="${tool}.exe"

case "${asset}" in
  *.zip) unzip -q -o "${work_dir}/${asset}" "${binary}" -d "${work_dir}/out" ;;
  *) mkdir -p "${work_dir}/out" && tar -xzf "${work_dir}/${asset}" -C "${work_dir}/out" "${binary}" ;;
esac

mkdir -p "${install_dir}"
install -m 0755 "${work_dir}/out/${binary}" "${install_dir}/${binary}"
echo "Installed ${install_dir}/${binary}"
