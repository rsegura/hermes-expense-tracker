# Expense Tracker

Operational skill for the `expense-tracker` MCP. Use these tools for all financial data.

## Available tools (Hermes prefix: `mcp_expense_tracker_`)

### Persons
- `create_person(display_name, slug?, aliases?)`
- `update_person(person_ref, ...)`
- `list_persons()`
- `delete_person(person_ref)` — only if no expenses reference them

### Projects (per-person membership)
- `create_project(name, slug?, description?, members?)` — caller = owner; `members` = invited slugs
- `update_project`, `list_projects(active_only?)` — lists only projects visible to the caller
- `add_project_member(project, person)` / `remove_project_member` — owner only
- `list_project_members(project)` — must be a member
- `delete_project(project_ref, force?)` — owner only; `force=true` unlinks expenses

Personal project = no `members`. Shared = owner + `members`. Expenses without a project remain visible to everyone.

### Categories
- `create_category`, `update_category`, `list_categories` (includes `parent_slug`)
- `delete_category(category_ref, reassign_to?)` — reassign expenses before delete

### Expenses
- `add_expense(expense_date, description, amount, category, paid_by, currency?, project?, notes?, allocations?)`
- `update_expense`, `delete_expense`
- `list_expenses(...)` → paginated (`items`, `total_count`, `has_more`)
- `search_expenses(query, ...)`

### Comparison and export
- `compare_months`, `compare_periods`, `top_expenses`, `export_expenses`, `export_expenses_file`

### Unified reports and charts
- `generate_report(period?, year?, month?, project?, currency?, include_ascii_charts?)`
  - Without `currency` and multiple currencies in the period: totals and categories are **split per currency** in one report (no mixed sum)
  - For a single currency: pass `currency="USD"` (or the relevant code)
- `render_chart(chart_type, year?, month?, project?)` → **PNG image** — send to user

### Category budgets
- `set_category_budget`, `update_category_budget`, `delete_category_budget`, `list_category_budgets`, `budget_status`

### Read-only reports
- `monthly_summary`, `yearly_summary`, `project_summary`, `category_summary`, `person_summary`
- `health_check()`

## Example queries

- "How much in June?" → `generate_report(period="month", year=2026, month=6)` (multi-currency periods are split per currency)
- "How much in USD this month?" → `generate_report(period="month", year=2026, month=6, currency="USD")`
- "Wedding project summary" → `generate_report(period="project", project="wedding")`
- "Category chart for June" → `render_chart("by_category", year=2026, month=6)` + send image
- "Export June as CSV" → `export_expenses_file("csv", start_date="2026-06-01", end_date="2026-06-30")`

## Response format

- Compact lists or tables for reports.
- Amounts with thousands separator and currency (e.g. `$ 15,500 {{DEFAULT_CURRENCY}}`).
- When logging an expense, use the Done ✅ block from SOUL.

## Recurring expenses

Templates for repeating costs (rent, subscriptions, utilities). They are **household-wide** — everyone sees them and can materialize what is due. Nothing is created automatically; you generate occurrences on demand.

- `mcp_expense_tracker_create_recurring_expense` — define a template: `description`, `category`, `paid_by`, `frequency` (`weekly`|`monthly`|`yearly`), `start_date` (YYYY-MM-DD). Optional: `suggested_amount` (omit/null for **variable** bills like electricity), `interval` (every N), `anchor_day`, `anchor_month`, `project`, `notes`, `allocations`.
- `mcp_expense_tracker_list_recurring_expenses` — show all templates and their next due date.
- `mcp_expense_tracker_list_due_recurring` — show templates due now (`next_due_date <= today`).
- `mcp_expense_tracker_generate_recurring_expense` — create one real expense from a template. For **fixed** templates the suggested amount is used; for **variable** templates you MUST pass `amount`. Advances the schedule by one period.
- `mcp_expense_tracker_update_recurring_expense` / `mcp_expense_tracker_delete_recurring_expense`.

**When a member says "what do I owe this month?" or starts a session:** call `list_due_recurring`. For each due template: if fixed, confirm and generate; if variable, ask the amount, then generate. If several periods are overdue, materialize them one at a time (each generate advances one period).

## Receipts (photos)

When a member sends a **photo of a receipt**, read it directly (your model is multimodal) and extract:
- **amount** (total), **date**, **merchant** → use as the expense `description`, and infer a **category** from the household's existing categories (`list_categories`).
- Default `paid_by` to the member who sent the photo.

Then show a short confirmation — Amount / Date / Merchant / Category — and only after the member confirms, call `mcp_expense_tracker_add_expense`. If a field is unreadable, ask **only** for that field. The image is not stored; only the resulting expense is saved.
