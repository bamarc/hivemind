## Context

Hivemind is a Python-based distributed code indexing and semantic search system. It consists of:

- **core/** — Qdrant vector DB client, LM Studio embedding client, config management, RAG pipeline, search
- **indexer/** — Filesystem scanner, AST-aware chunkers (hybrid_ast, by_files, by_lines, by_size, markdown), watcher, worker pool
- **server/** — MCP (Model Context Protocol) server exposing tools: `semantic_code_search`, `get_file_tree`, `analyze_code_complexity`, `generate_blueprint`, `run_verification`
- **scout/** — Code analysis and complexity metrics
- **cli/** — Command-line entry points

Hivemind currently has no graphical interface. The project follows strict rules: no LangChain/LlamaIndex, `uv` for dependency management, component boundaries, and AsciiDoc documentation.

**Constraints:**
- PySide6 must match the Qt version used by the system-installed Kirigami QML module
- File indexing is I/O and CPU intensive — the UI must never block on indexing or search
- All QML property reads happen on Qt's main thread — backend data must be thread-safe
- Configuration should reuse Hivemind's existing `config.yaml`, not create a parallel config

## Goals / Non-Goals

**Goals:**
- Provide a convergent (desktop + mobile) Kirigami GUI for Hivemind
- Expose 6 functional pages: Dashboard, Repositories, Search, Server, Indexer, Settings
- Run all blocking operations (Qdrant queries, indexing, server start/stop) on background threads
- Reuse Hivemind's existing core modules directly — no wrapper API layer
- Keep the UI as a separate `ui/` subdirectory with its own `pyproject.toml`
- Follow KDE Human Interface Guidelines via standard Kirigami components

**Non-Goals:**
- Rewriting Hivemind's core architecture
- Adding web-based UI (this is a native Qt app)
- Building a mobile Android/iOS app (Kirigami convergent design makes this possible in future)
- Replacing the CLI or MCP server — the UI is an additional interface
- Real-time collaborative features
- Embedding the Qdrant web dashboard

## Decisions

### D1: QThread over asyncio for concurrency

The QML rendering loop runs on Qt's main thread. Any blocking call there freezes the UI. We use `QThread` subclasses (`IndexWorker`, `SearchWorker`) that emit Qt signals back to the main thread.

**Alternatives considered:** `asyncio` with `qasync` bridge. Rejected because QThread integrates natively with Qt's event loop — no bridging library, no event loop nesting issues, and better debugging via Qt's thread inspector.

### D2: BackendEngine singleton as QML context property

A single `BackendEngine` QObject is registered as `backend` on `QQmlApplicationEngine.rootContext()` before loading QML. All pages access it via `backend.search()`, `backend.serverStatus`, etc.

**Alternatives considered:** Per-page backend objects. Rejected because the engine needs to share state (e.g., indexing status shown on Dashboard and Indexer pages) — a singleton avoids duplicating state across pages.

### D3: QAbstractListModel for list data

Search results and repo lists use `QAbstractListModel` subclasses with defined `roleNames()` (e.g., `filePath`, `lineNumber`, `score`). QML's `ListView` and `CardsListView` bind directly to these via `model:` and access roles via `required property`.

**Alternatives considered:** Passing raw Python lists as QML `var` properties. Rejected because `QAbstractListModel` provides proper row-based semantics, change notifications, and works with `Kirigami.CardsListView` out of the box.

### D4: UI in its own `ui/` subdirectory with separate pyproject.toml

The UI code lives in `ui/` with its own `pyproject.toml` that has a path dependency on the parent Hivemind package. This keeps PySide6 and Kirigami dependencies isolated from Hivemind's core dependencies.

**Alternatives considered:** Adding PySide6 to the root `pyproject.toml`. Rejected because PySide6 is a large, desktop-only dependency that shouldn't be required for CLI/server users.

**Dependencies:**
- `ui/pyproject.toml`: `PySide6>=6.7`, `hivemind @ ..`
- System (not pip): Kirigami QML module (`org.kde.kirigami`)

### D5: Kirigami over plain QtQuick Controls

Kirigami provides convergent mobile/desktop layouts, hamburger drawer (`GlobalDrawer`), overlay sheets (`OverlaySheet`), cards, and KDE-native look-and-feel — all essential for a modern desktop app. Plain `QtQuick.Controls` lacks the sidebar navigation pattern and convergent layout system.

**Alternatives considered:** Plain QtQuick.Controls 2. Rejected because we'd need to reimplement sidebar, cards, and sheets from scratch. Kirigami's components are production-tested across KDE's entire application suite.

### D6: Reuse Hivemind's config.yaml directly

The UI reads/writes Hivemind's `~/.config/hivemind/config.yaml` via `hivemind.core.config.HivemindConfig` rather than maintaining a separate settings file.

**Alternatives considered:** Separate `ui/settings.json`. Rejected because it would fragment configuration — users shouldn't need to configure Qdrant connection in two places.

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  QML Layer (Kirigami)                                               │
│                                                                     │
│  Kirigami.ApplicationWindow                                         │
│  ├── GlobalDrawer (6 nav actions)                                   │
│  ├── ContextDrawer (per-page actions)                               │
│  └── PageStack                                                      │
│      ├── DashboardPage — StatusCard grid + recent activity          │
│      ├── RepositoriesPage — CardsListView + OverlaySheet            │
│      ├── SearchPage — TextField + CardsListView                     │
│      ├── ServerPage — InlineMessage + stats + tool list             │
│      ├── IndexerPage — ProgressBar + chunker config                 │
│      └── SettingsPage — FormLayout + Save/Reset                     │
│                                                                     │
│  Components: StatusCard, RepoDelegate, SearchResultDelegate          │
│  Dialogs: AddRepoSheet (OverlaySheet), ServerLogSheet               │
└──────────────────────────┬──────────────────────────────────────────-┘
                           │ Property bindings / signal-slot / models
┌──────────────────────────┴──────────────────────────────────────────┐
│  Python Backend (PySide6)                                          │
│                                                                     │
│  BackendEngine (QObject, singleton context property "backend")      │
│  ├── Q_PROPERTY: currentIndexing (bool)                             │
│  ├── Q_PROPERTY: serverStatus (str: "running"|"stopped")            │
│  ├── Q_INVOKABLE: search(query, limit) → list                       │
│  ├── Q_INVOKABLE: startServer() / stopServer() → bool              │
│  ├── Q_INVOKABLE: getRepos() / addRepo() / removeRepo()            │
│  │                                                                  │
│  ├── Managers (synchronous wrappers)                                │
│  │   ├── ConfigManager — read/write hivemind config.yaml            │
│  │   ├── SearchManager — wraps hivemind.core.search                 │
│  │   ├── IndexerManager — wraps hivemind.indexer                    │
│  │   └── ServerManager — wraps hivemind.server                      │
│  │                                                                  │
│  ├── Models (QAbstractListModel subclasses)                         │
│  │   ├── SearchResultsModel — roles: path, line, content, score,    │
│  │   │                   language                                   │
│  │   └── RepoListModel — roles: name, path, indexed, chunks         │
│  │                                                                  │
│  └── Workers (QThread subclasses)                                   │
│      ├── IndexWorker — progress(int,int), finished(bool,str)        │
│      └── SearchWorker — results_ready(list)                         │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ direct imports
┌──────────────────────────┴──────────────────────────────────────────┐
│  Hivemind Core Library                                              │
│  - hivemind.core (Qdrant client, search, config)                    │
│  - hivemind.indexer (chunkers, watcher, worker)                     │
│  - hivemind.server (MCP server)                                     │
│  - hivemind.scout (code analysis)                                   │
└─────────────────────────────────────────────────────────────────────┘
```

## Risks / Trade-offs

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| PySide6 / Kirigami Qt version mismatch | Medium | High — app crashes on startup | Install both from same distribution repositories. Document per-distro install commands in README. |
| Kirigami not packaged on user's distro | Medium | Medium — user must install manually | Provide `apt`, `dnf`, `pacman` install commands. As last resort, fall back to plain QtQuick Controls for critical features. |
| QML property access from worker thread | Low | High — undefined behavior/crash | All `Q_PROPERTY` values updated only on main thread. Workers emit `Signal` → main thread slot updates the property. |
| Hivemind config.yaml format changes | Medium | Low — config load silently fails | Wrap config reader in try/except with logging. UI shows "config load failed" message and allows manual field entry. |
| Qdrant server unreachable | Medium | Medium — search/indexing fails | Every page that queries Qdrant shows `Kirigami.InlineMessage` error banner. Retry button triggers reconnection. |

**Trade-offs:**
- **Kirigami vs portability**: Kirigami is KDE-native. On GNOME, it works but uses Breeze theming. On macOS/Windows, Kirigami works via Qt but looks non-native. This is acceptable — Hivemind is primarily a Linux development tool.
- **QThread vs simplicity**: QThread workers require more boilerplate than async/await, but the boilerplate is predictable and well-understood in Qt.
- **ui/ subdirectory vs monorepo**: A separate `ui/` dir with its own `pyproject.toml` adds a second build target but keeps the core package clean.

## Migration Plan

Phase-based implementation:

1. **Phase 0: Scaffold** — Create `ui/` directory, `pyproject.toml`, bare window that opens
2. **Phase 1: Backend** — `BackendEngine`, managers, models, workers (with stubs)
3. **Phase 2: QML pages** — All 6 pages with Kirigami components
4. **Phase 3: Real integration** — Wire stubs to real Hivemind modules
5. **Phase 4: Polish** — Icons, error states, tests, desktop file

**Rollback:** Delete `ui/` directory and revert `pyproject.toml`. No changes to Hivemind core.

## Open Questions

1. Should the UI be a standalone app (`hivemind-ui`) or an alternative entry point in the existing `hivemind` package?
   - Current plan: standalone entry script at `ui/main.py`, registered as `hivemind-ui` console script
   - Alternative: `hivemind ui` subcommand — requires adding PySide6 dep to root

2. Should we use `pyside6-rcc` to compile QRC resources, or load QML from filesystem during development?
   - Current plan: filesystem loading (simpler for development), QRC for packaging
   - Implement QRC at Phase 4

3. Dark/light theme support — Kirigami follows KDE Breeze automatically on KDE. On non-KDE systems, do we set an explicit palette?

4. Native file dialog or text field for repo path in AddRepoSheet?
   - Text field is simpler and works in all scenarios
   - `Kirigami.FileDialog` would provide native browsing — worth investigating
