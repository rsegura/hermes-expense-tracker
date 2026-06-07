# Onboarding — Expense Tracker

Skill for **first-time household setup**. Use when the user wants to start, configure, install, or says "first time".

## Important limits

**You have no terminal.** You cannot run `install.sh`, `add-member.sh`, or `hermes profile install`.

| What | Who does it |
|------|-------------|
| MCP, DB, Hermes profiles, Telegram bots | Terminal: `./install.sh` or `./add-member.sh` |
| Persons without a bot | You: `create_person` |
| Projects, budgets, first expense | You: MCP tools |

If `health_check` shows `persons: 0`, explain that `./install.sh` must run on the machine first.

## Guided flow (one question per turn)

1. **`health_check`** — confirm MCP and DB.
2. **`list_persons`** — if empty, point to `./install.sh`; otherwise greet by name.
3. **`list_projects`** — if empty or few, ask what projects to track → `create_project` for each.
4. **Budgets (optional)** — `set_category_budget` if they want monthly limits.
5. **First expense** — `add_expense` and confirm summary.
6. **Close** — mention `generate_report`, `render_chart`, Telegram pairing.

## Tone

- Brief, one question at a time.
- If already configured, skip onboarding — switch to normal expense mode.
