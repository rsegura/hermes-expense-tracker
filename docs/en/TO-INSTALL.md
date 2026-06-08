# Install instructions (copy to another AI or person)

Use this text when asking someone (or an agent with terminal access) to install the product on a machine with Hermes.

---

## Goal

Install **Hermes Expense Tracker**: shared household expenses. Each member can have their own Telegram bot; everyone shares one SQLite database.

## Requirements

- Python 3.11+ (`python3`, `python`, or Windows `py`)
- [Hermes Agent](https://hermes-agent.nousresearch.com) >= 0.14.0 on PATH (`hermes --version`)
- macOS, Linux, WSL2, or **Windows native** (PowerShell 5.1+)
- Model and Telegram are configured **after** install in each Hermes profile — not part of the installer

## Steps (Unix — bash)

```bash
cd ~
git clone https://github.com/Canopix/hermes-expense-tracker.git hermes-expense-tracker
cd hermes-expense-tracker
chmod +x install.sh bootstrap.sh add-member.sh update.sh
./install.sh
```

## Steps (Windows — PowerShell)

```powershell
cd $HOME
git clone https://github.com/Canopix/hermes-expense-tracker.git hermes-expense-tracker
cd hermes-expense-tracker
.\install.ps1
```

The wizard:

1. Asks **household language** (English / Español)
2. Shows the **shared database path** (default `~/.hermes/expense-tracker/expenses.db`) — Enter to keep, or type another path
3. Checks Python + Hermes (with spinners — uses Rich, like Hermes CLI)
4. On **first install**, sets up the expense server + database at that path (no confusing “bootstrap” question)
5. On **reinstall**, reuses existing database if present
6. Asks how many members, name + slug each
7. Optional people without bot, optional starter projects

## After install (each member, in order)

| Step | Command |
|------|---------|
| 1. Model | `hermes -p alice setup` |
| 2. MCP test | `hermes -p expense-alice mcp test expense-tracker` |
| 3. Telegram | [@BotFather](https://t.me/BotFather) → `alice gateway setup` then `alice gateway start` (Windows: run both commands; Unix: `&&` ok) |
| 4. Pairing | Message bot → `hermes -p alice pairing approve telegram <CODE>` |
| 5. Chat | `alice chat` |

Deleting a Hermes profile does **not** delete the expense database (default `~/.hermes/expense-tracker/expenses.db`, or your custom path in `~/.hermes/expense-tracker/db-path`).

## Onboarding in Hermes (conversational)

When MCP is working:

```bash
alice chat
```

Say: *"Let's set up"* or *"First time"*.

## Verification (developers)

```bash
cd ~/hermes-expense-tracker/mcp/expense-tracker
.venv/bin/python -m unittest discover -s tests -v
```

## Do not

- Do not commit profile secrets or Telegram tokens
- Do not put household expense data in the git repo (only in `~/.hermes/expense-tracker/expenses.db`)
