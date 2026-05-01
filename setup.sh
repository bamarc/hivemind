#!/bin/bash
set -e

# ──────────────────────────────────────────────────────────────────────
# Hivemind Setup Wizard
# ──────────────────────────────────────────────────────────────────────
# Usage:
#   bash setup.sh             # Simple install (core only, no scout)
#   bash setup.sh --extended  # Extended install (core + scout/web crawler)
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
    echo "🔧 Simple install: core only (scout/web crawler excluded)."
    echo "   To include scout, run: bash setup.sh --extended"
    uv sync --quiet
fi

# 2. Run the interactive wizard
echo "🚀 Starting wizard..."
PYTHONPATH=. uv run cli/setup.py

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✨ Setup complete! You can now use 'hivemind' from anywhere."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
