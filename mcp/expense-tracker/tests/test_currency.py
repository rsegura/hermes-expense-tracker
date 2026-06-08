"""Tests for household default currency."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from expense_tracker.currency import default_currency, format_money, normalize_currency
from expense_tracker.paths import currency_file


class CurrencyTests(unittest.TestCase):
    def test_normalize_accepts_iso4217(self) -> None:
        self.assertEqual(normalize_currency("usd"), "USD")
        self.assertEqual(normalize_currency(" EUR "), "EUR")

    def test_normalize_rejects_invalid(self) -> None:
        with self.assertRaises(ValueError):
            normalize_currency("US")
        with self.assertRaises(ValueError):
            normalize_currency("USDD")

    def test_default_from_env_then_file_then_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / ".hermes"
            os.environ["HERMES_HOME"] = str(home)
            os.environ["EXPENSE_DEFAULT_CURRENCY"] = "EUR"
            try:
                self.assertEqual(default_currency(), "EUR")
            finally:
                os.environ.pop("HERMES_HOME", None)
                os.environ.pop("EXPENSE_DEFAULT_CURRENCY", None)

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / ".hermes"
            tracker = home / "expense-tracker"
            tracker.mkdir(parents=True)
            os.environ["HERMES_HOME"] = str(home)
            os.environ.pop("EXPENSE_DEFAULT_CURRENCY", None)
            currency_file().write_text("GBP\n", encoding="utf-8")
            try:
                self.assertEqual(default_currency(), "GBP")
            finally:
                os.environ.pop("HERMES_HOME", None)

        os.environ.pop("EXPENSE_DEFAULT_CURRENCY", None)
        os.environ.pop("HERMES_HOME", None)
        self.assertEqual(default_currency(), "USD")

    def test_format_money_uses_symbol_map(self) -> None:
        os.environ["EXPENSE_DEFAULT_CURRENCY"] = "USD"
        try:
            self.assertEqual(format_money(1500), "$1,500")
            self.assertEqual(format_money(1500, "EUR"), "€1,500")
        finally:
            os.environ.pop("EXPENSE_DEFAULT_CURRENCY", None)


if __name__ == "__main__":
    unittest.main()
