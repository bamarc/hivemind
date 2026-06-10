# Testing Conventions

This file provides context and instructions for AI agents regarding testing in the Hivemind project.

## How Tests are Structured
The test suite is located in the `tests/` directory at the root of the project. It follows a clear organizational structure mirroring the main source code directories:

- `tests/test_core/`: Tests for the core module (clients, complexity, config, filesystem, planner, search, secrets).
- `tests/test_indexer/`: Tests for indexing operations, with a subdirectory `test_chunkers/` for individual chunker implementations.
- `tests/test_scout/`: Tests for the web crawler and scout functionalities.
- `tests/test_server/`: Tests for the API and MCP server implementations.
- `tests/test_integration/`: Integration tests that exercise larger components of the system pipeline.

## Writing Tests (Conventions)
When writing new tests or updating existing ones, adhere to the following conventions:

1. **Framework**: Tests are written using the `pytest` framework.
2. **Naming**: Test files must be named starting with `test_` (e.g., `test_clients.py`). Test functions must also start with `test_`.
3. **Async Support**: Since many components (especially those involving network requests or MCP) are asynchronous, tests often need to be async. Use the `@pytest.mark.asyncio` decorator where appropriate. The `pytest-asyncio` plugin is used to handle these correctly.
4. **Mocking**: Rely heavily on mocking external services to keep unit tests fast and deterministic. Use standard `unittest.mock` (like `@patch` or `MagicMock`).
5. **Fixtures**: Common test setups are defined as fixtures in `tests/conftest.py`. Review this file to utilize existing fixtures instead of reinventing setups.
6. **Coverage**: New features must include tests to maintain a high coverage standard.

## Running Tests
All testing operations are managed via `uv`. **Do not use raw python or pip directly.**

To execute the test suite, always use the dedicated test script located at the repository root:

```bash
./run_tests.sh
```

This script will run:
```bash
uv run pytest --cov=. --cov-report=term-missing --cov-report=html
```

It ensures that the test suite runs with coverage tracking enabled. Review the coverage output (in the terminal or `htmlcov/index.html`) to ensure any newly added code is appropriately tested before marking a task as done.
