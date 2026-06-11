# Hivemind Kirigami UI

A convergent desktop GUI for [Hivemind](https://github.com/nousresearch/hivemind), built with **PySide6** and **Kirigami QML**.

## Prerequisites

### Kirigami (system package)

Install the Kirigami QML module via your distribution:

- **Arch Linux**: `pacman -S qqc2-desktop-style kirigami`
- **Debian / Ubuntu**: `apt install qml6-module-org-kde-kirigami qml6-module-org-kde-kquickstyle`
- **Fedora**: `dnf install kf6-kirigami2 kf6-kirigami2-devel`
- **openSUSE**: `zypper install kirigami2`
- **macOS / Windows**: Kirigami is included with PySide6 — no system package needed.

### Python dependencies

```bash
cd ui
uv sync
```

## Running

```bash
cd ui
uv run python main.py
```

## Development

- **Backend** (`backend/`): Python PySide6 code — `BackendEngine`, managers, models, workers
- **QML** (`qml/`): Kirigami QML pages, components, and dialogs
- **Tests**: `uv run pytest tests/ -v`

## Project Structure

```
ui/
├── backend/
│   ├── engine.py          # BackendEngine QObject singleton
│   ├── managers/
│   │   ├── config_manager.py
│   │   ├── search_manager.py
│   │   └── server_manager.py
│   ├── models/
│   │   ├── search_results_model.py
│   │   └── repo_list_model.py
│   └── workers/
│       ├── index_worker.py
│       └── search_worker.py
├── qml/
│   ├── main.qml
│   ├── components/
│   │   ├── StatusCard.qml
│   │   ├── RepoDelegate.qml
│   │   └── SearchResultDelegate.qml
│   ├── dialogs/
│   │   ├── AddRepoSheet.qml
│   │   └── ServerLogSheet.qml
│   └── pages/
│       ├── DashboardPage.qml
│       ├── RepositoriesPage.qml
│       ├── SearchPage.qml
│       ├── ServerPage.qml
│       ├── IndexerPage.qml
│       └── SettingsPage.qml
├── resources/
├── tests/
├── main.py
└── pyproject.toml
```
