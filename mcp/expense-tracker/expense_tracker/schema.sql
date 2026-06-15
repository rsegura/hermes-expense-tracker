PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS persons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    aliases TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_by_person_id INTEGER REFERENCES persons(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS project_members (
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    person_id INTEGER NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('owner', 'member')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (project_id, person_id)
);

CREATE INDEX IF NOT EXISTS idx_project_members_person ON project_members(person_id);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    parent_id INTEGER REFERENCES categories(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    expense_date TEXT NOT NULL,
    description TEXT NOT NULL,
    amount REAL NOT NULL CHECK (amount >= 0),
    currency TEXT NOT NULL DEFAULT 'ARS',
    category_id INTEGER NOT NULL REFERENCES categories(id),
    project_id INTEGER REFERENCES projects(id),
    paid_by_person_id INTEGER NOT NULL REFERENCES persons(id),
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS expense_allocations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    expense_id INTEGER NOT NULL REFERENCES expenses(id) ON DELETE CASCADE,
    person_id INTEGER NOT NULL REFERENCES persons(id),
    percentage REAL NOT NULL CHECK (percentage > 0 AND percentage <= 100),
    UNIQUE (expense_id, person_id)
);

CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(expense_date);
CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category_id);
CREATE INDEX IF NOT EXISTS idx_expenses_project ON expenses(project_id);
CREATE INDEX IF NOT EXISTS idx_expenses_paid_by ON expenses(paid_by_person_id);
CREATE INDEX IF NOT EXISTS idx_allocations_person ON expense_allocations(person_id);
CREATE INDEX IF NOT EXISTS idx_expenses_currency ON expenses(currency);

CREATE TABLE IF NOT EXISTS category_budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL UNIQUE REFERENCES categories(id),
    monthly_amount REAL NOT NULL CHECK (monthly_amount >= 0),
    currency TEXT NOT NULL DEFAULT 'ARS',
    alert_threshold_pct REAL NOT NULL DEFAULT 100.0 CHECK (alert_threshold_pct > 0),
    is_active INTEGER NOT NULL DEFAULT 1,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_budgets_category ON category_budgets(category_id);

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
