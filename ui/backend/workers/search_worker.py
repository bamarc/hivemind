"""SearchWorker — QThread that runs semantic search on a background thread.

Phase 7: Wired to the ``SearchManager`` for real Qdrant-backed search.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QThread, Signal

from backend.managers.search_manager import SearchManager

logger = logging.getLogger(__name__)


class SearchWorker(QThread):
    """Search worker that runs semantic search on a background thread.

    Signals
    -------
    results_ready(results: list[dict])
        Emitted when search results are available.
    """

    results_ready = Signal(list)

    def __init__(
        self,
        query: str,
        limit: int = 5,
        parent: QObject | None = None,  # noqa: F821
    ) -> None:
        super().__init__(parent)
        self._query = query
        self._limit = limit

    def run(self) -> None:
        """Run the search via SearchManager (real Qdrant, fallback to stub)."""
        logger.info("SearchWorker started: query=%r limit=%d", self._query, self._limit)

        mgr = SearchManager()
        results = mgr.search(self._query, self._limit)
        self.results_ready.emit(results)
