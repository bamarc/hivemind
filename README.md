# Hivemind

Hivemind is a semantic code indexer and search tool. It allows you to index local codebases and web documentation, providing a semantic search interface for AI agents (via MCP) or REST API.

## Graphical UI

Hivemind also has a **Kirigami desktop GUI** built with PySide6:

```bash
cd ui
uv sync
uv run python main.py
```

See [ui/README.md](ui/README.md) and [ui/QUICKSTART.md](ui/QUICKSTART.md) for details.

## Key Features

- **Semantic Search**: Powered by Qdrant and high-performance embedding models.
- **Recursive Web Scouting**: Automatically crawl and index documentation from URLs using `crawl4ai`.
- **AST-Aware Chunking**: Intelligent code splitting that preserves logic context (Python, Go, TS, etc.).
- **Incremental Indexing**: Efficiently watches for file changes and only re-indexes what's necessary.
- **MCP Server**: Zero-config integration with AI agents like Cursor or Claude Desktop.
- **Pluggable Preprocessors**: Support for indexing PDF, Docx, and other document formats.

## Installation & Setup

Hivemind offers two install profiles:

| Profile | Command | Includes | Use Case |
|---------|---------|----------|----------|
| **Full** (default) | `bash install.sh` | Core + Web Search + Web Scout | Code indexing, search & web crawling |
| **Minimal** | `bash install.sh --minimal` | Core + Web Search | Code indexing & search only |

The **Web Scout** requires `crawl4ai` and `playwright` (which downloads Chromium, ~300 MB). These are included in the default install. If you only need code indexing and web search, use the `--minimal` flag.

### 1. The Interactive Setup (Recommended)
If you are setting up Hivemind for the first time, use the interactive wizard. It will help you configure your models and even start a local Qdrant instance via Docker.

```bash
# Full setup (core + web search + web crawler)
./setup.sh

# Minimal setup (core + web search only)
./setup.sh --minimal
```
*Note: You can run this anytime later using `hivemind setup`.*

### 2. The Simple Installer
If you just want to install/update the `hivemind` tool globally without a wizard:

```bash
# Full install (core + web search + web crawler)
./install.sh

# Minimal install (core + web search only)
./install.sh --minimal
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

## Security Disclaimer

**Hivemind is not hardened against prompt injection.** The MCP server executes tools based on instructions from AI agents, which may be influenced by untrusted content (e.g., web pages crawled via `scout_urls` or `deep_research`, or code files indexed from a repository). An attacker who can inject malicious instructions into crawled content could potentially trick the agent into performing unintended operations.

By using Hivemind, you acknowledge and accept this risk. The authors and contributors provide this software "as is", without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose, and noninfringement. In no event shall the authors or contributors be liable for any claim, damages, or other liability, whether in an action of contract, tort, or otherwise, arising from, out of, or in connection with the software or the use or other dealings in the software.

## Documentation

Start at the [Documentation Index](docs/index.adoc) for a complete overview with TOC, or jump directly to a specific guide:

- [Architecture](docs/architecture.adoc) — System design, component boundaries, data flow
- [API Reference](docs/api.adoc) — MCP tools, REST endpoints, Qdrant schema
- [CLI Command Reference](docs/cli.adoc) — All commands and options
- [Configuration Reference](docs/configuration.adoc) — Full settings schema
- [Indexer Deep Dive](docs/indexer.adoc) — Pipeline, chunking, state management
- [Scout Deep Dive](docs/scout.adoc) — Web crawling, Map-Reduce pattern
- [Deployment Guide](docs/deployment.adoc) — systemd, PM2, Docker
- [Troubleshooting](docs/troubleshooting.adoc) — Common issues and solutions
- [Agent Protocol (AGENTS.md)](AGENTS.md) — Rules for AI agents
