#!/usr/bin/env bash
# Resolve household locale (en | es) for installs and updates.

# shellcheck source=scripts/lib/hermes-home.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/hermes-home.sh"

LOCALE_FILE="$(expense_tracker_data_dir)/locale"

resolve_expense_locale() {
  local locale="${EXPENSE_LOCALE:-}"

  if [[ -z "${locale}" && -f "${LOCALE_FILE}" ]]; then
    locale="$(tr -d '[:space:]' < "${LOCALE_FILE}")"
  fi

  case "${locale}" in
    en|es) echo "${locale}" ;;
    "")
      echo "EXPENSE_LOCALE is required (en or es). Set env or run ./install.sh" >&2
      return 1
      ;;
    *)
      echo "Invalid EXPENSE_LOCALE: ${locale} (use en or es)" >&2
      return 1
      ;;
  esac
}

save_household_locale() {
  local locale="$1"
  mkdir -p "$(expense_tracker_data_dir)"
  printf '%s\n' "${locale}" > "${LOCALE_FILE}"
}
