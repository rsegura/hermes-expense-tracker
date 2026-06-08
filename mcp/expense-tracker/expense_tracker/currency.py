"""Household default currency (ISO 4217) resolution."""

from __future__ import annotations

import os
import re

from .paths import currency_file

_FALLBACK = "USD"
_ISO4217 = re.compile(r"^[A-Z]{3}$")

# Prefix/suffix hints for report formatting (fallback: "1,234 CUR")
_SYMBOL_PREFIX: dict[str, str] = {
    "USD": "$",
    "ARS": "$",
    "MXN": "$",
    "BRL": "R$",
    "CLP": "$",
    "COP": "$",
    "EUR": "€",
    "GBP": "£",
}


def normalize_currency(code: str) -> str:
    cur = code.strip().upper()
    if not _ISO4217.fullmatch(cur):
        raise ValueError(f"Invalid currency code: {code!r} (expected 3-letter ISO 4217, e.g. USD)")
    return cur


def default_currency() -> str:
    raw = os.environ.get("EXPENSE_DEFAULT_CURRENCY", "").strip().upper()
    if raw and _ISO4217.fullmatch(raw):
        return raw
    path = currency_file()
    if path.exists():
        stored = path.read_text(encoding="utf-8").strip().upper()
        if _ISO4217.fullmatch(stored):
            return stored
    return _FALLBACK


def format_money(amount: float, currency: str | None = None) -> str:
    from . import i18n

    cur = normalize_currency(currency) if currency else default_currency()
    rounded = int(round(amount))
    if i18n.get_locale() == "en":
        text = f"{rounded:,}"
    else:
        text = f"{rounded:,}".replace(",", ".")
    prefix = _SYMBOL_PREFIX.get(cur)
    if prefix:
        return f"{prefix}{text}"
    return f"{text} {cur}"
