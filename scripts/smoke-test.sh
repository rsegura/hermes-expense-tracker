#!/usr/bin/env bash
# Quick LLM smoke tests via hermes chat (requires working model in profile).
set -euo pipefail

usage() {
  echo "Usage: $0 <profile>" >&2
  echo "  e.g. $0 expense-alice" >&2
  echo "  Requires model configured in profile and MCP connected." >&2
  exit 1
}

PROFILE="${1:-}"
[[ -n "${PROFILE}" ]] || usage

PROFILE_ENV="${HOME}/.hermes/profiles/${PROFILE}/.env"
LOCALE="en"
if [[ -f "${PROFILE_ENV}" ]] && grep -q '^EXPENSE_LOCALE=' "${PROFILE_ENV}" 2>/dev/null; then
  LOCALE="$(grep '^EXPENSE_LOCALE=' "${PROFILE_ENV}" | tail -1 | cut -d= -f2- | tr -d '[:space:]')"
fi
case "${LOCALE}" in en|es) ;; *) LOCALE="en" ;; esac

run_test() {
  local label="$1"
  local query="$2"
  echo
  echo "── ${label} ──"
  hermes -p "${PROFILE}" chat -q "${query}" -Q --max-turns 30 2>&1 | tail -20
}

echo "Smoke test: ${PROFILE} (locale: ${LOCALE})"

if [[ "${LOCALE}" == "es" ]]; then
  run_test "Gasto simple" "9000 en kiosco"
  run_test "Consulta" "¿Cuánto gastamos este mes?"
else
  run_test "Simple expense" "Log 9000 at the kiosk"
  run_test "Query" "How much did we spend this month?"
fi

echo
echo "Done."
