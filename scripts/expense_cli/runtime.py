"""Cross-platform repo, venv, and Hermes paths."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MCP_DIR = REPO_ROOT / "mcp" / "expense-tracker"
TEMPLATE_DIR = REPO_ROOT / "profiles" / "expense-member"
ENV_PATHS_FILE = REPO_ROOT / ".env.paths"
HERMES_MIN = "0.14.0"


def venv_dir() -> Path:
    return MCP_DIR / ".venv"


def venv_python() -> Path:
    if sys.platform == "win32":
        return venv_dir() / "Scripts" / "python.exe"
    return venv_dir() / "bin" / "python"


def venv_pip() -> Path:
    if sys.platform == "win32":
        return venv_dir() / "Scripts" / "pip.exe"
    return venv_dir() / "bin" / "pip"


def env_path_value(path: Path) -> str:
    """Path string safe for .env files on all platforms."""
    return path.resolve().as_posix()


def find_system_python() -> Path | None:
    for name in ("python3", "python"):
        found = shutil.which(name)
        if found:
            return Path(found)
    if sys.platform == "win32":
        for args in (["py", "-3.12"], ["py", "-3.11"], ["py", "-3"]):
            try:
                result = subprocess.run(
                    [*args, "-c", "import sys; print(sys.executable)"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                exe = result.stdout.strip()
                if exe:
                    return Path(exe)
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
    return None


def hermes_executable() -> str | None:
    return shutil.which("hermes")


def hermes_profiles_dir() -> Path:
    sys.path.insert(0, str(MCP_DIR))
    from expense_tracker.paths import hermes_home

    return hermes_home() / "profiles"


def mcp_env(db_path: Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    parts = [str(MCP_DIR)]
    if env.get("PYTHONPATH"):
        parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(parts)
    if db_path is not None:
        env["EXPENSE_DB_PATH"] = str(db_path)
    return env


def run_hermes(args: list[str], *, quiet: bool = False) -> subprocess.CompletedProcess[str]:
    exe = hermes_executable()
    if not exe:
        raise RuntimeError("hermes not found in PATH")
    return subprocess.run(
        [exe, *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=quiet,
        check=False,
    )
