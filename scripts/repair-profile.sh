#!/usr/bin/env bash
# Fix a malformed profile (e.g. expense-expense-johanna) by creating expense-<slug> correctly.
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <slug> <display_name> [old_profile_name]" >&2
  echo "Example: $0 johanna Johanna expense-expense-johanna" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SLUG="$1"
DISPLAY_NAME="$2"
OLD_PROFILE="${3:-expense-expense-${SLUG}}"
NEW_PROFILE="expense-${SLUG}"

echo "==> Creating/repairing profile ${NEW_PROFILE}"
SKIP_PREREQ=1 INSTALL_QUIET=1 "${ROOT}/add-member.sh" "${SLUG}" "${DISPLAY_NAME}"

OLD_DIR="${HOME}/.hermes/profiles/${OLD_PROFILE}"
NEW_DIR="${HOME}/.hermes/profiles/${NEW_PROFILE}"

if [[ -d "${OLD_DIR}" && "${OLD_PROFILE}" != "${NEW_PROFILE}" ]]; then
  echo "==> Migrating config from ${OLD_PROFILE}"
  for f in config.yaml .env; do
    if [[ -f "${OLD_DIR}/${f}" && -f "${NEW_DIR}/${f}" ]]; then
      cp "${OLD_DIR}/${f}" "${NEW_DIR}/${f}.migrated.bak"
      cp "${OLD_DIR}/${f}" "${NEW_DIR}/${f}"
      echo "  copied ${f}"
    fi
  done
  hermes -p "${OLD_PROFILE}" gateway stop >/dev/null 2>&1 || true
  hermes -p "${NEW_PROFILE}" gateway start >/dev/null 2>&1 || true
  echo
  echo "Gateway: detenido ${OLD_PROFILE}, iniciado ${NEW_PROFILE}"
  echo "Perfil viejo aún en disco: ${OLD_DIR}"
  echo "  (opcional) rm -rf ${OLD_DIR}"
fi

echo
echo "==> DB cleanup (personas duplicadas expense-*)"
"${ROOT}/scripts/cleanup-db.sh"

echo
echo "==> Update + SOUL"
hermes profile update "${NEW_PROFILE}" -y
SKIP_PREREQ=1 INSTALL_QUIET=1 "${ROOT}/add-member.sh" "${SLUG}" "${DISPLAY_NAME}"

echo
echo "Listo. Probar:"
echo "  hermes -p ${NEW_PROFILE} gateway restart"
echo "  hermes -p ${NEW_PROFILE} chat -q '5000 en farmacia' -Q"
