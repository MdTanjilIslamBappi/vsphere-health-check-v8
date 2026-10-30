#!/usr/bin/env bash
# Installs vhealth into a project-local virtual environment on Linux/macOS.
#
# Creates .venv, installs dependencies from the committed uv.lock, installs
# vhealth into it, and verifies the CLI works. Safe to run repeatedly. Does
# not require root and never touches global/system Python packages.

set -euo pipefail

step() { printf '==> %s\n' "$1"; }
fail() { printf 'ERROR: %s\n' "$1" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
cd "$REPO_ROOT"

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

if [ -d ".venv" ]; then
    step "Virtual environment already exists at .venv (reusing it)"
else
    step "Creating project-local virtual environment (.venv)"
    uv venv --python ">=3.11" ".venv" || fail "Failed to create the virtual environment."
fi

step "Installing locked dependencies (uv sync)"
if ! uv sync --locked; then
    echo "    'uv sync --locked' failed; this means uv.lock is out of date with pyproject.toml." >&2
    fail "Dependency sync failed. If you intentionally changed pyproject.toml, run 'uv lock' first and commit the updated uv.lock."
fi

step "Verifying the installed CLI"
if ! VERSION_OUTPUT="$(.venv/bin/vhealth --version 2>&1)"; then
    fail "vhealth was installed but '--version' failed:
$VERSION_OUTPUT"
fi
echo "    $VERSION_OUTPUT"

echo ""
echo "Install complete."
echo ""
echo "Run vhealth with:"
echo "    $REPO_ROOT/.venv/bin/vhealth --help"
echo "or, after activating the environment:"
echo "    source $REPO_ROOT/.venv/bin/activate"
echo "    vhealth --help"
