"""Tests for cross-platform install runtime helpers."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from expense_cli.runtime import venv_pip, venv_python  # noqa: E402


class RuntimeTests(unittest.TestCase):
    def test_unix_venv_paths(self) -> None:
        with mock.patch("expense_cli.runtime.sys.platform", "linux"):
            self.assertEqual(venv_python().name, "python")
            self.assertIn("bin", str(venv_python()))
            self.assertIn("bin", str(venv_pip()))

    def test_windows_venv_paths(self) -> None:
        with mock.patch("expense_cli.runtime.sys.platform", "win32"):
            self.assertEqual(venv_python().name, "python.exe")
            self.assertIn("Scripts", str(venv_python()))
            self.assertEqual(venv_pip().name, "pip.exe")


if __name__ == "__main__":
    unittest.main()
