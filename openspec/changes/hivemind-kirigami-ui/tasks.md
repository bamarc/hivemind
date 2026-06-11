## 1. Project Scaffold

- [x] 1.1 Create `ui/` directory structure with `ui/__init__.py`, `ui/backend/`, `ui/qml/`, `ui/tests/`
- [x] 1.2 Write `ui/pyproject.toml` with PySide6 dependency and path dependency on parent hivemind package
- [x] 1.3 Write `ui/.gitignore` (pycache, qmlc, jsc)
- [x] 1.4 Write `ui/README.md` with prerequisites, install commands, and run instructions
- [x] 1.5 Verify: `cd ui && uv run python -c "from PySide6.QtCore import *; print('PySide6 OK')"`

## 2. Minimal Window (Phase 0)

- [x] 2.1 Write `ui/backend/__init__.py` and `ui/backend/engine.py` with minimal `BackendEngine(QObject)` stub
- [x] 2.2 Write `ui/qml/main.qml` with `Kirigami.ApplicationWindow`, 960x640, `GlobalDrawer` with 6 nav actions
- [x] 2.3 Write `ui/main.py` entry point: `QGuiApplication` + `QQmlApplicationEngine` + context property registration
- [x] 2.4 Verify: `cd ui && uv run python main.py` opens a Kirigami window with functional sidebar

## 3. Backend Managers (Phase 1)

- [x] 3.1 Write `ui/backend/managers/config_manager.py` — repo CRUD against hivemind's config.yaml
- [x] 3.2 Write `ui/backend/managers/search_manager.py` — wraps `hivemind.core.search` with stub results
- [x] 3.3 Write `ui/backend/managers/server_manager.py` — start/stop MCP server, query status
- [x] 3.4 Write `ui/backend/engine.py` full version — Q_PROPERTY for `currentIndexing`/`serverStatus`, Q_INVOKABLE for all operations
- [x] 3.5 Verify: `cd ui && uv run python -c "from backend.engine import BackendEngine; b = BackendEngine(); print(b.getRepos()); print(b.search('test', 2))"`

## 4. Backend Models (Phase 1)

- [x] 4.1 Write `ui/backend/models/search_results_model.py` — `QAbstractListModel` with roles: path, line, content, score, language
- [x] 4.2 Write `ui/backend/models/repo_list_model.py` — `QAbstractListModel` with roles: name, path, indexed, chunks
- [x] 4.3 Write `ui/backend/workers/index_worker.py` — `QThread` with `progress(files_done, files_total)` and `finished(success, message)` signals
- [x] 4.4 Write `ui/backend/workers/search_worker.py` — `QThread` with `results_ready(list)` signal
- [x] 4.5 Verify: workers emit signals correctly via pytest

## 5. Kirigami QML Pages (Phase 2)

- [x] 5.1 Write `ui/qml/components/StatusCard.qml` — `Kirigami.AbstractCard` with icon, label, value, color
- [x] 5.2 Write `ui/qml/pages/DashboardPage.qml` — 2x2 StatusCard grid + recent activity section
- [x] 5.3 Write `ui/qml/components/RepoDelegate.qml` — repo card with name, path, status, buttons
- [x] 5.4 Write `ui/qml/dialogs/AddRepoSheet.qml` — `Kirigami.OverlaySheet` with path field + chunker combo
- [x] 5.5 Write `ui/qml/pages/RepositoriesPage.qml` — `Kirigami.CardsListView` + add action + OverlaySheet
- [x] 5.6 Write `ui/qml/components/SearchResultDelegate.qml` — result card with path:line, content, score, language
- [x] 5.7 Write `ui/qml/pages/SearchPage.qml` — search field, filter checkboxes, CardsListView
- [x] 5.8 Write `ui/qml/pages/ServerPage.qml` — status banner, start/stop, stats card, registered tools, log sheet
- [x] 5.9 Write `ui/qml/dialogs/ServerLogSheet.qml` — OverlaySheet with monospace log text area
- [x] 5.10 Write `ui/qml/pages/IndexerPage.qml` — progress card, chunker config form, pause/stop controls
- [x] 5.11 Write `ui/qml/pages/SettingsPage.qml` — Qdrant config, embedding model config, file watcher config, save/reset

## 6. Navigation Integration (Phase 2)

- [x] 6.1 Wire GlobalDrawer actions to pageStack navigation (all 6 pages)
- [x] 6.2 Set pageStack.initialPage to DashboardPage.qml
- [x] 6.3 Verify all page transitions work correctly by running the app

## 7. Real Backend Integration (Phase 3)

- [x] 7.1 Wire `ConfigManager` to `hivemind.core.config.HivemindConfig` — replace all stub data with real config reads/writes
- [x] 7.2 Wire `SearchManager` to `hivemind.core.search.semantic_search()` — replace stub results with real Qdrant queries
- [x] 7.3 Wire `ServerManager` to `hivemind.server` — start/stop actual MCP server process
- [x] 7.4 Wire `IndexWorker` to `hivemind.indexer.manager.IndexManager` — replace sleep stub with real indexing with progress callbacks
- [x] 7.5 Verify: search returns real results from Qdrant, indexing shows real progress, server starts/stops

## 8. Polish & Packaging (Phase 4)

- [x] 8.1 Create `ui/resources/resources.qrc` with app icon
- [x] 8.2 Create `ui/org.hivemind.ui.desktop` desktop entry file
- [x] 8.3 Add `Kirigami.InlineMessage` error banners to all pages for connection failure handling
- [x] 8.4 Add loading states (spinner/OverlaySheet) for async operations
- [x] 8.5 Add empty-state placeholder labels for all list views
- [x] 8.6 Write `ui/tests/test_models.py` — unit tests for SearchResultsModel and RepoListModel
- [x] 8.7 Write `ui/tests/test_managers.py` — unit tests for ConfigManager add/remove repo
- [x] 8.8 Run full test suite: `cd ui && uv run pytest tests/ -v` — all tests pass

## 9. Documentation

- [x] 9.1 Update `docs/` with AsciiDoc page about the new Kirigami UI
- [x] 9.2 Document per-distro Kirigami installation commands in README
- [x] 9.3 Add screenshots to README showing each of the 6 pages
- [x] 9.4 Write a short `ui/QUICKSTART.md` for UI-specific developer onboarding
