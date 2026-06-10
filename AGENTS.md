# Hivemind - Agent Protocol

Welcome to the Hivemind codebase. This document outlines the architectural rules, boundaries, and conventions for AI agents (Cursor, Roo, Claude, Jules, GitHub Copilot/Agents, etc.) working on this repository.

## 1. The Core Philosophy

Hivemind is a distributed, modular pipeline. Do not introduce heavy abstractions. Avoid frameworks like LangChain or LlamaIndex. We prefer raw, direct API clients (openai, qdrant-client) to maintain strict control over performance, debugging, and metadata injection.

## 2. Component Boundaries

Never mix concerns between directories.

* /indexer: ONLY handles reading files, chunking text, and triggering ingestion. It should never handle user queries.

* /server: ONLY handles MCP tool definitions and LLM interactions. It should never read local files directly.

* /core: The ONLY place where external API clients (Qdrant, LM Studio) are instantiated. Both Indexer and Server must import clients from here.

* /infra: ONLY contains deployment artifacts (Docker, terraform, etc.) for the remote infrastructure.

* /cli: ONLY contains the execution scripts (__main__ entry points, CLI wrappers, daemon loops).

## 3. Dependency Management

This project strictly uses uv for dependency management.

* Do NOT use pip install directly.

* Use uv add <package> to add dependencies.

* Ensure the pyproject.toml remains the source of truth.

## 4. Modifying the Indexing Logic

If you are asked to improve how code is chunked (e.g., implementing tree-sitter for AST-aware splitting):

1. Implement the parsing logic in /indexer/chunkers/.

2. Ensure the metadata payload constructed for Qdrant remains flat and easily filterable.

3. Update /core/clients.py if the embedding model dimensions change.

## 5. MCP Tool Expansion

If you are asked to add new tools for the LLM (e.g., find_usages, get_file_tree):

1. Define the tool in /server/server.py using @mcp.tool().

2. Ensure the tool returns clean, formatted strings (markdown is preferred).

3. If the tool requires searching the database, use the pre-initialized db client from core.clients.

## 6. Roo Context & Workflow Rules

These rules apply to all AI agents (Roo, Cursor, Claude, etc.) working on this repository.

### 6.1 Project Execution

The project is managed exclusively via **uv**. Do not use `python` or `pip` directly — they are not guaranteed to be available on the path.

* Always use `uv run <script>` to execute any module or script.
* Use `uv add <package>` to add new dependencies.
* Use `uv sync` to install the project and its dependencies (equivalent to `pip install`).
* Use `uv lock` to update the lockfile after changes to `pyproject.toml`.

### 6.2 Test Before Completion

* Before submitting any change or marking a task as **done**, you **must** run the full test suite and check coverage using the provided script at the repository root:

  ```bash
  ./run_tests.sh
  ```

* If the change is scoped to a specific area, you may additionally run targeted tests first (`uv run pytest <path>`) for faster feedback, but the full suite script must pass before final submission.
* Review `.agents/testing_conventions.md` for more detailed testing guidelines.

### 6.3 Documentation Must Stay In Sync

* Whenever you modify code, update the relevant documentation in `/docs/` to reflect the changes.
* All documentation is written in **AsciiDoc** (`.adoc`) format.
* Keep [`README.md`](README.md) up to date if the change affects onboarding, configuration, or usage.
* Outdated documentation is considered a bug.

### 6.4 Prefer Semantic Search Over File Search

* When exploring the codebase to understand how something works or where to make changes, **always use semantic search first** (via `codebase_search` tool) rather than grepping for literal strings or manually navigating directories.
* Semantic search finds relevant code based on meaning, which is far more effective than regex-based search for understanding implementations.
* Fall back to regex/file search only when semantic search does not yield useful results.

### 6.5 MCP Tools Are Your Primary Interface

This project exposes custom MCP tools that are **more powerful** than generic file operations:

* **`semantic_code_search`** — Your PRIMARY tool for finding code. Always use this before reading files manually. It understands natural language queries and returns ranked, relevant snippets. Much faster and cheaper than browsing files.
* **`get_file_tree`** — Use only for structural overview. Do NOT use it to find specific logic — that's what `semantic_code_search` is for.
* **`analyze_code_complexity`** — Use to determine if a file is simple enough for a small model or needs a flagship model.
* **`generate_blueprint`** — Use for architectural planning before implementing complex features.
* **`run_verification`** — Use to run tests and linting before completing a task.

Reading files manually (`read_file`, `list_files`) should be your **last resort**, not your first. The MCP tools are faster, cheaper, and more accurate for code discovery and analysis.