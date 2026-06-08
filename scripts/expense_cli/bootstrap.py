"""Bootstrap MCP venv and optional shared database."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .locale_util import resolve_expense_locale
from .paths_util import resolve_expense_db_path, write_env_paths
from .runtime import MCP_DIR, REPO_ROOT, find_system_python, mcp_env, venv_dir, venv_pip, venv_python


def log(message: str, *, quiet: bool) -> None:
    if not quiet:
        print(message)


def run_bootstrap(
    *,
    quiet: bool = False,
    bootstrap_db: bool = True,
    locale: str | None = None,
    db_path: Path | None = None,
) -> int:
    py = find_system_python()
    if not py:
        print("python is required", file=sys.stderr)
        return 1

    resolved_db = db_path if db_path is not None else resolve_expense_db_path()

    log("==> Hermes Expense Tracker bootstrap", quiet=quiet)
    log(f"    Repo: {REPO_ROOT}", quiet=quiet)
    log("==> Creating MCP virtualenv", quiet=quiet)

    venv_dir().mkdir(parents=True, exist_ok=True)
    subprocess.run([str(py), "-m", "venv", str(venv_dir())], check=True, cwd=REPO_ROOT)

    pip = venv_pip()
    pip_args = [str(pip), "install"]
    if quiet:
        pip_args.extend(["-q", "--upgrade", "pip"])
    else:
        pip_args.extend(["--upgrade", "pip"])
    subprocess.run(pip_args, check=True, cwd=REPO_ROOT)

    req_args = [str(pip), "install"]
    if quiet:
        req_args.append("-q")
    req_args.extend(["-r", str(MCP_DIR / "requirements.txt")])
    subprocess.run(req_args, check=True, cwd=REPO_ROOT)

    if bootstrap_db:
        loc = locale or resolve_expense_locale(required=False) or "es"
        if loc not in ("en", "es"):
            loc = "es"
        resolved_db.parent.mkdir(parents=True, exist_ok=True)
        log(
            f"==> Initializing shared database at {resolved_db} (schema + categories, locale={loc})",
            quiet=quiet,
        )
        env = mcp_env(resolved_db)
        code = f'from expense_tracker.db import init_db\ninit_db(seed="categories", locale="{loc}")\n'
        result = subprocess.run(
            [str(venv_python()), "-c", code],
            env=env,
            cwd=REPO_ROOT,
            check=False,
        )
        if result.returncode != 0:
            return result.returncode

    write_env_paths(resolved_db)

    if not quiet:
        if bootstrap_db:
            print(f"==> Database ready: {resolved_db}")
        print(f"==> Wrote path variables to {REPO_ROOT / '.env.paths'}")
        print()
        install_cmd = ".\\install.ps1" if sys.platform == "win32" else "./install.sh"
        print("Next steps:")
        print(f"  1. {install_cmd}")
        print("  2. Hermes: hermes setup or profile config.yaml (model)")
        print("  3. <slug> gateway setup && <slug> gateway start")
    return 0


def main(argv: list[str] | None = None) -> int:
    _ = argv
    quiet = os.environ.get("QUIET", "").strip() != ""
    bootstrap_db = os.environ.get("BOOTSTRAP_DB", "1") != "0"
    locale = os.environ.get("EXPENSE_LOCALE", "").strip() or None
    db_raw = os.environ.get("EXPENSE_DB_PATH", "").strip()
    db_path = Path(os.path.expanduser(db_raw)).resolve() if db_raw else None
    return run_bootstrap(quiet=quiet, bootstrap_db=bootstrap_db, locale=locale, db_path=db_path)


if __name__ == "__main__":
    sys.exit(main())
