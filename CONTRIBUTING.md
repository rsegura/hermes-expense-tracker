# Contributing

Thanks for your interest in [Hermes Expense Tracker](https://github.com/Canopix/hermes-expense-tracker).

## Before you start

- Read [`docs/en/BRIEFING.md`](docs/en/BRIEFING.md) for architecture and conventions.
- MCP code and tests stay in **English**; user-facing agent copy lives in `locales/en/` and `locales/es/`.
- Run tests before opening a PR:

```bash
cd mcp/expense-tracker
.venv/bin/python -m unittest discover -s tests -v
```

## Pull requests

1. Fork and branch from `main`.
2. Keep changes focused — one feature or fix per PR.
3. Update README or `docs/` if behavior or install steps change.
4. Do not commit secrets, `.env`, `.env.paths`, or personal profile data.

## Reporting issues

Include:

- OS and Python version
- `hermes --version`
- Steps to reproduce
- Relevant output from `hermes -p <profile> mcp test expense-tracker`

## i18n

- New user-facing strings for reports/charts → `mcp/expense-tracker/expense_tracker/i18n.py`
- Agent SOUL/skills → both `locales/en/` and `locales/es/`
- Install wizard UI → `scripts/wizard_i18n.py`
