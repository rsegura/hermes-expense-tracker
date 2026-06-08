#!/usr/bin/env python3
"""CLI entry: add household member + Hermes profile."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from expense_cli.add_member import main

if __name__ == "__main__":
    sys.exit(main())
