from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from expense_tracker import reports
from expense_tracker import repositories as repo
from expense_tracker.db import init_db


class ReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"
        os.environ["EXPENSE_DB_PATH"] = str(self.db_path)
        os.environ.pop("EXPENSE_MEMBER_SLUG", None)
        os.environ["EXPENSE_LOCALE"] = "es"
        init_db(seed="test")
        repo.add_expense(
            expense_date="2026-06-05",
            description="Supermercado",
            amount=120000,
            category="supermercado",
            paid_by="alice",
            project="hogar",
        )
        repo.add_expense(
            expense_date="2026-06-10",
            description="Taxi",
            amount=15000,
            category="transporte",
            paid_by="bob",
            project="hogar",
        )

    def tearDown(self) -> None:
        os.environ.pop("EXPENSE_MEMBER_SLUG", None)
        os.environ.pop("EXPENSE_LOCALE", None)
        self.tmp.cleanup()

    def test_generate_report_month_markdown(self) -> None:
        result = reports.generate_report(period="month", year=2026, month=6)
        self.assertIn("Junio 2026", result["markdown"])
        self.assertGreater(result["total_amount"], 0)
        self.assertIn("Por categoría", result["markdown"])
        self.assertIn("█", result["markdown"])

    def test_generate_report_project(self) -> None:
        result = reports.generate_report(period="project", project="hogar")
        self.assertIn("Hogar", result["markdown"])
        self.assertEqual(result["expense_count"], 2)

    def test_export_expenses_to_file(self) -> None:
        result = reports.export_expenses_to_file(export_format="csv")
        path = Path(result["file_path"])
        self.assertTrue(path.exists())
        self.assertIn("Supermercado", path.read_text(encoding="utf-8"))

    def test_render_chart_by_category(self) -> None:
        result = reports.render_chart("by_category", year=2026, month=6)
        path = Path(result["file_path"])
        self.assertTrue(path.exists())
        self.assertGreater(path.stat().st_size, 1000)

    def test_render_chart_monthly_trend(self) -> None:
        result = reports.render_chart("monthly_trend", year=2026)
        self.assertTrue(Path(result["file_path"]).exists())

    def test_generate_report_month_english_locale(self) -> None:
        os.environ["EXPENSE_LOCALE"] = "en"
        result = reports.generate_report(period="month", year=2026, month=6)
        self.assertIn("June 2026", result["markdown"])
        self.assertIn("By category", result["markdown"])
        self.assertNotIn("Por categoría", result["markdown"])


if __name__ == "__main__":
    unittest.main()
