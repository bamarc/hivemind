#!/bin/bash
set -e

# ──────────────────────────────────────────────────────────────────────
# Hivemind Installer
# ──────────────────────────────────────────────────────────────────────
# Usage:
#   bash install.sh              # Full install (core + scout + web search)
#   bash install.sh --extended   # Same as default (full install)
#   bash install.sh --minimal    # Minimal install (core + web search only)
# ──────────────────────────────────────────────────────────────────────

MINIMAL=false
if [ "${1:-}" = "--minimal" ]; then
    MINIMAL=true
fi

echo "🚀 Updating Hivemind..."

# 1. Update the hivemind tool.
# We explicitly uninstall first to ensure a clean state for local updates.
echo "📦 Cleaning old installation..."
echo "📦 Installing hivemind tool..."

if [ "$MINIMAL" = true ]; then
    echo "🔧 Minimal install: core + web search only."
    echo "   To include the full web crawler, run: bash install.sh"
    uv tool install --reinstall --force . --with duckduckgo-search
    uv sync --extra web
else
    echo "🌐 Full install: including scout dependencies (crawl4ai, playwright)..."
    uv tool install --reinstall --force . --with duckduckgo-search --with crawl4ai --with playwright
    # Also sync project deps so `uv run` works locally
    uv sync --extra scout --extra web

    echo "🌐 Checking Playwright browsers..."
    if [ ! -d "$HOME/.cache/ms-playwright" ] || [ -z "$(ls -A $HOME/.cache/ms-playwright 2>/dev/null)" ]; then
        echo "📥 Installing playwright as a tool..."
        uv tool install playwright
        echo "📥 Installing browsers and system dependencies..."
        playwright install --with-deps
    else
        echo "✅ Browsers already present in ~/.cache/ms-playwright"
    fi
fi

echo "✨ Hivemind is ready!"
