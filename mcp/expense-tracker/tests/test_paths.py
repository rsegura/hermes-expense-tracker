"""Tests for Hermes-aligned data paths."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from expense_tracker.paths import (
    currency_file,
    db_path_override_file,
    default_db_path,
    expense_tracker_dir,
    hermes_home,
    is_legacy_db_path,
    locale_file,
    resolve_db_path,
)


class PathsTests(unittest.TestCase):
    def test_default_layout_under_hermes_home(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "user"
            hermes = home / ".hermes"
            os.environ["HERMES_HOME"] = str(hermes)
            try:
                self.assertEqual(hermes_home(), hermes.resolve())
                self.assertEqual(expense_tracker_dir(), (hermes / "expense-tracker").resolve())
                self.assertEqual(default_db_path(), (hermes / "expense-tracker" / "expenses.db").resolve())
                self.assertEqual(locale_file(), (hermes / "expense-tracker" / "locale").resolve())
                self.assertEqual(currency_file(), (hermes / "expense-tracker" / "currency").resolve())
                self.assertEqual(db_path_override_file(), (hermes / "expense-tracker" / "db-path").resolve())
            finally:
                os.environ.pop("HERMES_HOME", None)

    def test_legacy_path_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "user"
            home.mkdir()
            legacy = home / "expenses" / "data" / "expenses.db"
            self.assertTrue(is_legacy_db_path(legacy))
            hermes_db = home / ".hermes" / "expense-tracker" / "expenses.db"
            self.assertFalse(is_legacy_db_path(hermes_db))

    def test_resolve_skips_legacy_override_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "user"
            hermes = home / ".hermes" / "expense-tracker"
            hermes.mkdir(parents=True)
            os.environ["HERMES_HOME"] = str(home / ".hermes")
            os.environ.pop("EXPENSE_DB_PATH", None)
            (hermes / "db-path").write_text(str(home / "expenses" / "data" / "expenses.db") + "\n")
            try:
                self.assertEqual(resolve_db_path(), (hermes / "expenses.db").resolve())
            finally:
                os.environ.pop("HERMES_HOME", None)
                os.environ.pop("EXPENSE_DB_PATH", None)


if __name__ == "__main__":
    unittest.main()
