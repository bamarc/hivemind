# Hivemind Kirigami UI — Quickstart

## Prerequisites

1. **Kirigami QML module** (system package):
   - Arch: `pacman -S qqc2-desktop-style kirigami`
   - Debian/Ubuntu: `apt install qml6-module-org-kde-kirigami`
   - Fedora: `dnf install kf6-kirigami2`
   - macOS/Windows: included with PySide6 — no system package needed.

2. **Python 3.12+** with `uv` installed.

## Setup

```bash
cd ui
uv sync
```

## Run

```bash
cd ui
uv run python main.py
```

## Run Tests

```bash
cd ui
uv sync --extra test
uv run pytest tests/ -v
```

## Project Structure

```
ui/
├── backend/
│   ├── engine.py              # BackendEngine — QML context property
│   ├── managers/
│   │   ├── config_manager.py  # Config & repo CRUD
│   │   ├── search_manager.py  # Semantic search
│   │   └── server_manager.py  # MCP server lifecycle
│   ├── models/
│   │   ├── search_results_model.py
│   │   └── repo_list_model.py
│   └── workers/
│       ├── index_worker.py    # QThread for indexing
│       └── search_worker.py   # QThread for search
├── qml/
│   ├── main.qml               # ApplicationWindow + sidebar
│   ├── pages/                 # 6 Kirigami pages
│   ├── components/            # StatusCard, RepoDelegate, SearchResultDelegate
│   └── dialogs/               # AddRepoSheet, ServerLogSheet
├── tests/                     # pytest suite
├── main.py                    # Entry point
└── pyproject.toml
```

## Architecture

- **`BackendEngine`** — singleton QObject exposed as `backend` in QML context.
  All pages access it via `backend.getDashboardStats()`, `backend.search()`, etc.
- **QThread workers** — `IndexWorker` and `SearchWorker` run blocking operations
  on background threads, emitting Qt signals back to the main thread.
- **QAbstractListModel** — `SearchResultsModel` and `RepoListModel` provide
  proper row-based semantics for `Kirigami.CardsListView`.
- **Managers** — `ConfigManager`, `SearchManager`, `ServerManager` wrap
  Hivemind's core modules (`core.config`, `core.search`, `server.server`).

## Notes

- The embedding service and Qdrant must be running for real search.
  If unreachable, search falls back to stub results gracefully.
- The MCP server start/stop is currently logged but works via subprocess.
- Kirigami is required as a system package — it is not a pip dependency.
