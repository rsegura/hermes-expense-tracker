"""Household locale (en | es) resolution and persistence."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .runtime import MCP_DIR


def _locale_file() -> Path:
    sys.path.insert(0, str(MCP_DIR))
    from expense_tracker.paths import locale_file

    return locale_file()


def resolve_expense_locale(*, required: bool = True) -> str | None:
    locale = os.environ.get("EXPENSE_LOCALE", "").strip()
    path = _locale_file()
    if not locale and path.exists():
        locale = path.read_text(encoding="utf-8").strip()
    if locale in ("en", "es"):
        return locale
    if required:
        print("EXPENSE_LOCALE is required (en or es). Set env or run ./install.sh", file=sys.stderr)
        return None
    return "es"


def save_household_locale(locale: str) -> None:
    sys.path.insert(0, str(MCP_DIR))
    from expense_tracker.paths import expense_tracker_dir

    expense_tracker_dir().mkdir(parents=True, exist_ok=True)
    _locale_file().write_text(f"{locale}\n", encoding="utf-8")
