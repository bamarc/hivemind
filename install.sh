#!/bin/bash
set -e

echo "🚀 Updating Hivemind..."

# 1. Update the hivemind tool. 
# --force is necessary to overwrite the existing tool installation with your local changes.
# uv is smart enough to reuse cached dependencies, so this is fast.
uv tool install --force .

# 2. Install Playwright browsers.
# We use 'uv run' to ensure we use the exact version specified in pyproject.toml.
echo "🌐 Checking Playwright browsers..."
uv run playwright install --with-deps

echo "✅ Hivemind is ready!"


