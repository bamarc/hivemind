# CLI Command Reference

Hivemind provides a unified CLI via `main.py`.

## Global Options
*   `--help`: Show available commands and options.

## Commands

### `indexer start <path>`
Starts the code ingestion process.
*   **Arguments**:
    *   `<path>`: The directory to index.
*   **Options**:
    *   `--watch / --no-watch`: Enable/disable file system watching (default: watch).
    *   `--verbose`: Show detailed indexing logs.

### `indexer clean`
Wipes the local state and Qdrant collection for the current project. Useful for forced reindexing.
*   **Options**:
    *   `--force`, `-f`: Skip confirmation prompt.

### `search <query>`
Perform a semantic search from the terminal.
*   **Arguments**:
    *   `<query>`: The natural language search query.
*   **Options**:
    *   `--limit <int>`: Number of results to return (default: 5).
    *   `--verbose`: Show vector similarity scores.

### `mcp`
Start the MCP (Model Context Protocol) server.
*   Uses `stdio` for communication.
*   Exposes the `semantic_code_search` tool.

### `api`
Start the FastAPI REST server.
*   **Options**:
    *   `--host <text>`: Bind host (overrides config).
    *   `--port <int>`: Bind port (overrides config).
    *   `--verbose`: Enable debug logging for API requests.
