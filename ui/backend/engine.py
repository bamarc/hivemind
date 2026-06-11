"""BackendEngine — singleton QObject exposed as the ``backend`` QML context property.

All QML pages access backend services through this engine. Managers provide
stub data in Phases 2-6; real Hivemind core integration comes in Phase 7.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QObject, Signal, Property, Slot

from backend.managers.config_manager import ConfigManager
from backend.managers.search_manager import SearchManager
from backend.managers.server_manager import ServerManager

logger = logging.getLogger(__name__)


class BackendEngine(QObject):
    """Singleton backend engine exposed to QML as the ``backend`` context property.

    Properties
    ----------
    currentIndexing : bool
        Whether an indexing operation is currently in progress.
    serverStatus : str
        ``"running"`` or ``"stopped"``.
    """

    # ── Signals ──────────────────────────────────────────────────────────
    currentIndexingChanged = Signal(bool)
    serverStatusChanged = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._current_indexing = False
        self._server_status = "stopped"

        self._config_mgr = ConfigManager()
        self._search_mgr = SearchManager()
        self._server_mgr = ServerManager()

    # ── Q_PROPERTY: currentIndexing ───────────────────────────────────────

    @Property(bool, notify=currentIndexingChanged)
    def currentIndexing(self) -> bool:
        return self._current_indexing

    @currentIndexing.setter
    def currentIndexing(self, value: bool) -> None:
        if self._current_indexing != value:
            self._current_indexing = value
            self.currentIndexingChanged.emit(value)

    # ── Q_PROPERTY: serverStatus ──────────────────────────────────────────

    @Property(str, notify=serverStatusChanged)
    def serverStatus(self) -> str:
        return self._server_status

    @serverStatus.setter
    def serverStatus(self, value: str) -> None:
        if self._server_status != value:
            self._server_status = value
            self.serverStatusChanged.emit(value)

    # ── Q_INVOKABLE: Dashboard ─────────────────────────────────────────────

    @Slot(result="QVariantMap")
    def getDashboardStats(self) -> dict[str, Any]:
        repos = self._config_mgr.get_repos()
        total_chunks = sum(r["chunks"] for r in repos)
        total_files = sum(1 for r in repos if r["indexed"])
        return {
            "indexedChunks": total_chunks,
            "indexedFiles": total_files,
            "indexedRepos": len([r for r in repos if r["indexed"]]),
            "avgSearchTime": "0.32s",
            "recentSearches": [
                {"query": "authentication flow", "timestamp": "2 min ago"},
                {"query": "database connection pool", "timestamp": "15 min ago"},
                {"query": "embedding generation", "timestamp": "1 hour ago"},
            ],
        }

    # ── Q_INVOKABLE: Repositories ──────────────────────────────────────────

    @Slot(result="QVariantList")
    def getRepos(self) -> list[dict[str, Any]]:
        return self._config_mgr.get_repos()

    @Slot(str, str)
    def addRepo(self, path: str, chunker: str) -> None:
        self._config_mgr.add_repo(path, chunker)

    @Slot(str)
    def removeRepo(self, path: str) -> None:
        self._config_mgr.remove_repo(path)

    @Slot(str)
    def reindexRepo(self, path: str) -> None:
        if self._config_mgr.reindex_repo(path):
            self.currentIndexing = True

    # ── Q_INVOKABLE: Search ───────────────────────────────────────────────

    @Slot(str, int, result="QVariantList")
    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        return self._search_mgr.search(query, limit)

    # ── Q_INVOKABLE: Server ───────────────────────────────────────────────

    @Slot()
    def startServer(self) -> None:
        if self._server_mgr.start():
            self.serverStatus = "running"

    @Slot()
    def stopServer(self) -> None:
        if self._server_mgr.stop():
            self.serverStatus = "stopped"

    @Slot(result="QVariantMap")
    def getServerStats(self) -> dict[str, Any]:
        return self._server_mgr.get_stats()

    # ── Q_INVOKABLE: Indexer ──────────────────────────────────────────────

    @Slot(result="QVariantMap")
    def getIndexerStatus(self) -> dict[str, Any]:
        settings = self._config_mgr.get_settings()
        return {
            "active": self._current_indexing,
            "currentFile": "src/auth/login.py" if self._current_indexing else "",
            "filesDone": 23 if self._current_indexing else 0,
            "filesTotal": 100 if self._current_indexing else 0,
            "eta": "~45s" if self._current_indexing else "",
            "chunkerType": settings["embeddingProvider"],
            "maxChunkSize": 500,
            "overlap": 50,
        }

    @Slot()
    def pauseIndexing(self) -> None:
        logger.info("Indexing paused")

    @Slot()
    def resumeIndexing(self) -> None:
        logger.info("Indexing resumed")

    @Slot()
    def stopIndexing(self) -> None:
        self.currentIndexing = False

    # ── Q_INVOKABLE: Settings ─────────────────────────────────────────────

    @Slot(result="QVariantMap")
    def getSettings(self) -> dict[str, Any]:
        return self._config_mgr.get_settings()

    @Slot("QVariantMap")
    def saveSettings(self, settings_data: dict[str, Any]) -> None:
        self._config_mgr.save_settings(settings_data)
