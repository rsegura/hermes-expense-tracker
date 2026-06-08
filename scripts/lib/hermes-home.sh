#!/usr/bin/env bash
# Hermes user data directory (same as Hermes Agent: ~/.hermes or $HERMES_HOME).

resolve_hermes_home() {
  local home="${HERMES_HOME:-${HOME}/.hermes}"
  # shellcheck disable=SC2088
  home="${home/#\~/${HOME}}"
  echo "${home}"
}

expense_tracker_data_dir() {
  echo "$(resolve_hermes_home)/expense-tracker"
}
