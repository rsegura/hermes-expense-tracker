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


if __name__ == "__main__":
    unittest.main()
