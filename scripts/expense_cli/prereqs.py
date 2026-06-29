"""Prerequisite checks (Python 3.11+, Hermes >= 0.14.0)."""

from __future__ import annotations

import re
import subprocess
import sys

from .runtime import HERMES_MIN, find_system_python, hermes_executable, run_hermes

RECEIPT_NOTE = "Receipt photo capture requires a vision-capable (multimodal) model in the profile."


def check_python3() -> bool:
    py = find_system_python()
    if not py:
        print("✗ python not found in PATH.", file=sys.stderr)
        print("  Install Python 3.11+ and run the script again.", file=sys.stderr)
        return False
    result = subprocess.run(
        [str(py), "-c", "import sys; print('.'.join(map(str, sys.version_info[:3])))"],
        capture_output=True,
        text=True,
        check=False,
    )
    version = (result.stdout or "").strip() or "?"
    print(f"✓ python {version} ({py})")
    ok = subprocess.run(
        [str(py), "-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"],
        capture_output=True,
        check=False,
    ).returncode == 0
    if not ok:
        print(f"  ⚠ Python 3.11+ recommended (you have {version})", file=sys.stderr)
    return True


def check_hermes() -> bool:
    exe = hermes_executable()
    if not exe:
        print("✗ Hermes CLI not installed or not in PATH.", file=sys.stderr)
        print("  Install Hermes Agent: https://hermes-agent.nousresearch.com", file=sys.stderr)
        return False
    ver_out = subprocess.run([exe, "--version"], capture_output=True, text=True, check=False)
    combined = (ver_out.stdout or "") + (ver_out.stderr or "")
    match = re.search(r"(\d+\.\d+\.\d+)", combined)
    parsed = match.group(1) if match else ""
    if not parsed:
        print("✗ Could not parse Hermes version.", file=sys.stderr)
        return False
    if parsed < HERMES_MIN:
        print(f"✗ Hermes {parsed} is too old. Required >= {HERMES_MIN}.", file=sys.stderr)
        return False
    if run_hermes(["profile", "list"], quiet=True).returncode != 0:
        print("✗ Hermes responds but 'hermes profile list' failed.", file=sys.stderr)
        return False
    print(f"✓ Hermes {parsed} ({exe})")
    return True


def require_prerequisites(*, need_hermes: bool = True) -> bool:
    print("Checking prerequisites...")
    ok = check_python3()
    if need_hermes:
        ok = check_hermes() and ok
    print()
    print(f"ℹ {RECEIPT_NOTE}")
    print()
    if not ok:
        print("Install aborted. Fix prerequisites and try again.", file=sys.stderr)
    return ok
