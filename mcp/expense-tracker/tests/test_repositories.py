from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from expense_tracker import repositories as repo
from expense_tracker.db import init_db


class ExpenseTrackerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"
        os.environ["EXPENSE_DB_PATH"] = str(self.db_path)
        init_db(seed="test")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_health_check(self) -> None:
        result = repo.health_check()
        self.assertEqual(result["status"], "ok")
        self.assertGreaterEqual(result["counts"]["persons"], 2)

    def test_add_expense_with_allocations(self) -> None:
        expense = repo.add_expense(
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
        self.assertEqual(expense["amount"], 120000)
        self.assertEqual(len(expense["allocations"]), 2)
        total_pct = sum(a["percentage"] for a in expense["allocations"])
        self.assertAlmostEqual(total_pct, 100.0)

    def test_allocation_validation_rejects_invalid_sum(self) -> None:
        with self.assertRaises(repo.ValidationError):
            repo.add_expense(
                expense_date="2026-06-05",
                description="Test",
                amount=100,
                category="comida",
                paid_by="alice",
                allocations=[
                    {"person": "alice", "percentage": 40},
                    {"person": "bob", "percentage": 40},
                ],
            )

    def test_person_summary_paid_vs_attributed_with_breakdowns(self) -> None:
        repo.add_expense(
            expense_date="2026-06-05",
            description="Cena",
            amount=10000,
            category="restaurante",
            paid_by="alice",
            project="hogar",
            allocations=[
                {"person": "alice", "percentage": 50},
                {"person": "bob", "percentage": 50},
            ],
        )
        summary = repo.person_summary("alice")
        self.assertEqual(summary["paid_total"], 10000)
        self.assertEqual(summary["attributed_total"], 5000)
        self.assertTrue(any(row["category"] == "Restaurante" for row in summary["by_category"]))
        self.assertTrue(any(row["project"] == "Hogar" for row in summary["by_project"]))

    def test_monthly_summary(self) -> None:
        repo.add_expense(
            expense_date="2026-06-10",
            description="Farmacia",
            amount=5000,
            category="farmacia",
            paid_by="bob",
        )
        summary = repo.monthly_summary(2026, 6)
        self.assertGreaterEqual(summary["total_amount"], 5000)
        self.assertGreaterEqual(summary["expense_count"], 1)
        self.assertTrue(summary["by_person"])

    def test_monthly_summary_filtered_by_project(self) -> None:
        repo.add_expense(
            expense_date="2026-06-10",
            description="Hogar only",
            amount=3000,
            category="servicios",
            paid_by="alice",
            project="hogar",
        )
        repo.add_expense(
            expense_date="2026-06-11",
            description="Other",
            amount=7000,
            category="comida",
            paid_by="bob",
        )
        summary = repo.monthly_summary(2026, 6, project="hogar")
        self.assertEqual(summary["total_amount"], 3000)

    def test_yearly_summary_with_category_and_project_breakdown(self) -> None:
        repo.add_expense(
            expense_date="2026-03-01",
            description="Year test",
            amount=2000,
            category="transporte",
            paid_by="alice",
            project="hogar",
        )
        summary = repo.yearly_summary(2026)
        self.assertGreaterEqual(summary["total_amount"], 2000)
        self.assertTrue(summary["by_category"])
        self.assertTrue(summary["by_project"])

    def test_category_summary_breakdowns(self) -> None:
        repo.add_expense(
            expense_date="2026-06-01",
            description="Cat A",
            amount=1000,
            category="comida",
            paid_by="alice",
            project="hogar",
        )
        repo.add_expense(
            expense_date="2026-07-01",
            description="Cat B",
            amount=2000,
            category="comida",
            paid_by="bob",
        )
        summary = repo.category_summary("comida")
        self.assertEqual(summary["total_amount"], 3000)
        self.assertEqual(len(summary["by_month"]), 2)
        self.assertTrue(summary["by_project"])

    def test_list_expenses_allocated_to_and_pagination(self) -> None:
        repo.add_expense(
            expense_date="2026-06-05",
            description="Alice share",
            amount=1000,
            category="comida",
            paid_by="bob",
            allocations=[
                {"person": "alice", "percentage": 50},
                {"person": "bob", "percentage": 50},
            ],
        )
        page = repo.list_expenses(allocated_to="alice", limit=10, offset=0)
        self.assertEqual(page["total_count"], 1)
        self.assertEqual(len(page["items"]), 1)
        self.assertFalse(page["has_more"])

    def test_search_expenses_with_date_and_amount_filters(self) -> None:
        repo.add_expense(
            expense_date="2026-06-05",
            description="Coto express",
            amount=15000,
            category="supermercado",
            paid_by="alice",
        )
        result = repo.search_expenses(
            "Coto",
            start_date="2026-06-01",
            end_date="2026-06-30",
            min_amount=10000,
            max_amount=20000,
        )
        self.assertEqual(result["total_count"], 1)
        self.assertEqual(result["items"][0]["description"], "Coto express")

    def test_list_categories_includes_parent(self) -> None:
        parent = repo.create_category("Vivienda")
        child = repo.create_category("Expensas", parent_id=parent["id"])
        categories = repo.list_categories()
        match = next(c for c in categories if c["id"] == child["id"])
        self.assertEqual(match["parent_slug"], parent["slug"])

    def test_create_person(self) -> None:
        person = repo.create_person("Tía Rosa", aliases=["rosa"])
        self.assertEqual(person["display_name"], "Tía Rosa")
        persons = repo.list_persons()
        self.assertTrue(any(p["slug"] == person["slug"] for p in persons))

    def test_delete_project_force_unlinks_expenses(self) -> None:
        project = repo.create_project("Temporal", owner="alice")
        repo.add_expense(
            expense_date="2026-06-05",
            description="Linked",
            amount=100,
            category="comida",
            paid_by="alice",
            project=project["slug"],
        )
        with self.assertRaises(repo.ValidationError):
            repo.delete_project(project["slug"])
        deleted = repo.delete_project(project["slug"], force=True)
        self.assertEqual(deleted["expenses_unlinked"], 1)
        listed = repo.list_expenses()
        self.assertTrue(all(item["project"] is None for item in listed["items"] if item["description"] == "Linked"))

    def test_delete_category_with_reassign(self) -> None:
        source = repo.create_category("Old Cat")
        target = repo.create_category("New Cat")
        expense = repo.add_expense(
            expense_date="2026-06-05",
            description="Move me",
            amount=100,
            category=source["slug"],
            paid_by="alice",
        )
        repo.delete_category(source["slug"], reassign_to=target["slug"])
        updated = repo.list_expenses(category=target["slug"])
        self.assertEqual(updated["total_count"], 1)
        self.assertEqual(updated["items"][0]["id"], expense["id"])

    def test_delete_person_blocked_when_referenced(self) -> None:
        repo.add_expense(
            expense_date="2026-06-05",
            description="Blocks delete",
            amount=100,
            category="comida",
            paid_by="alice",
        )
        with self.assertRaises(repo.ValidationError):
            repo.delete_person("alice")

    def test_shared_visibility(self) -> None:
        first = repo.add_expense(
            expense_date="2026-06-05",
            description="Compartido",
            amount=3000,
            category="transporte",
            paid_by="bob",
        )
        listed = repo.list_expenses()
        ids = [item["id"] for item in listed["items"]]
        self.assertIn(first["id"], ids)


class ProjectMembershipTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"
        os.environ["EXPENSE_DB_PATH"] = str(self.db_path)
        os.environ.pop("EXPENSE_MEMBER_SLUG", None)
        init_db(seed="test")

    def tearDown(self) -> None:
        os.environ.pop("EXPENSE_MEMBER_SLUG", None)
        self.tmp.cleanup()

    def test_migration_backfills_hogar_members(self) -> None:
        os.environ["EXPENSE_MEMBER_SLUG"] = "alice"
        projects = repo.list_projects()
        hogar = next(item for item in projects if item["slug"] == "hogar")
        self.assertGreaterEqual(hogar["member_count"], 2)
        self.assertEqual(hogar["role"], "owner")

    def test_personal_project_only_visible_to_owner(self) -> None:
        os.environ["EXPENSE_MEMBER_SLUG"] = "alice"
        repo.create_project("Personal", slug="personal")

        self.assertTrue(any(item["slug"] == "personal" for item in repo.list_projects()))

        os.environ["EXPENSE_MEMBER_SLUG"] = "bob"
        self.assertFalse(any(item["slug"] == "personal" for item in repo.list_projects()))

    def test_shared_project_visible_to_invited_member(self) -> None:
        os.environ["EXPENSE_MEMBER_SLUG"] = "alice"
        repo.create_project("Casamiento", slug="casamiento", members=["bob"])

        os.environ["EXPENSE_MEMBER_SLUG"] = "bob"
        slugs = {item["slug"] for item in repo.list_projects()}
        self.assertIn("casamiento", slugs)
        member_slugs = {item["slug"] for item in repo.list_project_members("casamiento")}
        self.assertEqual(member_slugs, {"alice", "bob"})

    def test_non_owner_cannot_manage_members(self) -> None:
        os.environ["EXPENSE_MEMBER_SLUG"] = "alice"
        repo.create_project("Casamiento", slug="casamiento", members=["bob"])

        os.environ["EXPENSE_MEMBER_SLUG"] = "bob"
        with self.assertRaises(repo.ValidationError):
            repo.add_project_member("casamiento", "alice")
        with self.assertRaises(repo.ValidationError):
            repo.delete_project("casamiento")

    def test_non_member_cannot_add_expense_to_project(self) -> None:
        os.environ["EXPENSE_MEMBER_SLUG"] = "alice"
        repo.create_project("Secret", slug="secret")

        os.environ["EXPENSE_MEMBER_SLUG"] = "bob"
        with self.assertRaises(repo.ValidationError):
            repo.add_expense(
                expense_date="2026-06-05",
                description="Blocked",
                amount=1000,
                category="comida",
                paid_by="bob",
                project="secret",
            )

    def test_list_expenses_hides_other_members_project(self) -> None:
        os.environ["EXPENSE_MEMBER_SLUG"] = "alice"
        repo.create_project("Secret", slug="secret")
        hidden = repo.add_expense(
            expense_date="2026-06-05",
            description="Hidden",
            amount=1000,
            category="comida",
            paid_by="alice",
            project="secret",
        )

        os.environ["EXPENSE_MEMBER_SLUG"] = "bob"
        listed = repo.list_expenses()
        ids = [item["id"] for item in listed["items"]]
        self.assertNotIn(hidden["id"], ids)

    def test_monthly_summary_hides_other_members_project(self) -> None:
        os.environ["EXPENSE_MEMBER_SLUG"] = "alice"
        repo.create_project("Secret", slug="secret")
        repo.add_expense(
            expense_date="2026-06-05",
            description="Hidden",
            amount=5000,
            category="comida",
            paid_by="alice",
            project="secret",
        )

        os.environ["EXPENSE_MEMBER_SLUG"] = "bob"
        summary = repo.monthly_summary(2026, 6)
        project_slugs = {row["project_slug"] for row in summary["by_project"] if row["project_slug"]}
        self.assertNotIn("secret", project_slugs)

    def test_create_project_requires_caller_or_owner(self) -> None:
        with self.assertRaises(repo.ValidationError):
            repo.create_project("No caller")


class RecurringDateMathTests(unittest.TestCase):
    def test_weekly_advance(self) -> None:
        self.assertEqual(
            repo._advance_due_date("2026-06-01", "weekly", 2, None, None),
            "2026-06-15",
        )

    def test_monthly_advance_clamps_end_of_month(self) -> None:
        # Jan 31 + 1 month -> Feb 28 (2026 is not a leap year)
        self.assertEqual(
            repo._advance_due_date("2026-01-31", "monthly", 1, 31, None),
            "2026-02-28",
        )

    def test_monthly_advance_preserves_anchor_after_clamp(self) -> None:
        # From the clamped Feb 28, next month should return to day 31 (March)
        self.assertEqual(
            repo._advance_due_date("2026-02-28", "monthly", 1, 31, None),
            "2026-03-31",
        )

    def test_yearly_advance_honors_anchor_month_and_day(self) -> None:
        # Feb 29 (leap) + 1 year -> Feb 28 (2025 not a leap year), anchor day clamped
        self.assertEqual(
            repo._advance_due_date("2024-02-29", "yearly", 1, 29, 2),
            "2025-02-28",
        )

    def test_unknown_frequency_raises(self) -> None:
        with self.assertRaises(repo.ValidationError):
            repo._advance_due_date("2026-01-01", "daily", 1, None, None)

    def test_monthly_advance_multi_interval_clamps(self) -> None:
        # Jan 31 + 3 months -> April 30 (April has 30 days), anchor day 31 preserved
        self.assertEqual(
            repo._advance_due_date("2026-01-31", "monthly", 3, 31, None),
            "2026-04-30",
        )


class RecurringRepoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"
        os.environ["EXPENSE_DB_PATH"] = str(self.db_path)
        init_db(seed="test")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _make_rent(self, **overrides):
        params = dict(
            description="Alquiler",
            category="comida",
            paid_by="alice",
            frequency="monthly",
            start_date="2026-01-05",
            suggested_amount=100000,
        )
        params.update(overrides)
        return repo.create_recurring_expense(**params)

    def test_create_sets_next_due_to_start_and_default_allocation(self) -> None:
        rec = self._make_rent()
        self.assertEqual(rec["next_due_date"], "2026-01-05")
        self.assertEqual(rec["frequency"], "monthly")
        self.assertEqual(rec["interval"], 1)
        self.assertEqual(rec["anchor_day"], 5)
        self.assertEqual(rec["anchor_month"], 1)  # start_date is 2026-01-05
        self.assertEqual(len(rec["allocations"]), 1)
        self.assertEqual(rec["allocations"][0]["person_slug"], "alice")
        self.assertAlmostEqual(rec["allocations"][0]["percentage"], 100.0)

    def test_create_with_split_allocations(self) -> None:
        rec = self._make_rent(
            allocations=[
                {"person": "alice", "percentage": 60},
                {"person": "bob", "percentage": 40},
            ],
        )
        self.assertEqual(len(rec["allocations"]), 2)

    def test_create_rejects_bad_frequency(self) -> None:
        with self.assertRaises(repo.ValidationError):
            self._make_rent(frequency="daily")

    def test_list_returns_created_templates(self) -> None:
        self._make_rent()
        self._make_rent(description="Netflix", suggested_amount=5000)
        items = repo.list_recurring_expenses()
        self.assertEqual(len(items), 2)
        for it in items:
            self.assertIn("next_due_date", it)
            self.assertIsInstance(it["allocations"], list)
            self.assertGreater(len(it["allocations"]), 0)
        # Both have the same start_date, so ordering falls back to id (insertion order)
        self.assertEqual(items[0]["description"], "Alquiler")
        self.assertEqual(items[1]["description"], "Netflix")

    def test_update_changes_fields_and_recomputes_due_on_cadence_change(self) -> None:
        rec = self._make_rent()
        updated = repo.update_recurring_expense(
            rec["id"], suggested_amount=120000, frequency="yearly", anchor_month=1, anchor_day=5
        )
        self.assertEqual(updated["suggested_amount"], 120000)
        self.assertEqual(updated["frequency"], "yearly")
        # next_due_date recomputed from start_date with new cadence anchor
        self.assertEqual(updated["next_due_date"], "2026-01-05")

    def test_update_replaces_allocations(self) -> None:
        rec = self._make_rent()
        updated = repo.update_recurring_expense(
            rec["id"],
            allocations=[
                {"person": "alice", "percentage": 30},
                {"person": "bob", "percentage": 70},
            ],
        )
        self.assertEqual(len(updated["allocations"]), 2)

    def test_delete_deactivates_when_referenced(self) -> None:
        from expense_tracker.db import connect
        rec = self._make_rent()
        # Simulate a generated expense referencing this template (via raw SQL).
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO expenses
                    (expense_date, description, amount, currency, category_id, paid_by_person_id, recurring_id)
                SELECT '2026-01-05', 'Alquiler', 100000, 'ARS', category_id, paid_by_person_id, id
                FROM recurring_expenses WHERE id = ?
                """,
                (rec["id"],),
            )
            conn.commit()
        result = repo.delete_recurring_expense(rec["id"])
        self.assertFalse(result["hard_deleted"])
        items = repo.list_recurring_expenses()
        self.assertEqual(items[0]["is_active"], 0)

    def test_delete_hard_when_unreferenced(self) -> None:
        rec = self._make_rent()
        result = repo.delete_recurring_expense(rec["id"])
        self.assertTrue(result["hard_deleted"])
        self.assertEqual(repo.list_recurring_expenses(), [])

    def test_update_nonexistent_raises(self) -> None:
        with self.assertRaises(repo.NotFoundError):
            repo.update_recurring_expense(99999, description="Ghost")

    def test_delete_nonexistent_raises(self) -> None:
        with self.assertRaises(repo.NotFoundError):
            repo.delete_recurring_expense(99999)

    def test_list_due_returns_only_active_and_due(self) -> None:
        # Due: start in the past
        self._make_rent(start_date="2020-01-05")
        # Not due: start in the far future
        self._make_rent(description="Future", start_date="2999-01-05")
        due = repo.list_due_recurring(today="2026-06-15")
        self.assertEqual(len(due), 1)
        self.assertEqual(due[0]["description"], "Alquiler")

    def test_list_due_excludes_inactive(self) -> None:
        rec = self._make_rent(start_date="2020-01-05")
        repo.update_recurring_expense(rec["id"], is_active=False)
        self.assertEqual(repo.list_due_recurring(today="2026-06-15"), [])


if __name__ == "__main__":
    unittest.main()
