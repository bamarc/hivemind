#!/bin/bash
set -e

echo "🚀 Updating Hivemind..."

# 1. Update the hivemind tool. 
# We explicitly uninstall first to ensure a clean state for local updates.
echo "📦 Cleaning old installation..."
uv tool uninstall hivemind || true
uv tool install .

# 2. Install Playwright browsers if missing.
# We check the default cache location for existing browser binaries.
echo "🌐 Checking Playwright browsers..."
if [ ! -d "$HOME/.cache/ms-playwright" ] || [ -z "$(ls -A $HOME/.cache/ms-playwright 2>/dev/null)" ]; then
    echo "📥 Installing browsers and system dependencies..."
    uv run playwright install --with-deps
else
    echo "✅ Browsers already present in ~/.cache/ms-playwright"
fi

echo "✨ Hivemind is ready!"


