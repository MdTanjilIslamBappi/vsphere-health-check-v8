#!/usr/bin/env python3
"""Build a portable single-file vhealth executable with PyInstaller.

This packages the *current platform's* interpreter and dependencies into
one executable under dist/. It does not cross-compile: run it on Windows
to get a Windows .exe, on Linux to get a Linux binary.

Usage:
    uv run python scripts/build_release.py

Status: experimental. See CHANGELOG.md for what has actually been built
and smoke-tested versus merely attempted.
"""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print(
            "PyInstaller is not installed. Install the packaging extras first:\n"
            "    uv sync --group packaging",
            file=sys.stderr,
        )
        return 1

    system = platform.system().lower()
    name = f"vhealth-{system}-{platform.machine().lower()}"

    resources_dir = REPO_ROOT / "src" / "vhealth" / "resources"
    separator = ";" if system == "windows" else ":"
    add_data = f"{resources_dir}{separator}vhealth/resources"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        name,
        "--onefile",
        "--console",
        "--paths",
        str(REPO_ROOT / "src"),
        "--add-data",
        add_data,
        str(REPO_ROOT / "src" / "vhealth" / "cli.py"),
    ]
    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=REPO_ROOT)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
