#!/usr/bin/env bash
# Removes what install.sh created, on Linux/macOS.
#
# Deletes the project-local virtual environment (.venv) and any local
# build/test caches. Safe to run repeatedly, including when nothing was
# ever installed. Requires no root.
#
# Does NOT touch:
#   - uv or Python themselves (installed outside this repo, and likely
#     shared with other projects on this machine)
#   - anything you passed to 'vhealth assess --output <dir>' (your own
#     generated reports)
#   - the cloned repo folder itself
# See the "Uninstall" section in README.md if you want those gone too.

set -euo pipefail

step() { printf '==> %s\n' "$1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
cd "$REPO_ROOT"

removed_something=0

if [ -d ".venv" ]; then
    step "Removing virtual environment (.venv)"
    rm -rf ".venv"
    removed_something=1
else
    echo "    .venv not found (already removed, or vhealth was never installed here)."
fi

for dir in .pytest_cache .ruff_cache .mypy_cache htmlcov dist build; do
    if [ -d "$dir" ]; then
        step "Removing $dir"
        rm -rf "$dir"
        removed_something=1
    fi
done

if [ -f ".coverage" ]; then
    step "Removing .coverage"
    rm -f ".coverage"
    removed_something=1
fi

echo ""
if [ "$removed_something" -eq 1 ]; then
    echo "Uninstall complete."
else
    echo "Nothing to remove - vhealth wasn't installed in this folder."
fi
echo ""
echo "Not touched (remove these yourself if you want a fully clean machine):"
echo "  - uv / Python (shared with other projects; see https://docs.astral.sh/uv/)"
echo "  - Any report folders you gave to 'vhealth assess --output <dir>'"
echo "  - This cloned repo folder: $REPO_ROOT"
