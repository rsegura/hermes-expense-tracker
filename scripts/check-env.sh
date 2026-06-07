#!/usr/bin/env bash
# Shared prerequisite checks for install.sh / add-member.sh

HERMES_MIN_VERSION="${HERMES_MIN_VERSION:-0.14.0}"

check_python3() {
  if ! command -v python3 >/dev/null 2>&1; then
    echo "✗ python3 not found in PATH." >&2
    echo "  Install Python 3.11+ and run the script again." >&2
    return 1
  fi
  local py_version
  py_version="$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"
  echo "✓ python3 ${py_version} ($(command -v python3))"
  if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    echo "  ⚠ Python 3.11+ recommended (you have ${py_version})" >&2
  fi
  return 0
}

check_hermes() {
  local hermes_bin version_line parsed_version

  if ! command -v hermes >/dev/null 2>&1; then
    echo "✗ Hermes CLI not installed or not in PATH." >&2
    echo "  Install Hermes Agent: https://hermes-agent.nousresearch.com" >&2
    echo "  Then verify with: hermes --version" >&2
    return 1
  fi

  hermes_bin="$(command -v hermes)"

  if ! version_line="$(hermes --version 2>&1)"; then
    echo "✗ 'hermes' exists (${hermes_bin}) but failed to run." >&2
    echo "  Output: ${version_line}" >&2
    return 1
  fi

  parsed_version="$(printf '%s\n' "$version_line" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)"
  if [[ -z "$parsed_version" ]]; then
    echo "✗ Could not parse Hermes version." >&2
    echo "  Output of 'hermes --version': ${version_line}" >&2
    return 1
  fi

  if [[ "$(printf '%s\n' "$HERMES_MIN_VERSION" "$parsed_version" | sort -V | tail -1)" != "$parsed_version" ]]; then
    echo "✗ Hermes ${parsed_version} is too old. Required >= ${HERMES_MIN_VERSION}." >&2
    echo "  Upgrade Hermes and run the script again." >&2
    return 1
  fi

  if ! hermes profile list >/dev/null 2>&1; then
    echo "✗ Hermes responds but 'hermes profile list' failed." >&2
    echo "  Check ~/.hermes or run 'hermes doctor' if available." >&2
    return 1
  fi

  echo "✓ Hermes ${parsed_version} (${hermes_bin})"
  return 0
}

require_prerequisites() {
  local need_hermes="${1:-1}"
  local failed=0

  echo "Checking prerequisites..."
  check_python3 || failed=1
  if [[ "$need_hermes" == "1" ]]; then
    check_hermes || failed=1
  fi
  echo

  if [[ "$failed" -ne 0 ]]; then
    echo "Install aborted. Fix prerequisites and try again." >&2
    return 1
  fi
  return 0
}
