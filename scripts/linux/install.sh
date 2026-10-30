#!/usr/bin/env bash
# Installs vhealth into a project-local virtual environment on Linux/macOS.
#
# Creates .venv (or the directory named by $1), installs dependencies from
# the committed uv.lock, installs vhealth into it, and verifies the CLI
# works. Safe to run repeatedly. Does not require root and never touches
# global/system Python packages.
#
# If you access this same checkout from both Windows and WSL/Linux (e.g.
# C:\path and /mnt/c/path are the same folder), pass a different directory
# name here so the two OSes don't fight over one .venv -- a Windows venv
# and a Linux venv cannot be the same directory:
#   ./scripts/linux/install.sh .venv-linux

set -euo pipefail

step() { printf '==> %s\n' "$1"; }
fail() { printf 'ERROR: %s\n' "$1" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
cd "$REPO_ROOT"

VENV_DIR="${1:-.venv}"
export UV_PROJECT_ENVIRONMENT="$VENV_DIR"

step "Checking for uv"
if ! command -v uv >/dev/null 2>&1; then
    fail "uv was not found on PATH. Install it from https://docs.astral.sh/uv/ and re-run this script.
Quick install (no root required): curl -LsSf https://astral.sh/uv/install.sh | sh"
fi
echo "    Found: $(uv --version)"

step "Checking for a usable Python interpreter"
if ! uv python find ">=3.11" >/dev/null 2>&1; then
    echo "    No Python >=3.11 found; letting uv install one into its own managed location."
fi

if [ -d "$VENV_DIR" ] && [ ! -x "$VENV_DIR/bin/python3" ]; then
    fail "'$VENV_DIR' already exists but isn't a Linux virtual environment
(missing $VENV_DIR/bin/python3). This usually means the same checkout is
also used from Windows, which created $VENV_DIR as a Windows venv
($VENV_DIR\\Scripts\\...) -- a Windows venv and a Linux venv can't share
one directory. Re-run with a different name instead, e.g.:
    ./scripts/linux/install.sh .venv-linux"
fi

if [ -d "$VENV_DIR" ]; then
    step "Virtual environment already exists at $VENV_DIR (reusing it)"
else
    step "Creating project-local virtual environment ($VENV_DIR)"
    uv venv --python ">=3.11" "$VENV_DIR" || fail "Failed to create the virtual environment."
fi

step "Installing locked dependencies (uv sync)"
if ! uv sync --locked; then
    echo "    'uv sync --locked' failed; this means uv.lock is out of date with pyproject.toml." >&2
    fail "Dependency sync failed. If you intentionally changed pyproject.toml, run 'uv lock' first and commit the updated uv.lock."
fi

step "Verifying the installed CLI"
if ! VERSION_OUTPUT="$("$VENV_DIR/bin/vhealth" --version 2>&1)"; then
    fail "vhealth was installed but '--version' failed:
$VERSION_OUTPUT"
fi
echo "    $VERSION_OUTPUT"

echo ""
echo "Install complete."
echo ""
echo "Run vhealth with:"
echo "    $REPO_ROOT/$VENV_DIR/bin/vhealth --help"
echo "or, after activating the environment:"
echo "    source $REPO_ROOT/$VENV_DIR/bin/activate"
echo "    vhealth --help"
