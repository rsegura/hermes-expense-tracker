from __future__ import annotations

import json
import os
import tempfile
import unittest

from expense_tracker.db import init_db
import server


class E2EValidation(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["EXPENSE_DB_PATH"] = f"{self.tmp.name}/shared.db"
        init_db(seed="test")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _call(self, fn, **kwargs) -> dict:
        raw = fn(**kwargs)
        payload = json.loads(raw)
        self.assertTrue(payload["ok"], payload)
        return payload["data"]

    def test_allocation_load_and_reports(self) -> None:
        self._call(
            server.add_expense,
            expense_date="2026-06-05",
            description="Supermercado",
            amount=120000,
            category="supermercado",
            paid_by="alice",
            project="hogar",
            allocations=[
                {"person": "alice", "percentage": 50},
                {"person": "bob", "percentage": 50},
            ],
        )
        monthly = self._call(server.monthly_summary, year=2026, month=6)
        self.assertGreaterEqual(monthly["total_amount"], 120000)
        self.assertTrue(monthly["by_person"])
        filtered = self._call(server.monthly_summary, year=2026, month=6, project="hogar")
        self.assertGreaterEqual(filtered["total_amount"], 120000)
        project = self._call(server.project_summary, project="hogar")
        self.assertGreaterEqual(project["total_amount"], 120000)
        alice = self._call(server.person_summary, person="alice")
        self.assertEqual(alice["paid_total"], 120000)
        self.assertEqual(alice["attributed_total"], 60000)
        self.assertTrue(alice["by_category"])

    def test_invalid_allocation_rejected(self) -> None:
        raw = server.add_expense(
            expense_date="2026-06-05",
            description="Bad split",
            amount=100,
            category="comida",
            paid_by="alice",
            allocations=[{"person": "alice", "percentage": 30}],
        )
        payload = json.loads(raw)
        self.assertFalse(payload["ok"])

    def test_shared_db_visibility(self) -> None:
        created = self._call(
            server.add_expense,
            expense_date="2026-06-06",
            description="Farmacia",
            amount=8000,
            category="farmacia",
            paid_by="bob",
        )
        listed = self._call(server.list_expenses)
        ids = [item["id"] for item in listed["items"]]
        self.assertIn(created["id"], ids)
        self.assertGreaterEqual(listed["total_count"], 1)

    def test_list_expenses_allocated_to(self) -> None:
        self._call(
            server.add_expense,
            expense_date="2026-06-07",
            description="Split",
            amount=4000,
            category="comida",
            paid_by="bob",
            allocations=[
                {"person": "alice", "percentage": 50},
                {"person": "bob", "percentage": 50},
            ],
        )
        page = self._call(server.list_expenses, allocated_to="alice")
        self.assertGreaterEqual(page["total_count"], 1)

    def test_search_with_filters(self) -> None:
        self._call(
            server.add_expense,
            expense_date="2026-06-08",
            description="Jumbo market",
            amount=9000,
            category="supermercado",
            paid_by="alice",
        )
        result = self._call(
            server.search_expenses,
            query="Jumbo",
            start_date="2026-06-01",
            end_date="2026-06-30",
            min_amount=5000,
        )
        self.assertEqual(result["total_count"], 1)

    def test_delete_project_tool(self) -> None:
        project = self._call(server.create_project, name="Temp Project", owner="alice")
        self._call(
            server.add_expense,
            expense_date="2026-06-09",
            description="Temp",
            amount=500,
            category="comida",
            paid_by="alice",
            project=project["slug"],
        )
        deleted = self._call(server.delete_project, project_ref=project["slug"], force=True)
        self.assertTrue(deleted["deleted"])

    def test_create_person_without_profile(self) -> None:
        person = self._call(server.create_person, display_name="Tía Rosa", aliases=["rosa"])
        persons = self._call(server.list_persons)
        self.assertTrue(any(p["slug"] == person["slug"] for p in persons))

    def test_health_check_tool(self) -> None:
        result = self._call(server.health_check)
        self.assertEqual(result["status"], "ok")
        self.assertGreaterEqual(result["counts"]["categories"], 1)


if __name__ == "__main__":
    unittest.main()
