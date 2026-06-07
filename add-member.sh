#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <slug> <display_name>" >&2
  echo "  slug: short id without expense- prefix (e.g. alice, johanna)" >&2
  echo "  Set EXPENSE_LOCALE=en|es or run ./install.sh first." >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/check-env.sh
source "${ROOT}/scripts/check-env.sh"
# shellcheck source=scripts/lib/slug.sh
source "${ROOT}/scripts/lib/slug.sh"
# shellcheck source=scripts/lib/locale.sh
source "${ROOT}/scripts/lib/locale.sh"

LOCALE="$(resolve_expense_locale)" || exit 1
LOCALE_DIR="${ROOT}/locales/${LOCALE}"
if [[ ! -f "${LOCALE_DIR}/SOUL.md" ]]; then
  echo "Missing locale files: ${LOCALE_DIR}/SOUL.md" >&2
  exit 1
fi

RAW_SLUG="$1"
DISPLAY_NAME="$2"
SLUG="$(normalize_member_slug "${RAW_SLUG}")"
if ! validate_member_slug "${SLUG}"; then
  exit 1
fi
if [[ "${RAW_SLUG}" != "${SLUG}" ]]; then
  echo "Nota: slug normalizado '${RAW_SLUG}' → '${SLUG}'" >&2
fi

PROFILE_NAME="expense-${SLUG}"
TEMPLATE="${ROOT}/profiles/expense-member"
MCP_DIR="${ROOT}/mcp/expense-tracker"
VENV="${MCP_DIR}/.venv"
DB_PATH="${EXPENSE_DB_PATH:-${HOME}/expenses/data/expenses.db}"
INSTALL_QUIET="${INSTALL_QUIET:-}"

log() {
  if [[ -z "${INSTALL_QUIET}" ]]; then
    echo "$@"
  fi
}

if [[ -z "${SKIP_PREREQ:-}" ]]; then
  require_prerequisites 1 || exit 1
fi

if [[ ! -x "${VENV}/bin/python" ]]; then
  echo "MCP venv not found. Run ./bootstrap.sh first." >&2
  exit 1
fi

log "==> Registering person '${SLUG}' in shared database"
export EXPENSE_DB_PATH="${DB_PATH}"
export PYTHONPATH="${MCP_DIR}:${PYTHONPATH:-}"
PERSON_MSG="$("${VENV}/bin/python" - <<PY
from expense_tracker import repositories as repo
from expense_tracker.db import init_db

init_db(seed=False)
slug = "${SLUG}"
name = """${DISPLAY_NAME}"""
try:
    person = repo.create_person(name, slug=slug)
    print(f"created:{person['slug']}")
except repo.ValidationError as exc:
    if "already exists" in str(exc):
        print(f"exists:{slug}")
    else:
        raise
PY
)"
log "${PERSON_MSG}"

log "==> Hermes profile ${PROFILE_NAME}"
if hermes profile show "${PROFILE_NAME}" >/dev/null 2>&1; then
  log "Profile ${PROFILE_NAME} already exists — skipping install"
else
  if [[ -n "${INSTALL_QUIET}" ]]; then
    hermes profile install "${TEMPLATE}" --name "${PROFILE_NAME}" -y >/dev/null
  else
    hermes profile install "${TEMPLATE}" --name "${PROFILE_NAME}" -y
  fi
fi

if command -v "${SLUG}" >/dev/null 2>&1 || [[ -x "${HOME}/.local/bin/${SLUG}" ]]; then
  log "Alias '${SLUG}' already exists — skipping"
elif hermes profile show "${PROFILE_NAME}" >/dev/null 2>&1; then
  log "==> Creating alias '${SLUG}' → ${PROFILE_NAME}"
  if [[ -n "${INSTALL_QUIET}" ]]; then
    hermes profile alias "${PROFILE_NAME}" --name "${SLUG}" >/dev/null
  else
    hermes profile alias "${PROFILE_NAME}" --name "${SLUG}"
  fi
fi

PROFILE_DIR="${HOME}/.hermes/profiles/${PROFILE_NAME}"
if [[ ! -d "${PROFILE_DIR}" ]]; then
  echo "Profile directory missing: ${PROFILE_DIR}" >&2
  exit 1
fi

log "==> Personalizing SOUL for ${DISPLAY_NAME} (slug: ${SLUG}, locale: ${LOCALE})"
sed \
  -e "s/{{MEMBER_NAME}}/${DISPLAY_NAME}/g" \
  -e "s/{{MEMBER_SLUG}}/${SLUG}/g" \
  "${LOCALE_DIR}/SOUL.md" > "${PROFILE_DIR}/SOUL.md"

if [[ -d "${LOCALE_DIR}/skills" ]]; then
  mkdir -p "${PROFILE_DIR}/skills"
  cp -R "${LOCALE_DIR}/skills/." "${PROFILE_DIR}/skills/"
fi

if [[ -f "${ROOT}/.env.paths" ]]; then
  if ! grep -q "EXPENSE_DB_PATH" "${PROFILE_DIR}/.env" 2>/dev/null; then
    cat "${ROOT}/.env.paths" >> "${PROFILE_DIR}/.env"
  fi
fi

ENV_FILE="${PROFILE_DIR}/.env"
touch "${ENV_FILE}"
if grep -q "^EXPENSE_MEMBER_SLUG=" "${ENV_FILE}" 2>/dev/null; then
  grep -v "^EXPENSE_MEMBER_SLUG=" "${ENV_FILE}" > "${ENV_FILE}.tmp"
  mv "${ENV_FILE}.tmp" "${ENV_FILE}"
fi
echo "EXPENSE_MEMBER_SLUG=${SLUG}" >> "${ENV_FILE}"

if grep -q "^EXPENSE_LOCALE=" "${ENV_FILE}" 2>/dev/null; then
  grep -v "^EXPENSE_LOCALE=" "${ENV_FILE}" > "${ENV_FILE}.tmp"
  mv "${ENV_FILE}.tmp" "${ENV_FILE}"
fi
echo "EXPENSE_LOCALE=${LOCALE}" >> "${ENV_FILE}"

INSTALL_QUIET=1 EXPENSE_LOCALE="${LOCALE}" "${ROOT}/scripts/apply-telegram-ux.sh" "${PROFILE_NAME}" >/dev/null 2>&1 || true

if [[ -z "${INSTALL_QUIET}" ]]; then
  echo "==> Profile ready: ${PROFILE_NAME} (atajo: ${SLUG})"
  echo "    Path: ${PROFILE_DIR}"
  echo "Next: hermes -p ${PROFILE_NAME} setup · ${SLUG} gateway setup · gateway start"
fi
