"""Update MCP and refresh all expense-* Hermes profiles."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .bootstrap import run_bootstrap
from .currency_util import resolve_expense_currency, save_household_currency
from .locale_util import resolve_expense_locale, save_household_locale
from .paths_util import resolve_expense_db_path
from .runtime import MCP_DIR, hermes_profiles_dir, mcp_env, run_hermes, venv_python
from .add_member import run_add_member


def _profile_locale(profile_dir: Path) -> str:
    from expense_tracker.paths import locale_file

    env_file = profile_dir / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("EXPENSE_LOCALE="):
                loc = line.split("=", 1)[1].strip()
                if loc in ("en", "es"):
                    return loc
    path = locale_file()
    if path.exists():
        loc = path.read_text(encoding="utf-8").strip()
        if loc in ("en", "es"):
            return loc
    return "es"


def _display_name(slug: str, db_path: Path) -> str:
    venv_py = venv_python()
    code = f"""
import os, sys
sys.path.insert(0, {str(MCP_DIR)!r})
os.environ["EXPENSE_DB_PATH"] = {str(db_path)!r}
from expense_tracker import repositories as repo
from expense_tracker.db import init_db
init_db(seed=False)
slug = {slug!r}
for p in repo.list_persons():
    if p["slug"] == slug:
        print(p["display_name"])
        break
else:
    print(slug.capitalize())
"""
    import subprocess

    result = subprocess.run(
        [str(venv_py), "-c", code],
        env=mcp_env(db_path),
        capture_output=True,
        text=True,
        check=False,
    )
    return (result.stdout or "").strip() or slug.capitalize()


def run_update() -> int:
    print("==> Hermes Expense Tracker — update")
    print()

    print("==> Bootstrap MCP")
    code = run_bootstrap(quiet=True, bootstrap_db=False)
    if code != 0:
        return code

    venv_py = venv_python()
    if not venv_py.exists():
        print("MCP venv missing after bootstrap.", file=sys.stderr)
        return 1

    db_path = resolve_expense_db_path()
    locale_for_currency = resolve_expense_locale(required=False) or "en"
    sys.path.insert(0, str(MCP_DIR))
    from expense_tracker.paths import currency_file

    if not currency_file().exists():
        save_household_currency("ARS" if locale_for_currency == "es" else "USD")
    currency = resolve_expense_currency() or "USD"

    print()
    print("==> DB migrations (project members)")
    import subprocess

    mig = subprocess.run(
        [str(venv_py), "-c", "from expense_tracker.db import init_db\ninit_db(seed=False)\nprint('migrations ok')"],
        env=mcp_env(db_path),
        cwd=MCP_DIR.parent.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    if mig.returncode != 0:
        print(mig.stderr or mig.stdout, file=sys.stderr)
        return mig.returncode
    print((mig.stdout or "").strip() or "migrations ok")

    profiles_dir = hermes_profiles_dir()
    if not profiles_dir.is_dir():
        print(f"No profiles in {profiles_dir}", file=sys.stderr)
        return 0

    for profile_dir in sorted(profiles_dir.glob("expense-*")):
        if not profile_dir.is_dir():
            continue
        profile = profile_dir.name
        slug = profile.removeprefix("expense-")
        if slug.startswith("expense-"):
            inner = slug.removeprefix("expense-")
            print(f"⚠ Saltando perfil mal formado: {profile}")
            add_cmd = ".\\add-member.ps1" if sys.platform == "win32" else "./add-member.sh"
            print(f"  Borrá el perfil: hermes profile delete {profile}")
            print(f"  Recreá: {add_cmd} {inner} <nombre>")
            continue

        print()
        print(f"── {profile} ──")
        display_name = _display_name(slug, db_path)
        locale = _profile_locale(profile_dir)
        save_household_locale(locale)

        upd = run_hermes(["profile", "update", profile, "-y"], quiet=False)
        if upd.returncode != 0:
            return upd.returncode

        os.environ["EXPENSE_LOCALE"] = locale
        os.environ["EXPENSE_DEFAULT_CURRENCY"] = currency
        os.environ["INSTALL_QUIET"] = "1"
        os.environ["SKIP_PREREQ"] = "1"
        code = run_add_member(slug, display_name, quiet=True, skip_prereq=True)
        if code != 0:
            return code

        status = run_hermes(["-p", profile, "gateway", "status"], quiet=True)
        if status.returncode == 0:
            run_hermes(["-p", profile, "gateway", "restart"], quiet=True)
            print(f"✓ {profile} ({display_name}) — gateway restarted")
        else:
            print(f"✓ {profile} ({display_name}) — gateway not running")

    print()
    smoke = ".\\scripts\\smoke-test.ps1 expense-alice" if sys.platform == "win32" else "./scripts/smoke-test.sh expense-alice"
    print("Update listo. Probar:")
    print(f"  {smoke}")
    return 0


def main() -> int:
    return run_update()


if __name__ == "__main__":
    sys.exit(main())
