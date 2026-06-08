"""Household default currency (ISO 4217) resolution and persistence."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .runtime import MCP_DIR


def _currency_file() -> Path:
    sys.path.insert(0, str(MCP_DIR))
    from expense_tracker.paths import currency_file

    return currency_file()


def _normalize(code: str) -> str:
    sys.path.insert(0, str(MCP_DIR))
    from expense_tracker.currency import normalize_currency

    return normalize_currency(code)


def resolve_expense_currency(*, required: bool = False) -> str | None:
    raw = os.environ.get("EXPENSE_DEFAULT_CURRENCY", "").strip()
    path = _currency_file()
    if not raw and path.exists():
        raw = path.read_text(encoding="utf-8").strip()
    if raw:
        try:
            return _normalize(raw)
        except ValueError:
            print(f"Invalid EXPENSE_DEFAULT_CURRENCY: {raw!r}", file=sys.stderr)
            return None
    if required:
        print("EXPENSE_DEFAULT_CURRENCY is required. Set env or run ./install.sh", file=sys.stderr)
        return None
    return "USD"


def save_household_currency(code: str) -> None:
    normalized = _normalize(code)
    sys.path.insert(0, str(MCP_DIR))
    from expense_tracker.paths import expense_tracker_dir

    expense_tracker_dir().mkdir(parents=True, exist_ok=True)
    _currency_file().write_text(f"{normalized}\n", encoding="utf-8")
