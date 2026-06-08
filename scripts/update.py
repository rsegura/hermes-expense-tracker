#!/usr/bin/env python3
"""CLI entry: update MCP + all expense-* profiles."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from expense_cli.update import main

if __name__ == "__main__":
    sys.exit(main())
