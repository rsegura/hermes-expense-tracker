from __future__ import annotations

import sqlite3

from .db import connect


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (name,),
    ).fetchone()
    return row is not None


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row["name"] == column for row in rows)


def _default_owner_id(conn: sqlite3.Connection) -> int | None:
    row = conn.execute("SELECT id FROM persons ORDER BY created_at, id LIMIT 1").fetchone()
    return int(row["id"]) if row is not None else None


def _backfill_project_members(conn: sqlite3.Connection) -> None:
    projects = conn.execute("SELECT id, created_by_person_id FROM projects").fetchall()
    persons = conn.execute("SELECT id FROM persons ORDER BY id").fetchall()
    if not persons:
        return

    for project in projects:
        owner_id = project["created_by_person_id"] or _default_owner_id(conn)
        if owner_id is None:
            continue
        if project["created_by_person_id"] is None:
            conn.execute(
                "UPDATE projects SET created_by_person_id = ? WHERE id = ?",
                (owner_id, project["id"]),
            )

        existing = conn.execute(
            "SELECT COUNT(*) AS c FROM project_members WHERE project_id = ?",
            (project["id"],),
        ).fetchone()["c"]
        if existing:
            continue

        for person in persons:
            role = "owner" if person["id"] == owner_id else "member"
            conn.execute(
                """
                INSERT OR IGNORE INTO project_members (project_id, person_id, role)
                VALUES (?, ?, ?)
                """,
                (project["id"], person["id"], role),
            )


def run_migrations() -> None:
    with connect() as conn:
        if not _column_exists(conn, "projects", "created_by_person_id"):
            conn.execute(
                "ALTER TABLE projects ADD COLUMN created_by_person_id INTEGER REFERENCES persons(id)",
            )

        if not _table_exists(conn, "project_members"):
            conn.execute(
                """
                CREATE TABLE project_members (
                    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    person_id INTEGER NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
                    role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('owner', 'member')),
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    PRIMARY KEY (project_id, person_id)
                )
                """,
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_project_members_person ON project_members(person_id)",
            )

        _backfill_project_members(conn)

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
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_expenses_recurring ON expenses(recurring_id)",
            )

        conn.commit()
