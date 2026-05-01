#!/bin/bash
set -e

# ──────────────────────────────────────────────────────────────────────
# Hivemind Setup Wizard
# ──────────────────────────────────────────────────────────────────────
# Usage:
#   bash setup.sh              # Standard install (core + web search)
#   bash setup.sh --extended   # Extended install (adds crawl4ai, playwright)
# ──────────────────────────────────────────────────────────────────────

EXTENDED=false
if [ "${1:-}" = "--extended" ]; then
    EXTENDED=true
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧙  Hivemind Dynamic Setup Wizard"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. Ensure the tool is installed and synced
echo "📦 Preparing environment..."

if [ "$EXTENDED" = true ]; then
    echo "🌐 Extended install: including scout dependencies (crawl4ai, playwright)..."
    uv sync --quiet --extra scout
else
    echo "🔧 Standard install: core + web search (duckduckgo-search)."
    echo "   To include the full web crawler, run: bash setup.sh --extended"
    uv sync --quiet --extra web
fi

# 2. Run the interactive wizard
echo "🚀 Starting wizard..."
PYTHONPATH=. uv run cli/setup.py

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✨ Setup complete! You can now use 'hivemind' from anywhere."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
