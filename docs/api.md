# API Reference

## MCP Tools (Primary Interface)

Hivemind exposes custom MCP (Model Context Protocol) tools for AI agents. These tools are **preferred** over generic file operations for code discovery and analysis.

### Tool Hierarchy (Priority Order)

| Priority | Tool | When to Use |
|----------|------|-------------|
| 🥇 | `semantic_code_search` | **Always first.** Find code by meaning, not filename. Use natural language queries. |
| 🥈 | `get_file_tree` | Only for structural overview. Do NOT use to find specific logic. |
| 🥉 | `analyze_code_complexity` | After finding a file, to determine if a small or flagship model should handle it. |
| 🥉 | `generate_blueprint` | For architectural planning before implementing complex features. |
| 🥉 | `run_verification` | To run tests and linting before completing a task. |
| ❌ | `read_file` / `list_files` | **Last resort.** Manual file reading is slower and less accurate than semantic search. |

### `semantic_code_search`

**Primary tool for code discovery.** Searches the vector index using natural language understanding.

- **Parameters:**
  - `query` (required): Natural language description of the functionality or logic you're looking for.
  - `limit` (optional, default 5): Maximum number of results.
  - `root_path` (optional): Project root path (auto-detected from workspace).
  - `file_filter` (optional): Substring filter on file paths (e.g., `"server/"`).
  - `language` (optional): Language filter (e.g., `"python"`, `"typescript"`).
  - `is_test` (optional): `true` for only test files, `false` to exclude them.

### `get_file_tree`

**Structural overview only.** Returns a directory tree of the project.

- **Parameters:**
  - `root_path` (optional): Project root path (auto-detected from workspace).
  - `depth` (optional, default 2): How many levels deep to show.

### `analyze_code_complexity`

Calculates AST depth, dependency count, and complexity score for a file.

- **Parameters:**
  - `filepath` (required): Path to the file to analyze.

### `generate_blueprint`

Generates a structured JSON blueprint for a coding task using a flagship model.

- **Parameters:**
  - `task` (required): Description of the task.
  - `context` (required): Context about the codebase.

### `run_verification`

Runs linters and tests for the project or a specific file.

- **Parameters:**
  - `filepath` (optional): Specific file to test. Runs full suite if omitted.

### `get_index_status` / `start_indexing`

Manage the semantic search index. Call `get_index_status` first; if not indexed, call `start_indexing`.

---

## REST API Reference

The Hivemind REST API provides programmatic access to search and embedding features.

## Authentication
If configured, requests must include the API key in the header defined by `security.api_key_header` (default: `X-API-Key`).

## Endpoints

### `GET /health`
Returns detailed health status of the system.
**Response**:
```json
{
  "status": "healthy",
  "components": {
    "qdrant": { "status": "connected", "collection": "hivemind_code" },
    "embedder": { "status": "connected", "model": "qwen3-4B-embedding" },
    "version": "0.2.0"
  }
}
```

### `POST /embed`
Generates a vector embedding for the provided text.
**Request**:
```json
{
  "text": "code snippet or query"
}
```

### `POST /search`
Performs a semantic search.
**Request**:
```json
{
  "query": "how do I handle auth?",
  "limit": 5
}
```

### `GET /metrics`
Returns system metrics.
**Response**:
```json
{
  "indexed_files_total": 1234,
  "total_chunks_in_db": 5678,
  "version": "0.2.0"
}
```
