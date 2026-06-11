## Why

Hivemind currently has no graphical user interface — it's used exclusively via CLI commands and an MCP server. This limits adoption for developers who prefer visual tools for managing code indexes, performing semantic search, and monitoring server status. A convergent desktop/mobile GUI built with Kirigami will make Hivemind accessible to a wider audience while preserving its philosophy of being lightweight, modular, and framework-agnostic.

## What Changes

- **New `ui/` subdirectory** in the Hivemind project containing a Kirigami-based desktop GUI
- **PySide6 Python backend** that imports Hivemind's core modules and exposes them to QML via `QAbstractListModel`, `Q_PROPERTY`, and `Q_INVOKABLE`
- **6 QML pages** using Kirigami components: Dashboard, Repositories, Search, Server, Indexer, Settings
- **QThread-based workers** for non-blocking search and indexing
- **Spec-driven development lifecycle** managed via OpenSpec for this feature
- **No new runtime dependencies on Hivemind's core** — PySide6 and Kirigami are UI-only deps

## Capabilities

### New Capabilities
- `dashboard`: Overview page showing indexed chunks count, server status, recent search activity, and system health at a glance
- `repository-management`: Add, remove, and re-index code repositories; browse indexed repos with status indicators
- `semantic-search-ui`: Graphical semantic search interface with query input, language filters, and scorable result cards
- `mcp-server-control`: Start/stop the MCP server, view registered tools, monitor connected clients and request stats
- `indexer-monitoring`: Real-time indexing progress with file count, ETA, progress bar, chunker configuration controls, and pause/stop
- `settings-management`: Configure Qdrant connection (host/port/collection), embedding provider/model/endpoint, and file watcher settings

### Modified Capabilities
- *None* — this is a new UI frontend; no existing capabilities are changing

## Impact

- **New dependency**: `PySide6 >= 6.7` (UI-only, in `ui/pyproject.toml`, not in the root `pyproject.toml`)
- **New dependency**: Kirigami QML module (system package, not pip)
- **New directory**: `ui/` with its own `pyproject.toml`, Python backend, QML templates, and tests
- **No changes** to existing `core/`, `indexer/`, `server/`, `scout/`, or `cli/` code
- The UI imports existing Hivemind modules via a path dependency in `ui/pyproject.toml`
