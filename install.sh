#!/bin/bash
set -e

# ──────────────────────────────────────────────────────────────────────
# Hivemind Installer
# ──────────────────────────────────────────────────────────────────────
# Usage:
#   bash install.sh           # Simple install (core only, no scout)
#   bash install.sh --extended  # Extended install (core + scout/web crawler)
# ──────────────────────────────────────────────────────────────────────

EXTENDED=false
if [ "${1:-}" = "--extended" ]; then
    EXTENDED=true
fi

echo "🚀 Updating Hivemind..."

# 1. Update the hivemind tool.
# We explicitly uninstall first to ensure a clean state for local updates.
echo "📦 Cleaning old installation..."
echo "📦 Installing hivemind tool..."

if [ "$EXTENDED" = true ]; then
    echo "🌐 Extended install: including scout dependencies (crawl4ai, playwright)..."
    uv tool install --reinstall --force . --with crawl4ai --with playwright
else
    echo "🔧 Simple install: core only (scout/web crawler excluded)."
    echo "   To include scout, run: bash install.sh --extended"
    uv tool install --reinstall --force .
fi

# 2. Install Playwright browsers if scout dependencies are present.
if [ "$EXTENDED" = true ]; then
    echo "🌐 Checking Playwright browsers..."
    if [ ! -d "$HOME/.cache/ms-playwright" ] || [ -z "$(ls -A $HOME/.cache/ms-playwright 2>/dev/null)" ]; then
        echo "📥 Installing browsers and system dependencies..."
        uv run playwright install --with-deps
    else
        echo "✅ Browsers already present in ~/.cache/ms-playwright"
    fi
else
    echo "⏭️  Skipping Playwright browser install (not needed for core install)."
fi

echo "✨ Hivemind is ready!"
