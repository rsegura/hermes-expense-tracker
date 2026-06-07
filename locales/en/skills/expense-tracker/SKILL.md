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
- `generate_report(period?, year?, month?, project?, include_ascii_charts?)`
- `render_chart(chart_type, year?, month?, project?)` → **PNG image** — send to user

### Category budgets
- `set_category_budget`, `update_category_budget`, `delete_category_budget`, `list_category_budgets`, `budget_status`

### Read-only reports
- `monthly_summary`, `yearly_summary`, `project_summary`, `category_summary`, `person_summary`
- `health_check()`

## Example queries

- "How much in June?" → `generate_report(period="month", year=2026, month=6)`
- "Wedding project summary" → `generate_report(period="project", project="wedding")`
- "Category chart for June" → `render_chart("by_category", year=2026, month=6)` + send image
- "Export June as CSV" → `export_expenses_file("csv", start_date="2026-06-01", end_date="2026-06-30")`

## Response format

- Compact lists or tables for reports.
- Amounts with thousands separator and currency (e.g. `$ 15,500 ARS`).
- When logging an expense, use the Done ✅ block from SOUL.
