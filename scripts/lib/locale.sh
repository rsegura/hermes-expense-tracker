#!/usr/bin/env bash
# Resolve household locale (en | es) for installs and updates.

resolve_expense_locale() {
  local locale="${EXPENSE_LOCALE:-}"
  local locale_file="${HOME}/expenses/locale"

  if [[ -z "${locale}" && -f "${locale_file}" ]]; then
    locale="$(tr -d '[:space:]' < "${locale_file}")"
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
  mkdir -p "${HOME}/expenses"
  printf '%s\n' "${locale}" > "${HOME}/expenses/locale"
}
