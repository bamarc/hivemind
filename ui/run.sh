#!/usr/bin/env bash
# Run Hivemind UI with system PySide6 + uv-managed hivemind deps
set -euo pipefail
cd "$(dirname "$0")"

# Detect system Python 3.x (prefer 3.13, fall back to 3)
PY=$(command -v python3.13 || command -v python3 || echo "")
if [ -z "$PY" ]; then
    echo "Python 3 not found"
    exit 1
fi

# 1. Ensure uv venv is ready (won't be touched after this)
uv sync 2>&1 | tail -3

# 2. Locate system PySide6
PYSIDE_DIR=$("$PY" -c "import PySide6; import os; print(os.path.dirname(PySide6.__file__))" 2>/dev/null || echo "")
if [ -z "$PYSIDE_DIR" ]; then
    echo "PySide6 not found. Install it with: sudo zypper install python3-pyside6"
    exit 1
fi

# 3. Symlink system PySide6 + shiboken6 into the uv venv
SITE_PKGS=$(.venv/bin/python3 -c "import site; print(site.getsitepackages()[0])")
for pkg in PySide6 shiboken6; do
    target="$SITE_PKGS/$pkg"
    [ -L "$target" ] || [ -e "$target" ] && continue
    src=$("$PY" -c "import $pkg; import os; print(os.path.dirname($pkg.__file__))" 2>/dev/null || echo "")
    [ -n "$src" ] && ln -s "$src" "$target"
done

# 4. Run using venv Python directly (no `uv run` = no venv recreation)
exec .venv/bin/python3 main.py "$@"
