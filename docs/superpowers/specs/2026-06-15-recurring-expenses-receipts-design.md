# Design: Recurring Expenses & Receipt Capture

**Date:** 2026-06-15
**Status:** Approved (design); pending implementation plan
**Scope:** Two features for Hermes Expense Tracker — (1) recurring expense templates with on-demand generation, (2) receipt capture via the agent's multimodal model.

---

## 1. Goals & non-goals

### Goals
- Let a household define **recurring expense templates** (rent, subscriptions, utilities) and materialize the actual expense entries **on demand**, without any always-on background process.
- Support both **fixed** (Netflix, rent) and **variable** (electricity, water) amounts.
- Support **weekly / monthly / yearly** cadences with an "every N" interval.
- Templates are **household-wide**: every member sees them and can materialize what is due.
- Let a member **photograph a receipt** in chat; the agent's multimodal model extracts amount/date/merchant/category, confirms, and logs the expense via the existing `add_expense` tool.

### Non-goals
- No background scheduler / cron / gateway job for recurring generation (explicitly out of scope; generation is lazy/on-demand).
- No storage/archiving of receipt images (extract-only). No OCR library inside the MCP.
- No debt/settlement ledger (remains out of the product's scope).
- No per-person or project-scoped visibility for recurring templates (household-wide only).

---

## 2. Feature A — Recurring expenses

### 2.1 Generation model: lazy / on-demand

There is **no background job**. Expense rows are created only when a member interacts:
- The agent (or a member asking "what's due?") calls `list_due_recurring` to find templates whose `next_due_date <= today`.
- For each due occurrence, the agent calls `generate_recurring_expense`, which creates the expense and advances the template's `next_due_date`.

### 2.2 Due tracking: explicit `next_due_date` (Approach A)

Each template stores its next due date. On materialization, the expense is logged and `next_due_date` is advanced by `interval × frequency`. "What's due" is a cheap query:

```sql
SELECT * FROM recurring_expenses
WHERE is_active = 1 AND next_due_date <= date('now');
```

Rejected alternative (B): recompute occurrences statelessly from `start_date` + last generated. More expensive and makes catch-up harder. A was chosen for simplicity and a trivial "due" query.

### 2.3 Data model

New table `recurring_expenses` (mirrors the expense shape; `suggested_amount` NULL means variable):

```sql
CREATE TABLE IF NOT EXISTS recurring_expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    suggested_amount REAL CHECK (suggested_amount IS NULL OR suggested_amount >= 0),  -- NULL = variable
    currency TEXT NOT NULL DEFAULT 'ARS',
    category_id INTEGER NOT NULL REFERENCES categories(id),
    project_id INTEGER REFERENCES projects(id),
    paid_by_person_id INTEGER NOT NULL REFERENCES persons(id),
    notes TEXT,
    frequency TEXT NOT NULL CHECK (frequency IN ('weekly', 'monthly', 'yearly')),
    interval INTEGER NOT NULL DEFAULT 1 CHECK (interval >= 1),   -- "every N"
    anchor_day INTEGER,      -- day-of-month (1-31) for monthly/yearly; day-of-week (0-6) for weekly
    anchor_month INTEGER,    -- month (1-12) for yearly
    start_date TEXT NOT NULL,
    next_due_date TEXT NOT NULL,
    last_generated_date TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_by_person_id INTEGER REFERENCES persons(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

New child table `recurring_allocations` (mirror of `expense_allocations`; same 100%-sum rule):

```sql
CREATE TABLE IF NOT EXISTS recurring_allocations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recurring_id INTEGER NOT NULL REFERENCES recurring_expenses(id) ON DELETE CASCADE,
    person_id INTEGER NOT NULL REFERENCES persons(id),
    percentage REAL NOT NULL CHECK (percentage > 0 AND percentage <= 100),
    UNIQUE (recurring_id, person_id)
);
CREATE INDEX IF NOT EXISTS idx_recurring_alloc_recurring ON recurring_allocations(recurring_id);
CREATE INDEX IF NOT EXISTS idx_recurring_due ON recurring_expenses(next_due_date) WHERE is_active = 1;
```

Provenance / idempotency link on the existing `expenses` table:

```sql
ALTER TABLE expenses ADD COLUMN recurring_id INTEGER REFERENCES recurring_expenses(id);
```

**Visibility:** household-wide. No membership table; every member can list, generate, edit. `paid_by_person_id` + `recurring_allocations` decide attribution exactly like a normal expense. The default currency mirrors the existing schema default (`ARS`); the actual default at runtime follows the same resolution the rest of the code uses.

### 2.4 New MCP tools (6 → total 44)

| Tool | Behavior |
|------|----------|
| `create_recurring_expense` | Define a template: description, `suggested_amount` (or null for variable), currency, category, `paid_by`, allocations (default 100% to payer), optional project, frequency, interval, anchor day/month, `start_date`. Computes initial `next_due_date` from `start_date`. Validates allocations sum to 100% (reuses existing validator). |
| `update_recurring_expense` | Edit any field; re-validates allocations; may recompute `next_due_date` when cadence/anchor changes. |
| `delete_recurring_expense` | Deactivate (`is_active = 0`) by default; hard delete only if no generated expenses reference it, otherwise keep for provenance. |
| `list_recurring_expenses` | All household templates with `next_due_date`, active flag, cadence, allocations. |
| `list_due_recurring` | Templates with `next_due_date <= today` and `is_active`. Returns the occurrences pending generation (including catch-up occurrences — see 2.5). |
| `generate_recurring_expense(recurring_id, amount?, expense_date?)` | Materialize **one** occurrence. If template is fixed, use `suggested_amount` when `amount` omitted; if variable, `amount` is required (error if missing). Create expense + copy allocations, set `expenses.recurring_id`, set `expense_date` (defaults to the occurrence's due date), then advance `next_due_date`. **Idempotent:** refuses to create a duplicate if an expense with the same `recurring_id` and `expense_date` already exists. |

### 2.5 Catch-up policy

If a template is overdue by multiple periods (e.g., 3 months), `list_due_recurring` reports each missed occurrence with its proper date. Default behavior:
- **Fixed** templates: the agent may batch-confirm and generate all missed occurrences.
- **Variable** templates: the agent asks the amount **per occurrence** before generating each.

`generate_recurring_expense` always advances exactly one period per call, so repeated calls walk the backlog forward deterministically.

### 2.6 Date math

`next_due_date` advancement, given `frequency`, `interval`, `anchor_day`, `anchor_month`:
- **weekly:** add `7 × interval` days from current due date.
- **monthly:** add `interval` months, clamping `anchor_day` to the month's last day (e.g., day 31 → 30/28).
- **yearly:** add `interval` years, honoring `anchor_month` + `anchor_day` with the same clamping.

This logic lives in `repositories.py` (pure helper, unit-tested independently). Standard-library `datetime` only — no new dependency.

---

## 3. Feature B — Receipt capture (extract-only, no archiving)

### 3.1 Approach

**Zero backend changes** — no new tables, no new MCP tools, no schema migration. Receipt capture is entirely **agent behavior** that rides on the existing `add_expense` tool.

When a member sends a photo of a receipt in chat, the profile's **multimodal model** reads the image directly and extracts the fields. The MCP never receives the image; only the structured `add_expense` call results from it.

### 3.2 Prerequisite

The profile's configured model **must be multimodal** (vision-capable). This is a configuration/documentation concern:
- Documented as a prerequisite for the receipt feature in `README.md` / `docs/`.
- A note added to `scripts/expense_cli/prereqs.py` guidance (informational; not a hard install gate, since text-only use remains valid).

### 3.3 Agent skill changes

Add a "Receipts" section to `locales/en/skills/expense-tracker/SKILL.md` and `locales/es/skills/expense-tracker/SKILL.md`, plus brief SOUL guidance in `locales/{en,es}/SOUL.md`:

- On receiving a receipt photo: read **amount**, **date**, **merchant → description**; infer **category** from the household's existing categories (`list_categories`); default `paid_by` to the caller's slug.
- Present a **structured confirmation** (Amount / Date / Merchant / Category) before writing.
- On confirmation, call `add_expense` with the extracted values.
- If a field is unreadable, ask **only** for that field — do not re-request everything.
- The image is **not stored** (per scope decision). No provenance marker is added to notes by default.

---

## 4. i18n

Add to `expense_tracker/i18n.py` (en/es):
- Frequency labels: weekly / monthly / yearly (semanal / mensual / anual).
- "Due" / "overdue" wording used if recurring data appears in any generated report or list.

The agent formats most user-facing recurring text conversationally; i18n covers only labels emitted by the MCP layer.

---

## 5. Migrations & install

`run_migrations()` in `expense_tracker/migrations.py` (idempotent, matching the existing `_table_exists` / `_column_exists` pattern):
1. `CREATE TABLE IF NOT EXISTS recurring_expenses (...)`
2. `CREATE TABLE IF NOT EXISTS recurring_allocations (...)`
3. Add `expenses.recurring_id` column guarded by `_column_exists`.
4. Create the new indexes.

`schema.sql` is updated so fresh installs get the tables directly. `update.sh` / `update.ps1` already run migrations — **no install-flow changes**.

---

## 6. Testing

### Recurring (backend)
`mcp/expense-tracker/tests/test_repositories.py`:
- create / update / list templates; allocations default to 100% payer; allocation-sum validation rejects ≠100%.
- `list_due_recurring` returns only `next_due_date <= today` and active templates.
- `generate_recurring_expense`: fixed uses `suggested_amount`; variable requires `amount` (error if missing); sets `expenses.recurring_id`; advances `next_due_date`.
- **Idempotency:** second generate for the same period/date does not duplicate.
- Date-math helper: weekly/monthly/yearly advancement, end-of-month clamping (31 → 30/28), leap years.
- Catch-up: multi-period backlog walks forward one period per call.

`mcp/expense-tracker/tests/test_e2e.py`:
- Create template → advance the clock (inject/override "today") → generate → assert expense + allocations + provenance link.

Migration test: `expenses.recurring_id` present after `run_migrations()` on a pre-existing DB; new tables created.

### Receipts
No backend tests (skill-only behavior). Coverage is the documented skill instructions + the multimodal-model prerequisite note.

---

## 7. Out-of-scope / future

- Background auto-generation of recurring expenses (scheduler) — deferred.
- Receipt image archiving + retrieval — deferred (explicitly excluded now).
- Receipt OCR inside the MCP (for non-multimodal models) — deferred.
- Recurring entries surfaced inside `generate_report` / charts — optional follow-up.
