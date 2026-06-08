#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$(command -v python3 || command -v python || true)"
[[ -n "${PY}" ]] || { echo "python3 or python is required" >&2; exit 1; }
exec "${PY}" "${ROOT}/scripts/bootstrap.py" "$@"
