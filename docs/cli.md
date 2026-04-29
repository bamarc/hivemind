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

### `indexer clean` (alias: `clear`)
Wipes the local state AND the Qdrant collection for the current project.
*   **Options**:
    *   `--force`, `-f`: Skip confirmation prompt.

### `scout crawl [urls...]`
Crawl web documentation and save it for indexing.
*   **Arguments**:
    *   `[urls...]`: Optional list of specific URLs to crawl.
*   **Options**:
    *   `--recursive`, `-r`: Enable recursive crawling (follows internal links).
    *   `--verbose`: Show detailed crawling logs.

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
