# Hivemind Architecture

Hivemind is a modular, distributed system designed to bridge the gap between local codebases and large-scale semantic search.

## Overview

The system is divided into four main layers, adhering to the boundaries defined in `AGENTS.md`:

1.  **Core (Shared)**:
    *   Handles configuration loading via Pydantic.
    *   Maintains connections to external services (Qdrant, Embedding API).
    *   Provides shared utility functions for embeddings and health checks.

2.  **Indexer (Ingestion)**:
    *   **Scanner**: Performs deep scans of directories to find files needing indexing.
    *   **Watcher**: Listens to OS file system events (created, modified) using `watchdog`.
    *   **Queue/Worker**: Coordinates concurrent indexing to prevent race conditions.
    *   **State Manager**: Tracks file checksums and modification times to enable incremental indexing.
    *   **Chunkers**: Pluggable strategies for splitting files into manageable pieces.

3.  **Server (Interfaces)**:
    *   **MCP Server**: Implements the Model Context Protocol over `stdio` for direct integration with LLM clients like Cursor or Claude Desktop.
    *   **REST API**: Provides a FastAPI interface for external integrations, metrics, and health monitoring.

4.  **Infra (Infrastructure)**:
    *   Contains deployment artifacts like Docker Compose for the Qdrant vector database.

## Data Flow

### Indexing Flow
1.  `Indexer` detects a file change or finds a new file during scan.
2.  File is passed to a `Chunker` which splits it into text snippets.
3.  Each snippet is sent to the `Embedder` (via `Core`) to generate a vector.
4.  Vectors and metadata (filepath, content, index) are upserted to `Qdrant`.
5.  `StateManager` updates the local state to reflect the file is indexed.

### Search Flow
1.  User/LLM initiates a search query.
2.  `Server` (MCP or API) receives the query.
3.  Query is embedded using the `Embedder`.
4.  `Qdrant` performs a vector similarity search.
5.  `Server` formats the results (Markdown or JSON) and returns them.
