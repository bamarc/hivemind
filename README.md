# Hivemind

Hivemind is a semantic code indexer and search tool. It allows you to index local codebases and web documentation, providing a semantic search interface for AI agents (via MCP) or REST API.

## Key Features

- **Semantic Search**: Powered by Qdrant and high-performance embedding models.
- **Recursive Web Scouting**: Automatically crawl and index documentation from URLs using `crawl4ai`.
- **AST-Aware Chunking**: Intelligent code splitting that preserves logic context (Python, Go, TS, etc.).
- **Incremental Indexing**: Efficiently watches for file changes and only re-indexes what's necessary.
- **MCP Server**: Zero-config integration with AI agents like Cursor or Claude Desktop.
- **Pluggable Preprocessors**: Support for indexing PDF, Docx, and other document formats.

## Quick Start

1. **Install dependencies**:
   ```bash
   uv sync
   ```

2. **Configure your models**:
   Copy `config.yaml.example` to `config.yaml` and edit it to include your Qdrant URL and Model API keys.

3. **Start the Indexer**:
   ```bash
   hivemind indexer start .
   ```

4. **Scout web content**:
   ```bash
   hivemind scout crawl https://docs.example.com --recursive
   ```

5. **Search**:
   ```bash
   hivemind search "how does the auth logic work?"
   ```

## Documentation

- [Architecture](docs/architecture.md)
- [Configuration Reference](docs/configuration.md)
- [CLI Command Reference](docs/cli.md)
- [REST API Reference](docs/api.md)
