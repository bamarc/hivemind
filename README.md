# Hivemind

Hivemind is a semantic code indexer and search tool. It allows you to index local codebases and web documentation, providing a semantic search interface for AI agents (via MCP) or REST API.

## Key Features

- **Semantic Search**: Powered by Qdrant and high-performance embedding models.
- **Recursive Web Scouting**: Automatically crawl and index documentation from URLs using `crawl4ai`.
- **AST-Aware Chunking**: Intelligent code splitting that preserves logic context (Python, Go, TS, etc.).
- **Incremental Indexing**: Efficiently watches for file changes and only re-indexes what's necessary.
- **MCP Server**: Zero-config integration with AI agents like Cursor or Claude Desktop.
- **Pluggable Preprocessors**: Support for indexing PDF, Docx, and other document formats.

## Installation & Setup

Hivemind provides two ways to get started:

### 1. The Interactive Setup (Recommended)
If you are setting up Hivemind for the first time, use the interactive wizard. It will help you configure your models and even start a local Qdrant instance via Docker.

```bash
./setup.sh
```
*Note: You can run this anytime later using `hivemind setup`.*

### 2. The Simple Installer
If you just want to install/update the `hivemind` tool globally without a wizard:

```bash
./install.sh
```

## Quick Start

1. **Initialize your project**:
   In your codebase directory, run:
   ```bash
   hivemind init
   ```

2. **Start the Indexer**:
   ```bash
   hivemind indexer start .
   ```

3. **Scout web content**:
   Crawl documentation and save it for indexing:
   ```bash
   hivemind scout crawl https://docs.example.com --recursive
   ```

4. **Search**:
   Perform a semantic search in your terminal:
   ```bash
   hivemind search "how does the auth logic work?"
   ```

## Documentation

- [Architecture](docs/architecture.md)
- [Configuration Reference](docs/configuration.md)
- [CLI Command Reference](docs/cli.md)
- [REST API Reference](docs/api.md)
- [Agent Protocol (AGENTS.md)](AGENTS.md)
