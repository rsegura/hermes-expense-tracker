<div align="center">

# Hermes Expense Tracker

**Shared household expenses, by chat.**

[Español](docs/es/README.md)

</div>

Each family member gets their own assistant on [Hermes Agent](https://hermes-agent.nousresearch.com) — Telegram, CLI, or other channels — while everyone reads and writes the **same SQLite database**. All business logic lives in a Python MCP server; Hermes profiles only converse and call tools.

**Good fit for:** couples, families, roommates, or any group tracking shared spending without building a custom app.

---

## Before you start

This repo is a **Hermes profile + MCP pack** — not a standalone app. Install [Hermes Agent](https://hermes-agent.nousresearch.com) first (`hermes --version` >= 0.14.0), then clone this repo.

**Platforms:** install scripts run on **macOS, Linux, WSL2, and Windows native** (PowerShell 5.1+). Same Python logic everywhere; pick the launcher for your OS:

| OS | Guided install | Bootstrap / add member / update |
|----|----------------|----------------------------------|
| macOS / Linux / WSL | `./install.sh` | `./bootstrap.sh` · `./add-member.sh` · `./update.sh` |
| Windows (PowerShell) | `.\install.ps1` | `.\bootstrap.ps1` · `.\add-member.ps1` · `.\update.ps1` |

Household data lives under `%USERPROFILE%\.hermes\expense-tracker\` (same layout as `~/.hermes/expense-tracker/`). Override with `HERMES_HOME` if you use a custom Hermes data directory.

---

## Quick start (Hermes already installed)

**macOS / Linux / WSL:**

```bash
git clone https://github.com/Canopix/hermes-expense-tracker.git ~/hermes-expense-tracker
cd ~/hermes-expense-tracker
chmod +x install.sh bootstrap.sh add-member.sh update.sh
./install.sh
```

**Windows (PowerShell):**

```powershell
git clone https://github.com/Canopix/hermes-expense-tracker.git $HOME\hermes-expense-tracker
cd $HOME\hermes-expense-tracker
.\install.ps1
```

The wizard asks for language, sets up the expense server + database, and creates Hermes profiles. **Then per member** (replace `alice` with your slug):

| Step | Command | Expected |
|------|---------|----------|
| 1. Model + API key | `hermes -p alice setup` | Provider configured |
| 2. Verify MCP | `hermes -p expense-alice mcp test expense-tracker` | 44 tools, ✓ Connected |
| 3. Telegram bot | Create bot in [@BotFather](https://t.me/BotFather), then `alice gateway setup && alice gateway start` | Gateway running |
| 4. Pairing | Message your bot → copy code → `hermes -p alice pairing approve telegram <CODE>` | Bot replies in chat |
| 5. First expense | `alice chat` | *"Log $50 at the pharmacy, I paid"* |

**Note:** `alice` is the **shortcut alias**. The Hermes profile name is `expense-alice`. Deleting a profile does **not** delete `~/.hermes/expense-tracker/expenses.db`.

---

## Table of contents

- [Before you start](#before-you-start)
- [Quick start](#quick-start-hermes-already-installed)
- [How it works](#how-it-works)
- [Core concepts](#core-concepts)
- [What you can do](#what-you-can-do)
- [Internationalization (EN + ES)](#internationalization-en--es)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [After install](#after-install--configure-hermes-per-profile)
- [MCP tools reference](#mcp-tools-reference)
- [Repo structure](#repo-structure)
- [Tests](#tests)
- [Update](#update)
- [Troubleshooting](#troubleshooting)

---

## How it works

**Request path** (every message follows the same steps):

1. **Member** — Alice, Bob, or CLI sends a message (Telegram or `alice chat`).
2. **Hermes profile** — `expense-<slug>` loads SOUL + skills from `locales/`, calls only expense MCP tools.
3. **MCP server** — Python FastMCP runs the tool (`add_expense`, `generate_report`, …).
4. **Database** — reads or writes the shared file `~/.hermes/expense-tracker/expenses.db`.

| From | To | How |
|------|-----|-----|
| Member (Telegram, CLI) | Hermes profile | chat / gateway |
| Hermes profile | MCP server | stdio — tools named `mcp_expense_tracker_*` |
| MCP server | SQLite | `EXPENSE_DB_PATH` (same path for every profile) |

| Layer | Role |
|-------|------|
| **Hermes profile** | Chat UI, model, Telegram gateway. Restricted to expense MCP only (`platform_toolsets: [mcp-expense-tracker]`). |
| **SOUL + skills** | Domain guardrails, confirmation format, tool usage patterns. Copied from `locales/en/` or `locales/es/` on install. |
| **MCP server** | CRUD, reports, charts, budgets, project visibility. Single source of truth. |
| **SQLite DB** | Shared across all profiles. Path: `~/.hermes/expense-tracker/expenses.db`. |

**Important:** expense data never goes into Hermes `state.db` or `memories/`. Hermes memory is disabled in the template (`memory.memory_enabled: false`).

Each profile sends two env vars to the MCP:

| Variable | Purpose |
|----------|---------|
| `EXPENSE_MEMBER_SLUG` | Who is calling — filters project visibility and scopes actions |
| `EXPENSE_LOCALE` | Language for report/chart labels (`en` or `es`) |

---

## Core concepts

### Persons

A **person** is anyone who can pay for or be allocated an expense. Members with a bot are created via `add-member.sh`. Others (kids, relatives) can be added by chat: *"Create person Aunt Rosa"*.

### Expenses

Every expense has:

| Field | Meaning |
|-------|---------|
| `paid_by` | Who actually paid (slug) |
| `allocations` | Who the expense counts toward — must sum to 100% |
| `category` | e.g. groceries, transport, health |
| `project` | Optional — home, vacation, wedding, etc. |
| `amount`, `currency`, `date`, `description` | Standard fields |

If you don't specify allocations, the MCP assigns **100% to the payer**.

Example: Alice pays $120 for groceries split 50/50 → `paid_by: alice`, `allocations: [{alice: 50}, {bob: 50}]`.

### Projects

Projects group expenses (home, vacation, health, custom). Each project has an **owner** and optional **members**:

- **Personal** — only the owner sees and logs expenses there
- **Shared** — owner invites others; all members see project expenses in lists and reports

You only see projects you own or were invited to. Expenses without a project are visible to everyone.

### Categories

Seeded at bootstrap (groceries, transport, health, etc.). You can create custom categories by chat. Categories support parent/child hierarchy.

### Budgets

Monthly spending limits per category. The MCP tracks progress and can alert when you're near or over budget (`budget_status`).

### Reports vs raw summaries

- **Summary tools** (`monthly_summary`, etc.) return structured JSON for the agent to format
- **`generate_report`** returns ready-to-send markdown (with optional ASCII bar charts)
- **`render_chart`** returns a PNG image (category breakdown, project breakdown, monthly trend, top expenses)

---

## What you can do

Everything below is done **by chatting** with your bot (or CLI). You never touch SQL or Python.

### Log and manage expenses

| You say | MCP does |
|---------|----------|
| *"Log $80 at the pharmacy, I paid"* | `add_expense` with today's date |
| *"Yesterday's taxi $15, split with Bob"* | `add_expense` + 50/50 allocations |
| *"Show last 10 expenses"* | `list_expenses` (paginated) |
| *"Search farmacia"* | `search_expenses` |
| *"Delete expense #42"* | `delete_expense` (with safety checks) |

### Understand spending

| You say | MCP does |
|---------|----------|
| *"How much in June?"* | `generate_report(period="month", year=2026, month=6)` |
| *"June vs May"* | `compare_months` |
| *"Top 5 expenses this month"* | `top_expenses` |
| *"How much on groceries this year?"* | `category_summary` or filtered report |
| *"What did Alice pay vs what was attributed to her?"* | `person_summary` |

### Projects

| You say | MCP does |
|---------|----------|
| *"Create project Wedding 2027"* | `create_project` (you become owner) |
| *"Invite Bob to vacation project"* | `add_project_member` |
| *"Expenses for home project"* | `project_summary` or filtered `list_expenses` |
| *"Wedding project report"* | `generate_report(period="project", project="wedding")` |

### Charts and export

| You say | MCP does |
|---------|----------|
| *"Category chart for June"* | `render_chart("by_category", ...)` → PNG sent in chat |
| *"Monthly spending trend 2026"* | `render_chart("monthly_trend", year=2026)` |
| *"Export June as CSV"* | `export_expenses_file("csv", start_date=..., end_date=...)` |

### Budgets

| You say | MCP does |
|---------|----------|
| *"Set $500 budget for groceries"* | `set_category_budget` |
| *"Which budgets am I about to break?"* | `budget_status` |
| *"List all budgets"* | `list_category_budgets` |

### Recurring expenses

| You say | MCP does |
|---------|----------|
| *"Create a monthly $200 rent expense"* | `create_recurring_expense` |
| *"Show all my recurring expenses"* | `list_recurring_expenses` |
| *"Which recurring expenses are due today?"* | `list_due_recurring` |
| *"Log this month's rent"* | `generate_recurring_expense` — creates the real expense and advances the schedule |
| *"Change rent amount to $220"* | `update_recurring_expense` |
| *"Remove the streaming subscription"* | `delete_recurring_expense` |

Templates use a `weekly` / `monthly` / `yearly` cadence. Set `suggested_amount: null` for variable amounts (e.g., utilities). Generation is on-demand — no background scheduler runs.

### Receipts (photos)

Send a photo of a receipt in chat and the assistant reads the amount, date, merchant, and category, then logs the expense after you confirm. The receipt image itself is **not stored** — only the resulting expense record is saved to the database.

**Requirement:** the profile's model must be vision-capable (multimodal). If the model cannot process images, receipt capture will not work. Check `hermes -p expense-<slug> config` to confirm which model is in use.

### Household setup (conversational)

| You say | MCP does |
|---------|----------|
| *"Let's set up"* / *"First time"* | `onboarding` skill — projects, budgets, first expense |
| *"Create person Tía Rosa"* | `create_person` (no bot needed) |
| *"Add category Pets"* | `create_category` |

---

## Internationalization (EN + ES)

During `./install.sh`, the wizard **always asks** for household language first (`English` or `Español`).

| Layer | Language |
|-------|----------|
| Code, tests, MCP errors | English (canonical) |
| `README.md`, `docs/en/` | English |
| `docs/es/` | Spanish |
| Agent SOUL + skills | `locales/en/` or `locales/es/` |
| Reports + chart labels | `EXPENSE_LOCALE` (`en` \| `es`) |
| Expense descriptions in DB | Whatever you type in chat |
| Default category **names** | Seeded at first bootstrap in household locale (`shared/seed-categories-en.sql` / `-es.sql`) |
| Category **slugs** | Same in all locales (`supermercado`, `transporte`, …) — stable MCP identifiers |

- Locale is stored in `~/.hermes/expense-tracker/locale` and in each profile `.env` as `EXPENSE_LOCALE`.
- Database path is stored in `~/.hermes/expense-tracker/db-path` (default `~/.hermes/expense-tracker/expenses.db`). The install wizard lets you confirm or change it. Both paths honor `HERMES_HOME` when set.
- Manual install: `EXPENSE_LOCALE=en EXPENSE_DB_PATH=~/.hermes/expense-tracker/expenses.db ./bootstrap.sh`
- Existing installs without locale default to **Spanish** on `./update.sh` (legacy behavior).

**Docs:** [`docs/en/`](docs/en/README.md) · [`docs/es/`](docs/es/README.md) · Technical briefing: [`docs/en/BRIEFING.md`](docs/en/BRIEFING.md)

---

## Prerequisites

- [Hermes Agent](https://hermes-agent.nousresearch.com) installed (`hermes --version` >= 0.14.0)
- Python 3.11+
- LLM API key (OpenRouter, your own endpoint, etc.)
- One Telegram bot **per person** who wants to chat (via [@BotFather](https://t.me/BotFather))

---

## Installation

### Option A — Guided (recommended)

Terminal wizard with Rich panels: prerequisites, short prompts, no `pip` spam.

**macOS / Linux / WSL:**

```bash
git clone https://github.com/Canopix/hermes-expense-tracker.git ~/hermes-expense-tracker
cd ~/hermes-expense-tracker
chmod +x install.sh bootstrap.sh add-member.sh update.sh
./install.sh
```

**Windows (PowerShell):**

```powershell
git clone https://github.com/Canopix/hermes-expense-tracker.git $HOME\hermes-expense-tracker
cd $HOME\hermes-expense-tracker
.\install.ps1
```

The wizard:

1. Asks **household language** (English / Español)
2. Shows the **shared database path** (default `~/.hermes/expense-tracker/expenses.db`) — press Enter to keep it or type another file/folder
3. Checks Python + Hermes (with progress indicators)
4. **First install:** sets up expense server + database at that path  
5. **Existing database:** skips server setup, keeps your data, goes straight to members  
6. Asks how many members get their own bot, name + slug per member
7. Optional people without a bot, optional starter projects

To refresh after `git pull`, use `./update.sh` or `.\update.ps1` on Windows — not the install wizard.

> Hand off to another AI: [`docs/en/TO-INSTALL.md`](docs/en/TO-INSTALL.md) · [`docs/es/PARA-INSTALAR.md`](docs/es/PARA-INSTALAR.md)

### Option B — Manual

```bash
EXPENSE_LOCALE=en EXPENSE_DB_PATH=~/.hermes/expense-tracker/expenses.db ./bootstrap.sh
EXPENSE_LOCALE=en ./add-member.sh alice Alice
EXPENSE_LOCALE=en ./add-member.sh bob Bob
```

| Script | What it does |
|--------|--------------|
| `bootstrap.sh` | MCP Python venv + schema + default categories (uses `EXPENSE_LOCALE`, default `es`) |
| `add-member.sh` | Person in DB + Hermes profile + SOUL/skills from `locales/${EXPENSE_LOCALE}/` |

This product **does not** ask for API keys or Telegram tokens in `install.sh`. That is configured in Hermes per profile.

---

## After install — configure Hermes (per profile)

`add-member.sh` creates `~/.hermes/profiles/expense-<slug>/` and a command alias `<slug>`:

```bash
alice gateway          # same as hermes -p expense-alice gateway
hermes -p expense-alice chat   # full profile name also works
hermes -p alice chat           # shortcut alias
```

**Post-install order (each member):**

| Step | Command | Notes |
|------|---------|-------|
| 1 | `hermes -p alice setup` | Model + API key |
| 2 | `hermes -p expense-alice mcp test expense-tracker` | Must show 44 tools |
| 3 | [@BotFather](https://t.me/BotFather) → new bot → `alice gateway setup` | Paste bot token |
| 4 | `alice gateway start` | Keep gateway running |
| 5 | Message bot in Telegram → `hermes -p alice pairing approve telegram <CODE>` | Code appears when you first message the bot |
| 6 | `alice chat` | Try logging an expense |

**What each layer configures:**

| What | Where | How |
|------|-------|-----|
| MCP paths (`EXPENSE_*`) | Profile `.env` | `add-member.sh` writes them; `config.yaml` resolves `${...}` |
| `EXPENSE_MEMBER_SLUG` | Profile `.env` | Set automatically per member |
| `EXPENSE_LOCALE` | Profile `.env` + MCP env | From install wizard or manual |
| Model / provider / API key | `config.yaml` | `hermes setup` or edit manually |
| Telegram, gateway, pairing | `config.yaml` + gateway | `<slug> gateway setup` |
| SOUL, skills, toolsets | Installed profile | Copied from `locales/` on install |

### Telegram UX (quiet)

The `expense-member` template is configured for a clean chat:

| Setting | Effect |
|---------|--------|
| `display.tool_progress: off` | No `⚙️ mcp_expense_tracker_*` messages |
| `display.interim_assistant_messages: false` | No interim narration ("Creating category...") |
| `telegram.reactions: true` | 👀 while processing, 👍 when done |
| SOUL + skill | Structured confirmation (`Done ✅` + bullets), no tool narration |

**Member slug:** short name only (`alice`, `bob`). **Do not** use `expense-alice` — `add-member.sh` adds the `expense-` prefix to the Hermes profile name.

New installs inherit UX from the template. `add-member.sh` always re-personalizes SOUL (also after `profile update`).

### Conversational onboarding

With MCP connected, the first chat can guide projects, budgets, and the first expense:

```bash
alice chat
# "Let's set up" / "First time"
```

The `onboarding` skill asks one question at a time. It **does not** create profiles or bots — that is `install.sh` / `add-member.sh`.

### People without a bot

If someone participates in expenses but does not chat:

- From any profile: *"Create person Aunt Rosa"*
- Agent calls `create_person`
- They appear in DB for allocations and reports
- **No** `./add-member.sh` or Telegram bot required

---

## MCP tools reference

**44 tools.** Hermes exposes them as `mcp_expense_tracker_<tool>`.

### Persons

| Tool | Description |
|------|-------------|
| `create_person` | Add someone who appears in expenses but may not have a bot |
| `update_person` | Change display name or aliases |
| `list_persons` | All people in the household DB |
| `delete_person` | Only if no expenses reference them |

### Projects (with membership)

| Tool | Description |
|------|-------------|
| `create_project` | New project; caller = owner; optional `members` slugs |
| `update_project` | Rename, describe, archive |
| `list_projects` | Only projects visible to caller |
| `add_project_member` / `remove_project_member` | Owner only |
| `list_project_members` | Must be a member |
| `delete_project` | Owner only; `force=true` unlinks expenses |

**Visibility rules:**

- Personal project → only owner
- Shared project → owner + invited members
- No project → everyone sees the expense
- Caller cannot list or report on projects they don't belong to

### Categories

| Tool | Description |
|------|-------------|
| `create_category` / `update_category` / `list_categories` | CRUD; supports `parent_slug` hierarchy |
| `delete_category` | Reassign expenses first via `reassign_to` |

### Expenses

| Tool | Description |
|------|-------------|
| `add_expense` | Core write — date, amount, category, payer, optional project, allocations |
| `update_expense` / `delete_expense` | Edit or remove |
| `list_expenses` | Paginated list with filters (date, category, project, person, currency) |
| `search_expenses` | Full-text search on description + notes |

Pagination shape: `{ items, total_count, has_more, offset }`.

### Reports (structured data)

| Tool | Returns |
|------|---------|
| `monthly_summary` | Totals + breakdowns by category, project, person |
| `yearly_summary` | By month, category, project |
| `project_summary` | All expenses and totals for one project |
| `category_summary` | Spending for one category over time |
| `person_summary` | Paid total vs attributed total per person |

All report tools accept filters: `category`, `project`, `paid_by`, `allocated_to`, `currency`.

### Comparison, export, and presentation

| Tool | Description |
|------|-------------|
| `compare_months` | Side-by-side two months |
| `compare_periods` | Arbitrary date ranges |
| `top_expenses` | Largest expenses in a period |
| `export_expenses` | JSON/CSV data in response |
| `export_expenses_file` | Writes CSV/JSON to disk, returns path |
| `generate_report` | Markdown report with optional ASCII charts (locale-aware) |
| `render_chart` | PNG chart via matplotlib — `by_category`, `by_project`, `monthly_trend`, `top_expenses` |

### Recurring expenses

| Tool | Description |
|------|-------------|
| `create_recurring_expense` | Define a recurring template (`weekly` / `monthly` / `yearly`); `suggested_amount: null` = variable amount |
| `update_recurring_expense` | Edit a template; changing cadence or start date resets the next due date |
| `delete_recurring_expense` | Deactivates if it has generated expenses; hard-deletes otherwise |
| `list_recurring_expenses` | All household templates with their next due date |
| `list_due_recurring` | Templates whose `next_due_date` is on or before today |
| `generate_recurring_expense` | Materialize one occurrence into a real expense and advance the schedule |

Generation is lazy and on-demand — no background scheduler. Each call to `generate_recurring_expense` creates one real expense and moves the template's `next_due_date` forward by one period.

### Budgets

| Tool | Description |
|------|-------------|
| `set_category_budget` | Monthly limit for a category |
| `update_category_budget` / `delete_category_budget` | Modify or remove |
| `list_category_budgets` | All active budgets |
| `budget_status` | Progress and alerts (near/over limit) |

### Utility

| Tool | Description |
|------|-------------|
| `health_check` | DB reachable, schema version, basic stats |

---

## What you touch vs what you don't

| Action | Code? | How |
|--------|-------|-----|
| Install | No | `git clone` + `./install.sh` or `./bootstrap.sh` |
| Member with chat | No | `EXPENSE_LOCALE=en ./add-member.sh <slug> <name>` |
| Model / API key | No | Profile `config.yaml` or `hermes setup` |
| Telegram | No | `gateway setup` + BotFather |
| Pairing | No | `hermes -p <slug> pairing approve telegram CODE` |
| Person expenses-only | No | Ask the bot "create person X" |
| Household projects | No | Ask the bot "create project vacation" |
| Category budgets | No | Ask the bot or `set_category_budget` |
| Update everything | No | `./update.sh` or `.\update.ps1` (MCP + skills + SOUL) |

**Never overwritten on updates:** `.env`, `memories/`, `sessions/`, `state.db`, `pairing/`.

---

## Where things live

| Component | Location |
|-----------|----------|
| Repo (MCP + template) | `~/hermes-expense-tracker/` |
| Hermes profiles (runtime) | `~/.hermes/profiles/expense-<slug>/` (commands: alias `<slug>`) |
| Shared database | `~/.hermes/expense-tracker/expenses.db` (override via wizard or `db-path`) |
| Exports / charts | `~/.hermes/expense-tracker/exports/`, `charts/` (next to the DB file) |
| Household locale | `~/.hermes/expense-tracker/locale` |
| Localized agent copy | `~/hermes-expense-tracker/locales/{en,es}/` |
| Profile config | `~/.hermes/profiles/expense-<slug>/config.yaml` |

---

## Repo structure

```
hermes-expense-tracker/
├── README.md                 # this file (English, canonical)
├── LICENSE
├── CONTRIBUTING.md
├── install.sh                # guided wizard (Unix)
├── install.ps1               # guided wizard (Windows)
├── bootstrap.sh / bootstrap.ps1
├── add-member.sh / add-member.ps1
├── update.sh / update.ps1
├── locales/
│   ├── en/                   # SOUL.md + skills/ (English agent)
│   └── es/                   # SOUL.md + skills/ (Spanish agent)
├── docs/
│   ├── en/                   # BRIEFING, TO-INSTALL, index
│   └── es/                   # README, BRIEFING, PARA-INSTALAR
├── scripts/
│   ├── install_wizard.py     # Rich TUI installer
│   ├── bootstrap.py          # CLI → expense_cli.bootstrap
│   ├── add_member.py         # CLI → expense_cli.add_member
│   ├── update.py             # CLI → expense_cli.update
│   ├── expense_cli/          # cross-platform install logic (Python)
│   ├── smoke-test.sh
│   └── lib/                  # legacy bash helpers (optional; logic lives in expense_cli/)
├── shared/seed-categories-en.sql
├── shared/seed-categories-es.sql
├── mcp/expense-tracker/
│   ├── server.py             # 44 FastMCP tool definitions
│   ├── manifest.yaml
│   └── expense_tracker/
│       ├── repositories.py   # business logic + DB access
│       ├── reports.py        # generate_report, render_chart, export
│       ├── paths.py          # ~/.hermes/expense-tracker defaults
│       └── i18n.py           # report/chart strings (en/es)
└── profiles/
    └── expense-member/       # Hermes shell template (config, mcp.json — no full SOUL)
```

---

## Tests

```bash
cd mcp/expense-tracker
.venv/bin/python -m unittest discover -s tests -v
```

Covers repositories, project membership, reports, i18n, and end-to-end flows.

---

## Update

```bash
cd ~/hermes-expense-tracker
git pull                    # if using git
./update.sh                 # bootstrap + all expense-* profiles
```

`update.sh`:

1. Rebuilds MCP venv if needed
2. Runs DB migrations (e.g. project membership)
3. `hermes profile update` on each `expense-*` profile
4. Re-applies SOUL/skills via `add-member`
5. Restarts gateways if running

After updating:

```bash
./scripts/smoke-test.sh expense-alice
```

Duplicate profile name (`expense-expense-alice`): delete the bad profile, then recreate the member (DB is untouched):

```bash
hermes profile delete expense-expense-alice
EXPENSE_LOCALE=en ./add-member.sh alice Alice
```

Copy `config.yaml` / `.env` from the old folder manually if you need tokens or model settings before deleting.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| MCP won't connect | `hermes -p expense-<slug> mcp test expense-tracker`; check `EXPENSE_*` in profile `.env` |
| Deleted profile, want data back | DB at `~/.hermes/expense-tracker/expenses.db` is kept — run `EXPENSE_LOCALE=es ./add-member.sh <slug> <name>` |
| Different expenses per profile | `EXPENSE_DB_PATH` must be **identical** in all profiles |
| Telegram not responding | `<slug> gateway status`; check token and `allow_from` |
| Pairing rejected | `hermes -p <slug> pairing approve telegram CODE` (use `-p`) |
| Agent answers off-topic | Check `platform_toolsets: [mcp-expense-tracker]` in `config.yaml` |
| Person missing when logging expense | `./add-member.sh` or `create_person` from the bot |
| Profile `expense-expense-*` | `hermes profile delete <bad-profile>` then `./add-member.sh <slug> <name>` (copy `.env` first if needed) |
| SOUL still has `{{MEMBER_NAME}}` | `./add-member.sh <slug> <name>` or `./update.sh` |
| Reports in wrong language | Set `EXPENSE_LOCALE=en` or `es` in profile `.env`, then `./update.sh` |
| Project expenses invisible | Check project membership — caller must be owner or invited |
| Charts not sending in Telegram | Agent must attach the PNG path from `render_chart` |

---

## Further reading

| Doc | Audience |
|-----|----------|
| [`docs/en/BRIEFING.md`](docs/en/BRIEFING.md) | Contributors — architecture, seed strategy, tool list |
| [`docs/es/README.md`](docs/es/README.md) | Spanish version of this guide |
| [`docs/en/TO-INSTALL.md`](docs/en/TO-INSTALL.md) | Hand off install to another AI |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | How to contribute and run tests |
| [`locales/en/skills/expense-tracker/SKILL.md`](locales/en/skills/expense-tracker/SKILL.md) | Agent tool usage reference |
