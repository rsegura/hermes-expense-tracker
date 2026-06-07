#!/usr/bin/env bash
# Merge Telegram UX settings into an existing Hermes profile config.yaml.
# Does not touch model, API keys, or mcp_servers.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE="${1:-}"

if [[ -z "${PROFILE}" ]]; then
  echo "Usage: $0 <profile>" >&2
  echo "  profile: expense-<slug> or alias <slug>" >&2
  echo "Example: $0 expense-emanuel" >&2
  exit 1
fi

PROFILE_DIR="${HOME}/.hermes/profiles/${PROFILE}"
if [[ ! -d "${PROFILE_DIR}" ]]; then
  PROFILE_DIR="${HOME}/.hermes/profiles/expense-${PROFILE}"
fi
if [[ ! -d "${PROFILE_DIR}" ]]; then
  echo "Profile not found: ${PROFILE}" >&2
  exit 1
fi

CONFIG="${PROFILE_DIR}/config.yaml"
if [[ ! -f "${CONFIG}" ]]; then
  echo "Missing config: ${CONFIG}" >&2
  exit 1
fi

PROFILE_BASENAME="$(basename "${PROFILE_DIR}")"
MEMBER_SLUG="${PROFILE_BASENAME#expense-}"
if [[ "${MEMBER_SLUG}" == expense-* ]]; then
  MEMBER_SLUG=""
fi

LOCALE="${EXPENSE_LOCALE:-}"
if [[ -z "${LOCALE}" && -f "${PROFILE_DIR}/.env" ]]; then
  LOCALE="$(grep -E '^EXPENSE_LOCALE=' "${PROFILE_DIR}/.env" | tail -1 | cut -d= -f2- || true)"
fi
if [[ -z "${LOCALE}" && -f "${HOME}/expenses/locale" ]]; then
  LOCALE="$(tr -d '[:space:]' < "${HOME}/expenses/locale")"
fi
LOCALE="${LOCALE:-en}"

PYTHON=""
for candidate in \
  "${ROOT}/mcp/expense-tracker/.venv/bin/python" \
  "${HOME}/.hermes/hermes-agent/venv/bin/python" \
  "$(command -v python3 || true)"; do
  if [[ -n "${candidate}" && -x "${candidate}" ]]; then
    if "${candidate}" -c "import yaml" 2>/dev/null; then
      PYTHON="${candidate}"
      break
    fi
  fi
done

if [[ -z "${PYTHON}" ]]; then
  echo "Need python3 with PyYAML (run ./bootstrap.sh first)." >&2
  exit 1
fi

"${PYTHON}" - "${CONFIG}" "${MEMBER_SLUG}" "${LOCALE}" <<'PY'
import sys
from pathlib import Path

import yaml

config_path = Path(sys.argv[1])
member_slug = sys.argv[2].strip() if len(sys.argv) > 2 else ""
locale = sys.argv[3].strip() if len(sys.argv) > 3 else "en"
if locale not in {"en", "es"}:
    locale = "en"
data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

ux_display = {
    "tool_progress": "off",
    "interim_assistant_messages": False,
    "turn_completion_explainer": False,
    "language": locale,
    "platforms": {
        "telegram": {
            "tool_progress": "off",
            "streaming": True,
        }
    },
}

display = data.setdefault("display", {})
for key, value in ux_display.items():
    if key == "platforms":
        platforms = display.setdefault("platforms", {})
        tg = platforms.setdefault("telegram", {})
        tg.update(ux_display["platforms"]["telegram"])
    else:
        display[key] = value

data.setdefault("telegram", {})["reactions"] = True

toolsets = data.setdefault("platform_toolsets", {})
for platform in ("cli", "telegram"):
    current = toolsets.get(platform) or []
    if "mcp-expense-tracker" not in current:
        toolsets[platform] = [*current, "mcp-expense-tracker"]

if member_slug:
    mcp_servers = data.setdefault("mcp_servers", {})
    expense_server = mcp_servers.setdefault("expense-tracker", {})
    env = expense_server.setdefault("env", {})
    env["EXPENSE_MEMBER_SLUG"] = "${EXPENSE_MEMBER_SLUG}"
    env["EXPENSE_LOCALE"] = "${EXPENSE_LOCALE}"

config_path.write_text(
    yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
    encoding="utf-8",
)
print(f"✓ Telegram UX applied: {config_path}")
PY

if [[ -z "${INSTALL_QUIET:-}" ]]; then
  echo
  echo "Next:"
  echo "  hermes profile update ${PROFILE} -y          # skills (SOUL: ./add-member.sh)"
  echo "  hermes -p ${PROFILE} gateway restart"
fi
