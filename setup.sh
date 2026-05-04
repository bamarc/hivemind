#!/bin/bash
set -e

# ──────────────────────────────────────────────────────────────────────
# Hivemind Setup Wizard
# ──────────────────────────────────────────────────────────────────────
# Usage:
#   bash setup.sh              # Full setup (core + scout + web search)
#   bash setup.sh --extended   # Same as default (full setup)
#   bash setup.sh --minimal    # Minimal setup (core + web search only)
# ──────────────────────────────────────────────────────────────────────

MINIMAL=false
if [ "${1:-}" = "--minimal" ]; then
    MINIMAL=true
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧙  Hivemind Dynamic Setup Wizard"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. Ensure dependencies are installed
echo "📦 Preparing environment..."

if [ "$MINIMAL" = true ]; then
    echo "🔧 Minimal setup: core + web search only."
    echo "   To include the full web crawler, run: bash setup.sh"
    uv sync --quiet --extra web
else
    echo "🌐 Full setup: including scout dependencies (crawl4ai, playwright)..."
    uv sync --quiet --extra scout --extra web
fi

# 2. Run the interactive wizard
echo "🚀 Starting wizard..."
PYTHONPATH=. uv run cli/setup.py

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✨ Setup complete! You can now use 'hivemind' from anywhere."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
