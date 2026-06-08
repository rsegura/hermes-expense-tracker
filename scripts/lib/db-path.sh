#!/usr/bin/env bash
# Resolve shared expense database path for installs and updates.

# shellcheck source=scripts/lib/hermes-home.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/hermes-home.sh"

EXPENSE_TRACKER_DIR="$(expense_tracker_data_dir)"
DEFAULT_EXPENSE_DB_PATH="${EXPENSE_TRACKER_DIR}/expenses.db"
DB_PATH_FILE="${EXPENSE_TRACKER_DIR}/db-path"

_is_legacy_db_path() {
  local path="$1"
  local home="${HOME}"
  case "${path}" in
    "${home}/expenses/data/expenses.db") return 0 ;;
    "${home}/expenses/"*) return 0 ;;
  esac
  return 1
}

resolve_expense_db_path() {
  local path="${EXPENSE_DB_PATH:-}"

  if [[ -z "${path}" && -f "${DB_PATH_FILE}" ]]; then
    path="$(tr -d '[:space:]' < "${DB_PATH_FILE}")"
    if _is_legacy_db_path "${path}"; then
      path=""
    fi
  fi

  if [[ -z "${path}" ]]; then
    path="${DEFAULT_EXPENSE_DB_PATH}"
  fi

  # shellcheck disable=SC2088
  path="${path/#\~/${HOME}}"
  echo "${path}"
}

save_household_db_path() {
  local path="$1"
  mkdir -p "${EXPENSE_TRACKER_DIR}"
  printf '%s\n' "${path}" > "${DB_PATH_FILE}"
}
