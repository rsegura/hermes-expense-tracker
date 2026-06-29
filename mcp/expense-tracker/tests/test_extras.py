from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from expense_tracker import repositories as repo
from expense_tracker.db import init_db
import server


class ExtraFeaturesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["EXPENSE_DB_PATH"] = str(Path(self.tmp.name) / "test.db")
        init_db(seed="test")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_compare_months(self) -> None:
        repo.add_expense(
            expense_date="2026-05-10",
            description="May",
            amount=1000,
            category="comida",
            paid_by="alice",
        )
        repo.add_expense(
            expense_date="2026-06-10",
            description="June",
            amount=3000,
            category="comida",
            paid_by="alice",
        )
        result = repo.compare_months(6, 5, year_a=2026, year_b=2026)
        self.assertEqual(result["period_a"]["total_amount"], 3000)
        self.assertEqual(result["period_b"]["total_amount"], 1000)
        self.assertEqual(result["delta_amount"], -2000)

    def test_top_expenses(self) -> None:
        repo.add_expense(
            expense_date="2026-06-01",
            description="Small",
            amount=100,
            category="comida",
            paid_by="alice",
        )
        repo.add_expense(
            expense_date="2026-06-02",
            description="Big",
            amount=9000,
            category="comida",
            paid_by="bob",
        )
        top = repo.top_expenses(year=2026, month=6, limit=1)
        self.assertEqual(len(top["items"]), 1)
        self.assertEqual(top["items"][0]["amount"], 9000)

    def test_export_expenses_csv_and_json(self) -> None:
        repo.add_expense(
            expense_date="2026-06-05",
            description="Export me",
            amount=500,
            category="transporte",
            paid_by="alice",
        )
        csv_export = repo.export_expenses("csv")
        self.assertIn("Export me", csv_export["content"])
        self.assertEqual(csv_export["row_count"], 1)
        json_export = repo.export_expenses("json")
        payload = json.loads(json_export["content"])
        self.assertEqual(payload[0]["description"], "Export me")

    def test_category_budgets_and_alerts(self) -> None:
        repo.set_category_budget("comida", monthly_amount=1000, alert_threshold_pct=80)
        repo.add_expense(
            expense_date="2026-06-05",
            description="Over budget",
            amount=900,
            category="comida",
            paid_by="alice",
        )
        status = repo.budget_status(2026, 6)
        self.assertEqual(len(status["items"]), 1)
        self.assertGreaterEqual(status["items"][0]["percent_used"], 80)
        self.assertTrue(status["alert_count"] >= 1)
        alerts = repo.budget_status(2026, 6, alerts_only=True)
        self.assertEqual(len(alerts["items"]), 1)

    def test_e2e_compare_and_budget_tools(self) -> None:
        repo.add_expense(
            expense_date="2026-06-15",
            description="E2E",
            amount=2000,
            category="supermercado",
            paid_by="alice",
        )
        raw = server.compare_months(month_a=6, month_b=5, year_a=2026, year_b=2026)
        payload = json.loads(raw)
        self.assertTrue(payload["ok"])
        raw = server.set_category_budget(category="supermercado", monthly_amount=5000)
        self.assertTrue(json.loads(raw)["ok"])
        raw = server.budget_status(year=2026, month=6)
        self.assertTrue(json.loads(raw)["ok"])


class RecurringSchemaMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"
        os.environ["EXPENSE_DB_PATH"] = str(self.db_path)
        init_db(seed="test")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_recurring_tables_and_provenance_column_exist(self) -> None:
        from expense_tracker.db import connect
        with connect() as conn:
            tables = {
                r["name"]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            self.assertIn("recurring_expenses", tables)
            self.assertIn("recurring_allocations", tables)
            cols = {r["name"] for r in conn.execute("PRAGMA table_info(expenses)").fetchall()}
            self.assertIn("recurring_id", cols)

    def test_migration_recreates_recurring_objects_on_existing_db(self) -> None:
        from expense_tracker.db import connect
        from expense_tracker.migrations import run_migrations
        # Simulate an older DB that predates the recurring feature.
        with connect() as conn:
            conn.execute("DROP TABLE recurring_allocations")
            conn.execute("DROP TABLE recurring_expenses")
            conn.commit()
        run_migrations()
        with connect() as conn:
            tables = {
                r["name"]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            self.assertIn("recurring_expenses", tables)
            self.assertIn("recurring_allocations", tables)


if __name__ == "__main__":
    unittest.main()
