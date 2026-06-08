#!/usr/bin/env bash
# Launcher — UI in scripts/install_wizard.py (Rich TUI, cross-platform)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_UNIX="${ROOT}/mcp/expense-tracker/.venv/bin/python"
VENV_WIN="${ROOT}/mcp/expense-tracker/.venv/Scripts/python.exe"
WIZARD="${ROOT}/scripts/install_wizard.py"
PY="$(command -v python3 || command -v python || true)"

if [[ -z "${PY}" ]]; then
  echo "python3 or python is required" >&2
  exit 1
fi

if [[ -x "${VENV_UNIX}" ]]; then
  VENV_PY="${VENV_UNIX}"
elif [[ -x "${VENV_WIN}" ]]; then
  VENV_PY="${VENV_WIN}"
else
  QUIET=1 BOOTSTRAP_DB=0 "${PY}" "${ROOT}/scripts/bootstrap.py"
  if [[ -x "${VENV_UNIX}" ]]; then
    VENV_PY="${VENV_UNIX}"
  elif [[ -x "${VENV_WIN}" ]]; then
    VENV_PY="${VENV_WIN}"
  else
    echo "MCP venv missing after bootstrap." >&2
    exit 1
  fi
fi

exec "${VENV_PY}" "${WIZARD}"
