"""Shared paths for expense-tracker data (aligned with Hermes Agent layout)."""

from __future__ import annotations

import os
from pathlib import Path


def hermes_home() -> Path:
    raw = os.environ.get("HERMES_HOME", "").strip()
    if raw:
        return Path(os.path.expanduser(raw)).resolve()
    return (Path.home() / ".hermes").resolve()


def expense_tracker_dir() -> Path:
    return hermes_home() / "expense-tracker"


def default_db_path() -> Path:
    return expense_tracker_dir() / "expenses.db"


def db_path_override_file() -> Path:
    return expense_tracker_dir() / "db-path"


def locale_file() -> Path:
    return expense_tracker_dir() / "locale"


def is_legacy_db_path(path: Path) -> bool:
    """Ignore pre-move defaults under ~/expenses/ (not ~/.hermes/expense-tracker/)."""
    parts = path.expanduser().resolve().parts
    if len(parts) >= 3 and parts[-3:] == ("expenses", "data", "expenses.db"):
        return True
    if len(parts) >= 2 and parts[-2:] in (("expenses", "db-path"), ("expenses", "locale")):
        return True
    return False


def resolve_db_path(*, honor_env: bool = True) -> Path:
    """Resolve shared DB path: env → ~/.hermes/expense-tracker/db-path → default."""
    raw = os.environ.get("EXPENSE_DB_PATH", "").strip() if honor_env else ""
    if not raw and db_path_override_file().exists():
        raw = db_path_override_file().read_text(encoding="utf-8").strip()
    if raw:
        candidate = Path(os.path.expanduser(raw)).resolve()
        if not is_legacy_db_path(candidate):
            return candidate
    return default_db_path()
