# API Reference

## MCP Tools (Primary Interface)

Hivemind exposes custom MCP (Model Context Protocol) tools for AI agents. These tools are **preferred** over generic file operations for code discovery and analysis.

### Tool Hierarchy (Priority Order)

| Priority | Tool | When to Use |
|----------|------|-------------|
| 🥇 | `semantic_code_search` | **Always first.** Find code by meaning, not filename. Use natural language queries. |
| 🥈 | `get_file_tree` | Only for structural overview. Do NOT use to find specific logic. |
| 🥈 | `search_web` | Search the internet for documentation, API references, or solutions. |
| 🥈 | `scout_urls` | Crawl URLs (from `search_web` results) to get full page markdown content. |
| � | `read_file` | Read file contents with line numbers and slicing. Use when `semantic_code_search` is insufficient. |
| 🥉 | `get_git_history` | Get last commit metadata (author, date, message) for any file. |
| 🥉 | `analyze_code_complexity` | After finding a file, to determine if a small or flagship model should handle it. |
| 🥉 | `generate_blueprint` | For architectural planning before implementing complex features. |
| 🥉 | `run_verification` | To run tests and linting before completing a task. |

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

### `search_web`

**Search the internet using DuckDuckGo.** Returns title, URL, and snippet for each result. Use this to find documentation, API references, or solutions for programming questions. Then use `scout_urls` to fetch full page content from the most promising results.

- **Parameters:**
  - `query` (required): The search query string (e.g., `"python asyncio gather documentation"`).
  - `max_results` (optional, default 10): Maximum results (capped at 20).

- **Requires:** `ddgs` package. Install with `uv sync --extra scout`.

### `scout_urls`

**Crawl one or more URLs and return their content as markdown.** Use this after `search_web` to get full page content from search results. Multiple URLs are crawled in parallel and returned in a single response to minimize token usage.

Supports a **Map-Reduce** pattern for large pages: first request a Table of Contents (`mode="toc"`), then request only the relevant sections (`mode="sections"`). This avoids context-window overflow from giant GitHub PRs, documentation pages, etc.

- **Parameters:**
  - `urls` (required): List of URLs to crawl (e.g., `["https://docs.python.org/3/library/asyncio.html"]`).
  - `max_results` (optional, default 3): Maximum URLs to process (capped at 10).
  - `mode` (optional, default `"full"`): One of:
    - `"full"` — Returns raw markdown content (backward compatible). If content exceeds ~8000 chars, shows an excerpt with a hint to use `mode="toc"`.
    - `"toc"` — Crawls the URL, splits content into sections via the MarkdownChunker, caches chunks in memory, and returns a Table of Contents showing section names, heading levels, line ranges, and estimated token counts. No raw content is returned.
    - `"sections"` — Reads previously cached chunks and returns content only for the sections named in the `sections` parameter. Falls back to re-crawling if cache is empty.
  - `sections` (optional, default `None`): List of section names or numeric indices to retrieve when `mode="sections"`. Matches are case-insensitive substring matches against header text (e.g., `["Conversation", "Checks"]` for a GitHub PR). Mutually exclusive with `mode="full"`.

- **Usage flow for large pages:**
  1. `scout_urls(["https://github.com/org/repo/pull/123"], mode="toc")` → get TOC
  2. `scout_urls(["https://github.com/org/repo/pull/123"], mode="sections", sections=["Conversation", "Checks"])` → get only relevant sections (~4500 tokens instead of 22000+)

- **Requires:** `crawl4ai` and `playwright`. Install with `uv sync --extra scout` then `playwright install chromium`.

### `read_file`

**Read file contents with line numbers and slicing.** Use when `semantic_code_search` doesn't give you enough context about a specific file.

- **Parameters:**
  - `filepath` (required): Path to the file (relative to workspace or absolute).
  - `start_line` (optional, default 1): First line to read (1-based).
  - `max_lines` (optional, default 500): Maximum lines to return (capped at 1000).

- **Safety:** Refuses to read from excluded directories (`.git`, `node_modules`, `__pycache__`, etc.).

### `get_git_history`

**Get git commit metadata for a file.** Returns the last commit's hash, author, email, date, and subject. Use to understand who last modified a file and why.

- **Parameters:**
  - `filepath` (required): Path to the file (relative to workspace root or absolute).

- **Graceful:** Returns a clear message for non-git repos or untracked files.

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
