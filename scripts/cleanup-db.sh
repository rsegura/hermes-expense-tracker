#!/usr/bin/env bash
# Remove mistaken duplicate persons (e.g. expense-johanna) and reassign expenses.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MCP_DIR="${ROOT}/mcp/expense-tracker"
VENV="${MCP_DIR}/.venv"
DB_PATH="${EXPENSE_DB_PATH:-${HOME}/expenses/data/expenses.db}"

if [[ ! -x "${VENV}/bin/python" ]]; then
  echo "Run ./bootstrap.sh first." >&2
  exit 1
fi

export EXPENSE_DB_PATH="${DB_PATH}"
export PYTHONPATH="${MCP_DIR}:${PYTHONPATH:-}"

"${VENV}/bin/python" - <<'PY'
from expense_tracker import repositories as repo
from expense_tracker.db import init_db

init_db(seed=False)

BAD_SLUGS = ["expense-johanna", "expense-emanuel"]
persons = {p["slug"]: p for p in repo.list_persons()}

for bad in BAD_SLUGS:
    if bad not in persons:
        continue
    bad_person = persons[bad]
    target_slug = bad.removeprefix("expense-")
    if target_slug not in persons:
        print(f"skip {bad}: no target person '{target_slug}'")
        continue
    target = persons[target_slug]
    expenses = repo.list_expenses(paid_by=bad, limit=500).get("items", [])
    for exp in expenses:
        repo.update_expense(
            exp["id"],
            paid_by=target_slug,
            allocations=[{"person": target_slug, "percentage": 100}],
        )
        print(f"reassigned expense {exp['id']} paid_by {bad} -> {target_slug}")
    try:
        repo.delete_person(bad)
        print(f"deleted duplicate person: {bad}")
    except repo.ValidationError as exc:
        print(f"could not delete {bad}: {exc}")

print("done")
PY
