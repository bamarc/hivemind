# Hivemind - Agent Protocol

Welcome to the Hivemind codebase. This document outlines the architectural rules, boundaries, and conventions for AI agents (Cursor, Roo, Claude, etc.) working on this repository.

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