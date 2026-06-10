#!/bin/bash

# This script runs the test suite for the project using uv and includes coverage reporting.
# Ensure you run this from the root of the repository.

echo "Running tests with coverage via uv..."
uv run pytest --cov=. --cov-report=term-missing --cov-report=html

# Check if tests were successful
if [ $? -eq 0 ]; then
    echo "Tests completed successfully."
    echo "Coverage report can be found in the terminal output and in htmlcov/index.html."
else
    echo "Tests failed. Please check the output above."
    exit 1
fi
