# Recurring Expenses & Receipt Capture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add household-wide recurring expense templates with lazy (on-demand) generation, plus receipt capture handled entirely by the agent's multimodal model.

**Architecture:** Recurring expenses are a new SQLite table (`recurring_expenses`) plus a child allocations table (`recurring_allocations`) mirroring the existing expense/allocation shape, with a provenance/idempotency column `expenses.recurring_id`. Generation is lazy: tools surface what is due (`next_due_date <= today`) and materialize one occurrence at a time into the existing `expenses` table. Receipt capture adds no backend — it is agent skill/SOUL behavior on top of the existing `add_expense` tool.

**Tech Stack:** Python 3.11+, FastMCP, SQLite (stdlib `sqlite3`), `unittest`. No new dependencies (`datetime` + `calendar` from stdlib).

---

## Conventions in this codebase (read before starting)

- Business logic lives in `mcp/expense-tracker/expense_tracker/repositories.py`. MCP tools in `mcp/expense-tracker/server.py` are thin wrappers returning JSON via `_ok()` / `_err()`.
- DB access: `from .db import connect`; `with connect() as conn:` (foreign keys are ON). Use `row_to_dict` / `rows_to_dicts` from `db.py`.
- Errors: raise `repo.ValidationError` (maps to `validation_error`) or `repo.NotFoundError` (maps to `not_found`).
- Allocations validate via `_validate_allocations(...)` and resolve refs via `_resolve_allocations(conn, allocations, paid_by_person_id)` (defaults to 100% to payer when `allocations` is None).
- Person/category/project refs resolve via `_get_person_by_ref`, `_get_category_by_ref`, `_get_accessible_project_by_ref`.
- Tests run from `mcp/expense-tracker/`: `.venv/bin/python -m unittest discover -s tests -v`. Tests set `EXPENSE_DB_PATH` to a temp file and call `init_db(seed="test")`. The test fixture (`tests/fixtures/seed-test.sql`) seeds persons `alice` and `bob`, categories such as `supermercado`/`comida`/`restaurante`, and project `hogar`.
- Migrations (`expense_tracker/migrations.py`) are idempotent using `_table_exists` / `_column_exists`, and `init_db` calls `run_migrations()` after applying `schema.sql`.

All commit messages in this plan end with the project's trailer:
```
Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
```

---

## File Structure

**Create:**
- (none — all logic extends existing files)

**Modify:**
- `mcp/expense-tracker/expense_tracker/schema.sql` — new tables + `expenses.recurring_id` for fresh installs.
- `mcp/expense-tracker/expense_tracker/migrations.py` — idempotent migration for existing DBs.
- `mcp/expense-tracker/expense_tracker/repositories.py` — date-math helper + 6 recurring functions.
- `mcp/expense-tracker/server.py` — 6 MCP tool wrappers.
- `mcp/expense-tracker/expense_tracker/i18n.py` — frequency labels.
- `mcp/expense-tracker/tests/test_repositories.py` — recurring repo tests + date-math tests.
- `mcp/expense-tracker/tests/test_e2e.py` — recurring end-to-end test.
- `mcp/expense-tracker/tests/test_extras.py` — migration test for `recurring_id`.
- `locales/en/skills/expense-tracker/SKILL.md`, `locales/es/skills/expense-tracker/SKILL.md` — receipts + recurring tool docs.
- `locales/en/SOUL.md`, `locales/es/SOUL.md` — receipt + recurring guidance.
- `README.md`, `docs/en/BRIEFING.md`, `docs/es/BRIEFING.md` — tool count 38 → 44, feature notes.
- `scripts/expense_cli/prereqs.py` — informational multimodal-model note.

---

## FEATURE A — Recurring expenses (backend)

### Task 1: Schema + migration for recurring tables

**Files:**
- Modify: `mcp/expense-tracker/expense_tracker/schema.sql`
- Modify: `mcp/expense-tracker/expense_tracker/migrations.py`
- Test: `mcp/expense-tracker/tests/test_extras.py`

- [ ] **Step 1: Write the failing test**

Add to `mcp/expense-tracker/tests/test_extras.py` (append a new test class; keep existing imports, add `from expense_tracker.db import connect` if not present):

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_extras.RecurringSchemaMigrationTests -v` (from `mcp/expense-tracker/`)
Expected: FAIL — `recurring_expenses` not in tables.

- [ ] **Step 3: Add the tables to `schema.sql`**

Append to `mcp/expense-tracker/expense_tracker/schema.sql` (after the `category_budgets` block):

```sql
CREATE TABLE IF NOT EXISTS recurring_expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    suggested_amount REAL CHECK (suggested_amount IS NULL OR suggested_amount >= 0),
    currency TEXT NOT NULL DEFAULT 'ARS',
    category_id INTEGER NOT NULL REFERENCES categories(id),
    project_id INTEGER REFERENCES projects(id),
    paid_by_person_id INTEGER NOT NULL REFERENCES persons(id),
    notes TEXT,
    frequency TEXT NOT NULL CHECK (frequency IN ('weekly', 'monthly', 'yearly')),
    interval INTEGER NOT NULL DEFAULT 1 CHECK (interval >= 1),
    anchor_day INTEGER,
    anchor_month INTEGER,
    start_date TEXT NOT NULL,
    next_due_date TEXT NOT NULL,
    last_generated_date TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_by_person_id INTEGER REFERENCES persons(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS recurring_allocations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recurring_id INTEGER NOT NULL REFERENCES recurring_expenses(id) ON DELETE CASCADE,
    person_id INTEGER NOT NULL REFERENCES persons(id),
    percentage REAL NOT NULL CHECK (percentage > 0 AND percentage <= 100),
    UNIQUE (recurring_id, person_id)
);

CREATE INDEX IF NOT EXISTS idx_recurring_alloc_recurring ON recurring_allocations(recurring_id);
CREATE INDEX IF NOT EXISTS idx_recurring_due ON recurring_expenses(next_due_date);
```

Note: `expenses.recurring_id` is intentionally NOT added to `schema.sql`'s `expenses` table here — it is added by the migration (Step 4) so the column-add path is exercised the same way on fresh and existing DBs. (Alternatively add it to the `expenses` DDL too; the migration's `_column_exists` guard makes both safe. This plan keeps it in the migration only to keep one source of truth for the column-add.)

- [ ] **Step 4: Add the migration**

In `mcp/expense-tracker/expense_tracker/migrations.py`, inside `run_migrations()` (before the final `conn.commit()`), add:

```python
        if not _table_exists(conn, "recurring_expenses"):
            conn.execute(
                """
                CREATE TABLE recurring_expenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    description TEXT NOT NULL,
                    suggested_amount REAL CHECK (suggested_amount IS NULL OR suggested_amount >= 0),
                    currency TEXT NOT NULL DEFAULT 'ARS',
                    category_id INTEGER NOT NULL REFERENCES categories(id),
                    project_id INTEGER REFERENCES projects(id),
                    paid_by_person_id INTEGER NOT NULL REFERENCES persons(id),
                    notes TEXT,
                    frequency TEXT NOT NULL CHECK (frequency IN ('weekly', 'monthly', 'yearly')),
                    interval INTEGER NOT NULL DEFAULT 1 CHECK (interval >= 1),
                    anchor_day INTEGER,
                    anchor_month INTEGER,
                    start_date TEXT NOT NULL,
                    next_due_date TEXT NOT NULL,
                    last_generated_date TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_by_person_id INTEGER REFERENCES persons(id),
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """,
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_recurring_due ON recurring_expenses(next_due_date)",
            )

        if not _table_exists(conn, "recurring_allocations"):
            conn.execute(
                """
                CREATE TABLE recurring_allocations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recurring_id INTEGER NOT NULL REFERENCES recurring_expenses(id) ON DELETE CASCADE,
                    person_id INTEGER NOT NULL REFERENCES persons(id),
                    percentage REAL NOT NULL CHECK (percentage > 0 AND percentage <= 100),
                    UNIQUE (recurring_id, person_id)
                )
                """,
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_recurring_alloc_recurring ON recurring_allocations(recurring_id)",
            )

        if not _column_exists(conn, "expenses", "recurring_id"):
            conn.execute(
                "ALTER TABLE expenses ADD COLUMN recurring_id INTEGER REFERENCES recurring_expenses(id)",
            )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m unittest tests.test_extras.RecurringSchemaMigrationTests -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add mcp/expense-tracker/expense_tracker/schema.sql mcp/expense-tracker/expense_tracker/migrations.py mcp/expense-tracker/tests/test_extras.py
git commit -m "feat(recurring): add recurring_expenses schema and migration

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Date-math helpers for due-date advancement

**Files:**
- Modify: `mcp/expense-tracker/expense_tracker/repositories.py`
- Test: `mcp/expense-tracker/tests/test_repositories.py`

- [ ] **Step 1: Write the failing test**

Add a new test class to `mcp/expense-tracker/tests/test_repositories.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_repositories.RecurringDateMathTests -v`
Expected: FAIL — `module 'expense_tracker.repositories' has no attribute '_advance_due_date'`.

- [ ] **Step 3: Implement the helpers**

At the top of `repositories.py`, ensure these imports exist (the file already imports `from datetime import datetime`; extend it):

```python
import calendar
from datetime import date, datetime, timedelta
```

Add near the other private helpers (e.g., after `_validate_allocations`):

```python
_FREQUENCIES = ("weekly", "monthly", "yearly")


def _today_str() -> str:
    return date.today().isoformat()


def _advance_due_date(
    due: str,
    frequency: str,
    interval: int,
    anchor_day: int | None,
    anchor_month: int | None,
) -> str:
    """Advance an ISO date by interval x frequency, preserving the anchor day."""
    d = date.fromisoformat(due)
    if frequency == "weekly":
        return (d + timedelta(days=7 * interval)).isoformat()
    if frequency == "monthly":
        month_index = (d.month - 1) + interval
        year = d.year + month_index // 12
        month = month_index % 12 + 1
        day = anchor_day or d.day
        last = calendar.monthrange(year, month)[1]
        return date(year, month, min(day, last)).isoformat()
    if frequency == "yearly":
        year = d.year + interval
        month = anchor_month or d.month
        day = anchor_day or d.day
        last = calendar.monthrange(year, month)[1]
        return date(year, month, min(day, last)).isoformat()
    raise ValidationError(f"Unknown frequency: {frequency}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m unittest tests.test_repositories.RecurringDateMathTests -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add mcp/expense-tracker/expense_tracker/repositories.py mcp/expense-tracker/tests/test_repositories.py
git commit -m "feat(recurring): add due-date advancement helper

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `create_recurring_expense` + `list_recurring_expenses`

**Files:**
- Modify: `mcp/expense-tracker/expense_tracker/repositories.py`
- Test: `mcp/expense-tracker/tests/test_repositories.py`

- [ ] **Step 1: Write the failing test**

Add to the new recurring test class (create one class `RecurringRepoTests` reusing the `setUp`/`tearDown` shape from `ExpenseTrackerTests` — temp DB + `init_db(seed="test")`):

```python
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
        self.assertTrue(all("next_due_date" in it for it in items))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_repositories.RecurringRepoTests -v`
Expected: FAIL — `no attribute 'create_recurring_expense'`.

- [ ] **Step 3: Implement `create_recurring_expense` + `list_recurring_expenses` + enrichment helper**

Add to `repositories.py`:

```python
def _recurring_with_relations(conn, recurring_id: int) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM recurring_expenses WHERE id = ?", (recurring_id,)
    ).fetchone()
    if row is None:
        raise NotFoundError(f"Recurring expense not found: {recurring_id}")
    rec = row_to_dict(row)
    rec["category"] = _get_category_by_ref(conn, rec["category_id"])
    rec["project"] = _get_project_by_ref(conn, rec["project_id"]) if rec["project_id"] else None
    rec["paid_by"] = _get_person_by_ref(conn, rec["paid_by_person_id"])
    alloc_rows = conn.execute(
        """
        SELECT ra.person_id, ra.percentage, p.slug AS person_slug, p.display_name AS person_name
        FROM recurring_allocations ra
        JOIN persons p ON p.id = ra.person_id
        WHERE ra.recurring_id = ?
        ORDER BY ra.person_id
        """,
        (recurring_id,),
    ).fetchall()
    rec["allocations"] = [
        {
            "person_id": r["person_id"],
            "person_slug": r["person_slug"],
            "person_name": r["person_name"],
            "percentage": r["percentage"],
        }
        for r in alloc_rows
    ]
    return rec


def create_recurring_expense(
    description: str,
    category: str | int,
    paid_by: str | int,
    frequency: str,
    start_date: str,
    suggested_amount: float | None = None,
    currency: str = "ARS",
    interval: int = 1,
    anchor_day: int | None = None,
    anchor_month: int | None = None,
    project: str | int | None = None,
    notes: str | None = None,
    allocations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if frequency not in _FREQUENCIES:
        raise ValidationError(f"frequency must be one of {_FREQUENCIES}")
    if interval < 1:
        raise ValidationError("interval must be >= 1")
    if suggested_amount is not None and suggested_amount < 0:
        raise ValidationError("suggested_amount must be >= 0")
    datetime.strptime(start_date, "%Y-%m-%d")
    start = date.fromisoformat(start_date)
    resolved_anchor_day = anchor_day if anchor_day is not None else start.day
    resolved_anchor_month = anchor_month if anchor_month is not None else start.month
    with connect() as conn:
        category_row = _get_category_by_ref(conn, category)
        paid_by_row = _get_person_by_ref(conn, paid_by)
        project_row = _get_accessible_project_by_ref(conn, project) if project else None
        caller = _get_caller_person(conn)
        normalized_allocations = _resolve_allocations(conn, allocations, paid_by_row["id"])
        cur = conn.execute(
            """
            INSERT INTO recurring_expenses (
                description, suggested_amount, currency, category_id, project_id,
                paid_by_person_id, notes, frequency, interval, anchor_day, anchor_month,
                start_date, next_due_date, created_by_person_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                description.strip(),
                float(suggested_amount) if suggested_amount is not None else None,
                currency.upper(),
                category_row["id"],
                project_row["id"] if project_row else None,
                paid_by_row["id"],
                notes,
                frequency,
                int(interval),
                resolved_anchor_day,
                resolved_anchor_month,
                start_date,
                start_date,  # first occurrence is on start_date
                caller["id"] if caller else None,
            ),
        )
        recurring_id = cur.lastrowid
        for alloc in normalized_allocations:
            conn.execute(
                "INSERT INTO recurring_allocations (recurring_id, person_id, percentage) VALUES (?, ?, ?)",
                (recurring_id, alloc["person_id"], alloc["percentage"]),
            )
        conn.commit()
        return _recurring_with_relations(conn, recurring_id)


def list_recurring_expenses(active_only: bool = False) -> list[dict[str, Any]]:
    with connect() as conn:
        clause = "WHERE is_active = 1" if active_only else ""
        rows = conn.execute(
            f"SELECT id FROM recurring_expenses {clause} ORDER BY next_due_date, id"
        ).fetchall()
        return [_recurring_with_relations(conn, r["id"]) for r in rows]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m unittest tests.test_repositories.RecurringRepoTests -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add mcp/expense-tracker/expense_tracker/repositories.py mcp/expense-tracker/tests/test_repositories.py
git commit -m "feat(recurring): create and list recurring templates

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: `update_recurring_expense` + `delete_recurring_expense`

**Files:**
- Modify: `mcp/expense-tracker/expense_tracker/repositories.py`
- Test: `mcp/expense-tracker/tests/test_repositories.py`

- [ ] **Step 1: Write the failing test**

Add to `RecurringRepoTests`:

```python
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
        rec = self._make_rent()
        repo.generate_recurring_expense(rec["id"])
        result = repo.delete_recurring_expense(rec["id"])
        self.assertFalse(result["hard_deleted"])
        items = repo.list_recurring_expenses()
        self.assertEqual(items[0]["is_active"], 0)

    def test_delete_hard_when_unreferenced(self) -> None:
        rec = self._make_rent()
        result = repo.delete_recurring_expense(rec["id"])
        self.assertTrue(result["hard_deleted"])
        self.assertEqual(repo.list_recurring_expenses(), [])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_repositories.RecurringRepoTests -v`
Expected: FAIL — `no attribute 'update_recurring_expense'`.

- [ ] **Step 3: Implement update + delete**

Add to `repositories.py`:

```python
def update_recurring_expense(
    recurring_id: int,
    description: str | None = None,
    suggested_amount: float | None = None,
    currency: str | None = None,
    category: str | int | None = None,
    project: str | int | None = None,
    paid_by: str | int | None = None,
    notes: str | None = None,
    frequency: str | None = None,
    interval: int | None = None,
    anchor_day: int | None = None,
    anchor_month: int | None = None,
    start_date: str | None = None,
    is_active: bool | None = None,
    allocations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if frequency is not None and frequency not in _FREQUENCIES:
        raise ValidationError(f"frequency must be one of {_FREQUENCIES}")
    if interval is not None and interval < 1:
        raise ValidationError("interval must be >= 1")
    if suggested_amount is not None and suggested_amount < 0:
        raise ValidationError("suggested_amount must be >= 0")
    if start_date is not None:
        datetime.strptime(start_date, "%Y-%m-%d")
    with connect() as conn:
        current = conn.execute(
            "SELECT * FROM recurring_expenses WHERE id = ?", (recurring_id,)
        ).fetchone()
        if current is None:
            raise NotFoundError(f"Recurring expense not found: {recurring_id}")
        category_id = _get_category_by_ref(conn, category)["id"] if category is not None else None
        project_id = (_get_accessible_project_by_ref(conn, project)["id"] if project else None) if project is not None else current["project_id"]
        paid_by_id = _get_person_by_ref(conn, paid_by)["id"] if paid_by is not None else None

        conn.execute(
            """
            UPDATE recurring_expenses
            SET description = COALESCE(?, description),
                suggested_amount = CASE WHEN ? = 1 THEN ? ELSE suggested_amount END,
                currency = COALESCE(?, currency),
                category_id = COALESCE(?, category_id),
                project_id = ?,
                paid_by_person_id = COALESCE(?, paid_by_person_id),
                notes = COALESCE(?, notes),
                frequency = COALESCE(?, frequency),
                interval = COALESCE(?, interval),
                anchor_day = COALESCE(?, anchor_day),
                anchor_month = COALESCE(?, anchor_month),
                start_date = COALESCE(?, start_date),
                is_active = COALESCE(?, is_active),
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                description.strip() if description else None,
                1 if suggested_amount is not None else 0,
                float(suggested_amount) if suggested_amount is not None else None,
                currency.upper() if currency else None,
                category_id,
                project_id,
                paid_by_id,
                notes,
                frequency,
                int(interval) if interval is not None else None,
                anchor_day,
                anchor_month,
                start_date,
                (1 if is_active else 0) if is_active is not None else None,
                recurring_id,
            ),
        )

        # If cadence or start changed, recompute next_due_date from start_date.
        if frequency is not None or interval is not None or start_date is not None or anchor_day is not None or anchor_month is not None:
            row = conn.execute("SELECT * FROM recurring_expenses WHERE id = ?", (recurring_id,)).fetchone()
            conn.execute(
                "UPDATE recurring_expenses SET next_due_date = ? WHERE id = ?",
                (row["start_date"], recurring_id),
            )

        if allocations is not None:
            row = conn.execute("SELECT paid_by_person_id FROM recurring_expenses WHERE id = ?", (recurring_id,)).fetchone()
            normalized = _resolve_allocations(conn, allocations, row["paid_by_person_id"])
            conn.execute("DELETE FROM recurring_allocations WHERE recurring_id = ?", (recurring_id,))
            for alloc in normalized:
                conn.execute(
                    "INSERT INTO recurring_allocations (recurring_id, person_id, percentage) VALUES (?, ?, ?)",
                    (recurring_id, alloc["person_id"], alloc["percentage"]),
                )
        conn.commit()
        return _recurring_with_relations(conn, recurring_id)


def delete_recurring_expense(recurring_id: int) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute("SELECT id FROM recurring_expenses WHERE id = ?", (recurring_id,)).fetchone()
        if row is None:
            raise NotFoundError(f"Recurring expense not found: {recurring_id}")
        referenced = conn.execute(
            "SELECT COUNT(*) AS c FROM expenses WHERE recurring_id = ?", (recurring_id,)
        ).fetchone()["c"]
        if referenced:
            conn.execute(
                "UPDATE recurring_expenses SET is_active = 0, updated_at = datetime('now') WHERE id = ?",
                (recurring_id,),
            )
            conn.commit()
            return {"hard_deleted": False, "deactivated": True, "id": recurring_id}
        conn.execute("DELETE FROM recurring_allocations WHERE recurring_id = ?", (recurring_id,))
        conn.execute("DELETE FROM recurring_expenses WHERE id = ?", (recurring_id,))
        conn.commit()
        return {"hard_deleted": True, "deactivated": False, "id": recurring_id}
```

Note on the `start_date`-only recompute: changing `start_date` alone resets `next_due_date` to the new start. This is intentional — editing the schedule restarts the cadence from the new anchor.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m unittest tests.test_repositories.RecurringRepoTests -v`
Expected: PASS. (Requires `generate_recurring_expense` from Task 6; if running this task in isolation before Task 6, the two delete tests will error — implement Task 6 before running the full class, or temporarily skip the delete tests. Recommended: do Tasks 5–6 then run the whole class.)

- [ ] **Step 5: Commit**

```bash
git add mcp/expense-tracker/expense_tracker/repositories.py mcp/expense-tracker/tests/test_repositories.py
git commit -m "feat(recurring): update and delete recurring templates

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: `list_due_recurring`

**Files:**
- Modify: `mcp/expense-tracker/expense_tracker/repositories.py`
- Test: `mcp/expense-tracker/tests/test_repositories.py`

- [ ] **Step 1: Write the failing test**

Add to `RecurringRepoTests`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_repositories.RecurringRepoTests.test_list_due_returns_only_active_and_due -v`
Expected: FAIL — `no attribute 'list_due_recurring'`.

- [ ] **Step 3: Implement `list_due_recurring`**

Add to `repositories.py`:

```python
def list_due_recurring(today: str | None = None) -> list[dict[str, Any]]:
    today = today or _today_str()
    datetime.strptime(today, "%Y-%m-%d")
    with connect() as conn:
        rows = conn.execute(
            "SELECT id FROM recurring_expenses WHERE is_active = 1 AND next_due_date <= ? ORDER BY next_due_date, id",
            (today,),
        ).fetchall()
        return [_recurring_with_relations(conn, r["id"]) for r in rows]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m unittest tests.test_repositories.RecurringRepoTests.test_list_due_returns_only_active_and_due tests.test_repositories.RecurringRepoTests.test_list_due_excludes_inactive -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add mcp/expense-tracker/expense_tracker/repositories.py mcp/expense-tracker/tests/test_repositories.py
git commit -m "feat(recurring): list due recurring templates

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: `generate_recurring_expense` (materialize one occurrence)

**Files:**
- Modify: `mcp/expense-tracker/expense_tracker/repositories.py`
- Test: `mcp/expense-tracker/tests/test_repositories.py`

- [ ] **Step 1: Write the failing test**

Add to `RecurringRepoTests`:

```python
    def test_generate_fixed_uses_suggested_amount_and_advances_due(self) -> None:
        rec = self._make_rent(start_date="2026-01-05", suggested_amount=100000)
        result = repo.generate_recurring_expense(rec["id"])
        self.assertEqual(result["expense"]["amount"], 100000)
        self.assertEqual(result["expense"]["expense_date"], "2026-01-05")
        self.assertEqual(result["expense"]["recurring_id"], rec["id"])
        # next_due advanced one month
        self.assertEqual(result["recurring"]["next_due_date"], "2026-02-05")
        self.assertEqual(result["recurring"]["last_generated_date"], "2026-01-05")

    def test_generate_variable_requires_amount(self) -> None:
        rec = self._make_rent(suggested_amount=None)
        with self.assertRaises(repo.ValidationError):
            repo.generate_recurring_expense(rec["id"])
        result = repo.generate_recurring_expense(rec["id"], amount=54321)
        self.assertEqual(result["expense"]["amount"], 54321)

    def test_generate_is_idempotent_for_same_period(self) -> None:
        rec = self._make_rent(start_date="2026-01-05", suggested_amount=100000)
        repo.generate_recurring_expense(rec["id"], expense_date="2026-01-05")
        with self.assertRaises(repo.ValidationError):
            repo.generate_recurring_expense(rec["id"], expense_date="2026-01-05")

    def test_generate_copies_allocations(self) -> None:
        rec = self._make_rent(
            allocations=[
                {"person": "alice", "percentage": 60},
                {"person": "bob", "percentage": 40},
            ],
        )
        result = repo.generate_recurring_expense(rec["id"])
        self.assertEqual(len(result["expense"]["allocations"]), 2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_repositories.RecurringRepoTests.test_generate_fixed_uses_suggested_amount_and_advances_due -v`
Expected: FAIL — `no attribute 'generate_recurring_expense'`.

- [ ] **Step 3: Implement `generate_recurring_expense`**

Add to `repositories.py`:

```python
def generate_recurring_expense(
    recurring_id: int,
    amount: float | None = None,
    expense_date: str | None = None,
) -> dict[str, Any]:
    with connect() as conn:
        rec = conn.execute(
            "SELECT * FROM recurring_expenses WHERE id = ?", (recurring_id,)
        ).fetchone()
        if rec is None:
            raise NotFoundError(f"Recurring expense not found: {recurring_id}")
        if not rec["is_active"]:
            raise ValidationError("Recurring template is inactive")

        occurrence_date = expense_date or rec["next_due_date"]
        datetime.strptime(occurrence_date, "%Y-%m-%d")

        # Idempotency: never create two expenses for the same template+date.
        existing = conn.execute(
            "SELECT 1 FROM expenses WHERE recurring_id = ? AND expense_date = ?",
            (recurring_id, occurrence_date),
        ).fetchone()
        if existing is not None:
            raise ValidationError(
                f"An expense for this recurring template already exists on {occurrence_date}"
            )

        if amount is None:
            if rec["suggested_amount"] is None:
                raise ValidationError("amount is required for a variable recurring expense")
            final_amount = float(rec["suggested_amount"])
        else:
            if amount < 0:
                raise ValidationError("Amount must be >= 0")
            final_amount = float(amount)

        cur = conn.execute(
            """
            INSERT INTO expenses (
                expense_date, description, amount, currency, category_id,
                project_id, paid_by_person_id, notes, recurring_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                occurrence_date,
                rec["description"],
                final_amount,
                rec["currency"],
                rec["category_id"],
                rec["project_id"],
                rec["paid_by_person_id"],
                rec["notes"],
                recurring_id,
            ),
        )
        expense_id = cur.lastrowid
        alloc_rows = conn.execute(
            "SELECT person_id, percentage FROM recurring_allocations WHERE recurring_id = ?",
            (recurring_id,),
        ).fetchall()
        for a in alloc_rows:
            conn.execute(
                "INSERT INTO expense_allocations (expense_id, person_id, percentage) VALUES (?, ?, ?)",
                (expense_id, a["person_id"], a["percentage"]),
            )

        # Advance the schedule only when we generated the current due occurrence.
        if occurrence_date >= rec["next_due_date"]:
            new_due = _advance_due_date(
                rec["next_due_date"], rec["frequency"], rec["interval"],
                rec["anchor_day"], rec["anchor_month"],
            )
            conn.execute(
                "UPDATE recurring_expenses SET next_due_date = ?, last_generated_date = ?, updated_at = datetime('now') WHERE id = ?",
                (new_due, occurrence_date, recurring_id),
            )
        conn.commit()
        return {
            "expense": _expense_with_relations(conn, expense_id),
            "recurring": _recurring_with_relations(conn, recurring_id),
        }
```

- [ ] **Step 4: Run the whole recurring class to verify it passes**

Run: `.venv/bin/python -m unittest tests.test_repositories.RecurringRepoTests -v`
Expected: PASS (all recurring repo tests, including the Task 4 delete tests).

- [ ] **Step 5: Commit**

```bash
git add mcp/expense-tracker/expense_tracker/repositories.py mcp/expense-tracker/tests/test_repositories.py
git commit -m "feat(recurring): materialize occurrences with idempotency

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Catch-up end-to-end test

**Files:**
- Test: `mcp/expense-tracker/tests/test_e2e.py`

- [ ] **Step 1: Write the failing test**

Add to `mcp/expense-tracker/tests/test_e2e.py` (follow the file's existing setUp pattern — temp DB + `init_db(seed="test")`; match the existing class style there):

```python
    def test_recurring_catch_up_walks_backlog(self) -> None:
        from expense_tracker import repositories as repo
        rec = repo.create_recurring_expense(
            description="Alquiler",
            category="comida",
            paid_by="alice",
            frequency="monthly",
            start_date="2026-01-05",
            suggested_amount=100000,
        )
        rid = rec["id"]
        generated_dates = []
        # Materialize every occurrence due on/before 2026-03-15
        for _ in range(12):  # safety bound
            due = repo.list_due_recurring(today="2026-03-15")
            if not due:
                break
            occ = due[0]["next_due_date"]
            repo.generate_recurring_expense(rid, expense_date=occ)
            generated_dates.append(occ)
        self.assertEqual(generated_dates, ["2026-01-05", "2026-02-05", "2026-03-05"])
        # Next due is now in the future relative to 2026-03-15
        remaining = repo.list_due_recurring(today="2026-03-15")
        self.assertEqual(remaining, [])
```

- [ ] **Step 2: Run test to verify it fails (then passes)**

Run: `.venv/bin/python -m unittest tests.test_e2e -v` (the test name; class is the existing e2e class)
Expected: PASS — backlog materializes three occurrences. (If it fails, the loop/advance logic from Task 6 needs review.) If the method is added to an existing class and the logic from Tasks 1–6 is in place, this passes immediately; that is the intended verification of the catch-up flow.

- [ ] **Step 3: Commit**

```bash
git add mcp/expense-tracker/tests/test_e2e.py
git commit -m "test(recurring): catch-up walks the backlog one period at a time

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: MCP server tool wrappers (6 tools)

**Files:**
- Modify: `mcp/expense-tracker/server.py`
- Test: manual MCP tool count check

- [ ] **Step 1: Add the 6 tool wrappers**

Append to `mcp/expense-tracker/server.py` (after the budget tools, before `health_check`), matching the existing `_ok`/`_err` wrapper pattern:

```python
@mcp.tool()
def create_recurring_expense(
    description: str,
    category: str,
    paid_by: str,
    frequency: str,
    start_date: str,
    suggested_amount: float | None = None,
    currency: str = "ARS",
    interval: int = 1,
    anchor_day: int | None = None,
    anchor_month: int | None = None,
    project: str | None = None,
    notes: str | None = None,
    allocations: list[dict[str, Any]] | None = None,
) -> str:
    """Create a recurring expense template (weekly/monthly/yearly). suggested_amount=null means variable."""
    try:
        return _ok(repo.create_recurring_expense(
            description=description, category=category, paid_by=paid_by,
            frequency=frequency, start_date=start_date, suggested_amount=suggested_amount,
            currency=currency, interval=interval, anchor_day=anchor_day,
            anchor_month=anchor_month, project=project, notes=notes, allocations=allocations,
        ))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def update_recurring_expense(
    recurring_id: int,
    description: str | None = None,
    suggested_amount: float | None = None,
    currency: str | None = None,
    category: str | None = None,
    project: str | None = None,
    paid_by: str | None = None,
    notes: str | None = None,
    frequency: str | None = None,
    interval: int | None = None,
    anchor_day: int | None = None,
    anchor_month: int | None = None,
    start_date: str | None = None,
    is_active: bool | None = None,
    allocations: list[dict[str, Any]] | None = None,
) -> str:
    """Update a recurring expense template. Changing cadence/start resets next_due_date."""
    try:
        return _ok(repo.update_recurring_expense(
            recurring_id, description=description, suggested_amount=suggested_amount,
            currency=currency, category=category, project=project, paid_by=paid_by,
            notes=notes, frequency=frequency, interval=interval, anchor_day=anchor_day,
            anchor_month=anchor_month, start_date=start_date, is_active=is_active,
            allocations=allocations,
        ))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def delete_recurring_expense(recurring_id: int) -> str:
    """Delete a recurring template (deactivates if it has generated expenses, else hard-deletes)."""
    try:
        return _ok(repo.delete_recurring_expense(recurring_id))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def list_recurring_expenses(active_only: bool = False) -> str:
    """List recurring expense templates for the household."""
    try:
        return _ok(repo.list_recurring_expenses(active_only=active_only))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def list_due_recurring(today: str | None = None) -> str:
    """List recurring templates whose next occurrence is due (next_due_date <= today)."""
    try:
        return _ok(repo.list_due_recurring(today=today))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def generate_recurring_expense(
    recurring_id: int,
    amount: float | None = None,
    expense_date: str | None = None,
) -> str:
    """Materialize one occurrence of a recurring template into a real expense (advances the schedule)."""
    try:
        return _ok(repo.generate_recurring_expense(recurring_id, amount=amount, expense_date=expense_date))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)
```

- [ ] **Step 2: Verify the server imports and tool count**

Run (from `mcp/expense-tracker/`):
```bash
.venv/bin/python -c "import server; print(len([t for t in dir(server) if not t.startswith('_')]))"
```
Then sanity-check the server starts without import errors:
```bash
.venv/bin/python -c "import server; print('ok')"
```
Expected: `ok` printed (no import error). The 6 new tools are registered.

- [ ] **Step 3: Run the full test suite**

Run: `.venv/bin/python -m unittest discover -s tests -v`
Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add mcp/expense-tracker/server.py
git commit -m "feat(recurring): expose recurring expense MCP tools

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: i18n frequency labels

**Files:**
- Modify: `mcp/expense-tracker/expense_tracker/i18n.py`
- Test: `mcp/expense-tracker/tests/test_i18n.py`

- [ ] **Step 1: Inspect the current i18n structure**

Run: `.venv/bin/python -c "from expense_tracker import i18n; print(dir(i18n))"` and open `expense_tracker/i18n.py` to see how strings are keyed (e.g., a `STRINGS = {"en": {...}, "es": {...}}` dict and a `t(key, locale)` accessor). Match that exact shape.

- [ ] **Step 2: Write the failing test**

Add to `mcp/expense-tracker/tests/test_i18n.py` (use the same accessor the file already exposes; example assumes a `t(key, locale)` function — adapt to the real API found in Step 1):

```python
    def test_frequency_labels(self) -> None:
        from expense_tracker import i18n
        self.assertEqual(i18n.frequency_label("monthly", "en"), "monthly")
        self.assertEqual(i18n.frequency_label("monthly", "es"), "mensual")
        self.assertEqual(i18n.frequency_label("weekly", "es"), "semanal")
        self.assertEqual(i18n.frequency_label("yearly", "es"), "anual")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_i18n -v`
Expected: FAIL — `frequency_label` not defined.

- [ ] **Step 4: Implement `frequency_label`**

Add to `expense_tracker/i18n.py`:

```python
_FREQUENCY_LABELS = {
    "en": {"weekly": "weekly", "monthly": "monthly", "yearly": "yearly"},
    "es": {"weekly": "semanal", "monthly": "mensual", "yearly": "anual"},
}


def frequency_label(frequency: str, locale: str | None = None) -> str:
    loc = (locale or "es").strip().lower()
    if loc not in _FREQUENCY_LABELS:
        loc = "es"
    return _FREQUENCY_LABELS[loc].get(frequency, frequency)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m unittest tests.test_i18n -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add mcp/expense-tracker/expense_tracker/i18n.py mcp/expense-tracker/tests/test_i18n.py
git commit -m "feat(recurring): add i18n frequency labels (en/es)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## FEATURE B — Receipt capture (agent skill, no backend)

### Task 10: Receipts + recurring agent skill instructions (EN + ES)

**Files:**
- Modify: `locales/en/skills/expense-tracker/SKILL.md`
- Modify: `locales/es/skills/expense-tracker/SKILL.md`

- [ ] **Step 1: Read the existing skill files**

Open both `SKILL.md` files to match their heading style, tool-naming convention (`mcp_expense_tracker_*`), and tone before editing.

- [ ] **Step 2: Add a "Recurring expenses" section to `locales/en/skills/expense-tracker/SKILL.md`**

Append a section documenting the new tools and the lazy flow:

```markdown
## Recurring expenses

Templates for repeating costs (rent, subscriptions, utilities). They are **household-wide** — everyone sees them and can materialize what is due. Nothing is created automatically; you generate occurrences on demand.

- `mcp_expense_tracker_create_recurring_expense` — define a template: `description`, `category`, `paid_by`, `frequency` (`weekly`|`monthly`|`yearly`), `start_date` (YYYY-MM-DD). Optional: `suggested_amount` (omit/null for **variable** bills like electricity), `interval` (every N), `anchor_day`, `anchor_month`, `project`, `notes`, `allocations`.
- `mcp_expense_tracker_list_recurring_expenses` — show all templates and their next due date.
- `mcp_expense_tracker_list_due_recurring` — show templates due now (`next_due_date <= today`).
- `mcp_expense_tracker_generate_recurring_expense` — create one real expense from a template. For **fixed** templates the suggested amount is used; for **variable** templates you MUST pass `amount`. Advances the schedule by one period.
- `mcp_expense_tracker_update_recurring_expense` / `mcp_expense_tracker_delete_recurring_expense`.

**When a member says "what do I owe this month?" or starts a session:** call `list_due_recurring`. For each due template: if fixed, confirm and generate; if variable, ask the amount, then generate. If several periods are overdue, materialize them one at a time (each generate advances one period).
```

- [ ] **Step 3: Add a "Receipts" section to `locales/en/skills/expense-tracker/SKILL.md`**

```markdown
## Receipts (photos)

When a member sends a **photo of a receipt**, read it directly (your model is multimodal) and extract:
- **amount** (total), **date**, **merchant** → use as the expense `description`, and infer a **category** from the household's existing categories (`list_categories`).
- Default `paid_by` to the member who sent the photo.

Then show a short confirmation — Amount / Date / Merchant / Category — and only after the member confirms, call `mcp_expense_tracker_add_expense`. If a field is unreadable, ask **only** for that field. The image is not stored; only the resulting expense is saved.
```

- [ ] **Step 4: Mirror both sections in Spanish in `locales/es/skills/expense-tracker/SKILL.md`**

Add the equivalent `## Gastos recurrentes` and `## Recibos (fotos)` sections, translated, keeping tool names identical (`mcp_expense_tracker_*`). Example for receipts:

```markdown
## Recibos (fotos)

Cuando un miembro envíe una **foto de un recibo**, léela directamente (tu modelo es multimodal) y extrae:
- **importe** (total), **fecha**, **comercio** → úsalo como `description`, e infiere la **categoría** de las categorías existentes del hogar (`list_categories`).
- Pon `paid_by` por defecto en quien envió la foto.

Muestra una confirmación breve — Importe / Fecha / Comercio / Categoría — y solo tras la confirmación llama a `mcp_expense_tracker_add_expense`. Si un campo no se lee, pregunta **solo** por ese campo. La imagen no se guarda; solo se registra el gasto resultante.
```

And `## Gastos recurrentes` translated equivalently to Step 2.

- [ ] **Step 5: Commit**

```bash
git add locales/en/skills/expense-tracker/SKILL.md locales/es/skills/expense-tracker/SKILL.md
git commit -m "docs(skills): document recurring expenses and receipt capture (en/es)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 11: SOUL guidance for receipts + recurring (EN + ES)

**Files:**
- Modify: `locales/en/SOUL.md`
- Modify: `locales/es/SOUL.md`

- [ ] **Step 1: Read both SOUL files**

Match the existing structure (defaults like "I paid" → `paid_by = {{MEMBER_SLUG}}`, no-narration rules).

- [ ] **Step 2: Add concise guidance to `locales/en/SOUL.md`**

Add to the behavior/defaults section:

```markdown
- If the user sends a photo of a receipt, extract amount/date/merchant/category, confirm the parsed values in one short message, then log the expense. Ask only for fields you could not read.
- For recurring costs ("every month I pay…"), offer to create a recurring template. When a member asks what is due or pending, check due recurring templates and offer to log them (ask the amount for variable bills).
```

- [ ] **Step 3: Add the Spanish equivalent to `locales/es/SOUL.md`**

```markdown
- Si el usuario envía una foto de un recibo, extrae importe/fecha/comercio/categoría, confirma los valores en un mensaje breve y registra el gasto. Pregunta solo por los campos que no hayas podido leer.
- Para gastos recurrentes ("todos los meses pago…"), ofrece crear una plantilla recurrente. Cuando un miembro pregunte qué toca pagar o qué hay pendiente, revisa las plantillas recurrentes vencidas y ofrece registrarlas (pregunta el importe en las facturas variables).
```

- [ ] **Step 4: Commit**

```bash
git add locales/en/SOUL.md locales/es/SOUL.md
git commit -m "docs(soul): guide receipt capture and recurring expenses (en/es)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 12: Docs + prerequisites note

**Files:**
- Modify: `README.md`
- Modify: `docs/en/BRIEFING.md`, `docs/es/BRIEFING.md`
- Modify: `scripts/expense_cli/prereqs.py`

- [ ] **Step 1: Update tool count and add feature notes in `README.md`**

- Replace every "38 tools" reference with "44 tools" (search: `grep -n "38 tools\|38 FastMCP\|Must show 38" README.md`). Update the MCP test expectation lines too (`mcp test expense-tracker` "38 tools" → "44 tools").
- Add a "Recurring expenses" row group to the MCP tools reference table listing the 6 new tools.
- Add a short "Receipts (photos)" note under "What you can do" explaining the multimodal-model requirement and that images are not stored.

- [ ] **Step 2: Update `docs/en/BRIEFING.md` and `docs/es/BRIEFING.md`**

Add a brief architecture note: recurring templates table + lazy generation; receipts handled by the agent's multimodal model with no backend storage. Update any tool count.

- [ ] **Step 3: Add an informational prerequisite note in `scripts/expense_cli/prereqs.py`**

Open `prereqs.py`; in the user-facing prerequisites summary/output, add a non-blocking informational line:

```python
# Informational only — not a hard gate (text-only use remains valid).
RECEIPT_NOTE = "Receipt photo capture requires a vision-capable (multimodal) model in the profile."
```
Surface `RECEIPT_NOTE` wherever the module prints its summary (match how other notes are emitted). Do not fail the prereq check based on it.

- [ ] **Step 4: Run the full suite once more**

Run (from `mcp/expense-tracker/`): `.venv/bin/python -m unittest discover -s tests -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add README.md docs/en/BRIEFING.md docs/es/BRIEFING.md scripts/expense_cli/prereqs.py
git commit -m "docs: recurring expenses + receipts (tool count 44, multimodal note)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Final verification

- [ ] Run the full test suite from `mcp/expense-tracker/`:
  ```bash
  .venv/bin/python -m unittest discover -s tests -v
  ```
  Expected: all tests pass, including `RecurringRepoTests`, `RecurringDateMathTests`, `RecurringSchemaMigrationTests`, the e2e catch-up test, and i18n.
- [ ] Confirm the MCP server imports cleanly: `.venv/bin/python -c "import server; print('ok')"`.
- [ ] Confirm migration is idempotent: run `.venv/bin/python -c "from expense_tracker.db import init_db; init_db(seed='none'); init_db(seed='none'); print('ok')"` against an existing DB path (no error on second run).
- [ ] `grep -rn "38 tools" README.md docs/` returns nothing (all updated to 44).

---

## Notes for the implementer

- **No new dependencies.** Only stdlib `datetime` + `calendar` are added.
- **Date injection for tests:** repository functions that depend on "today" (`list_due_recurring`) accept an optional `today` parameter; `generate_recurring_expense` derives the occurrence date from the template's `next_due_date` unless `expense_date` is passed. This keeps tests deterministic without monkeypatching.
- **Idempotency** relies on `expenses.recurring_id` + `expense_date`. Do not remove the duplicate check in `generate_recurring_expense`.
- **Visibility:** recurring templates are intentionally household-wide (no membership filter), unlike projects. Do not add a visibility clause.
- Receipts add **zero** backend code by design — resist the temptation to add an attachments table; archiving is explicitly out of scope.
```