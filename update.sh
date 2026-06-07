#!/usr/bin/env bash
# Update MCP + all expense-* Hermes profiles (skills, SOUL, Telegram UX).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MCP_DIR="${ROOT}/mcp/expense-tracker"
VENV="${MCP_DIR}/.venv"
DB_PATH="${HOME}/expenses/data/expenses.db"

echo "==> Hermes Expense Tracker — update"
echo

echo "==> Bootstrap MCP"
QUIET=1 "${ROOT}/bootstrap.sh"

if [[ ! -x "${VENV}/bin/python" ]]; then
  echo "MCP venv missing after bootstrap." >&2
  exit 1
fi

echo
echo "==> DB migrations (project members)"
export EXPENSE_DB_PATH="${DB_PATH}"
"${VENV}/bin/python" - <<PY
import sys
sys.path.insert(0, "${MCP_DIR}")
from expense_tracker.db import init_db
init_db(seed=False)
print("migrations ok")
PY

echo
echo "==> Cleanup DB (personas expense-* duplicadas)"
"${ROOT}/scripts/cleanup-db.sh" || true

PROFILES_DIR="${HOME}/.hermes/profiles"
if [[ ! -d "${PROFILES_DIR}" ]]; then
  echo "No profiles in ${PROFILES_DIR}" >&2
  exit 0
fi

shopt -s nullglob
for profile_dir in "${PROFILES_DIR}"/expense-*; do
  profile="$(basename "${profile_dir}")"
  slug="${profile#expense-}"

  if [[ "${slug}" == expense-* ]]; then
    echo "⚠ Saltando perfil mal formado: ${profile}"
    echo "  Corré: ./scripts/repair-profile.sh <slug> <nombre> ${profile}"
    continue
  fi

  echo
  echo "── ${profile} ──"

  display_name="$("${VENV}/bin/python" - <<PY
import os, sys
sys.path.insert(0, "${MCP_DIR}")
os.environ["EXPENSE_DB_PATH"] = "${DB_PATH}"
from expense_tracker import repositories as repo
from expense_tracker.db import init_db
init_db(seed=False)
slug = "${slug}"
for p in repo.list_persons():
    if p["slug"] == slug:
        print(p["display_name"])
        break
else:
    print(slug.capitalize())
PY
)"

  PROFILE_ENV="${profile_dir}/.env"
  LOCALE="es"
  if [[ -f "${PROFILE_ENV}" ]] && grep -q '^EXPENSE_LOCALE=' "${PROFILE_ENV}" 2>/dev/null; then
    LOCALE="$(grep '^EXPENSE_LOCALE=' "${PROFILE_ENV}" | tail -1 | cut -d= -f2-)"
  elif [[ -f "${HOME}/expenses/locale" ]]; then
    LOCALE="$(tr -d '[:space:]' < "${HOME}/expenses/locale")"
  fi
  case "${LOCALE}" in en|es) ;; *) LOCALE="es" ;; esac
  # shellcheck source=scripts/lib/locale.sh
  source "${ROOT}/scripts/lib/locale.sh"
  save_household_locale "${LOCALE}"

  hermes profile update "${profile}" -y
  INSTALL_QUIET=1 SKIP_PREREQ=1 EXPENSE_LOCALE="${LOCALE}" "${ROOT}/add-member.sh" "${slug}" "${display_name}"
  INSTALL_QUIET=1 EXPENSE_LOCALE="${LOCALE}" "${ROOT}/scripts/apply-telegram-ux.sh" "${profile}" >/dev/null

  if hermes -p "${profile}" gateway status >/dev/null 2>&1; then
    hermes -p "${profile}" gateway restart >/dev/null 2>&1 || true
    echo "✓ ${profile} (${display_name}) — gateway restarted"
  else
    echo "✓ ${profile} (${display_name}) — gateway not running"
  fi
done

echo
echo "Update listo. Probar:"
echo "  ./scripts/smoke-test.sh expense-alice"
