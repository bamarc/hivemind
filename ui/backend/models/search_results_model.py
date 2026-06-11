"""SearchResultsModel — QAbstractListModel for semantic search results.

Roles exposed to QML:
- ``filePath`` — path to the matched file
- ``lineNumber`` — line number of the match
- ``content`` — matching code snippet
- ``score`` — relevance score (0.0 – 1.0)
- ``language`` — programming language label
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt


class SearchResultsModel(QAbstractListModel):
    """Model backing the search results CardsListView in QML."""

    RoleNames = {
        0: b"filePath",
        1: b"lineNumber",
        2: b"content",
        3: b"score",
        4: b"language",
    }

    def __init__(self, parent: QObject | None = None) -> None:  # noqa: F821
        super().__init__(parent)
        self._items: list[dict[str, Any]] = []

    # ── QAbstractListModel interface ──────────────────────────────────────

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._items)

    def data(self, index: QModelIndex, role: int) -> Any:
        if not index.isValid() or index.row() >= len(self._items):
            return None
        item = self._items[index.row()]
        role_map = {v: k for k, v in self.RoleNames.items()}
        key = role_map.get(role)
        return item.get(key, None) if key else None

    def roleNames(self) -> dict[int, bytes]:
        return self.RoleNames

    # ── Public API ────────────────────────────────────────────────────────

    def set_results(self, results: list[dict[str, Any]]) -> None:
        """Replace all items and notify the view."""
        self.beginResetModel()
        self._items = list(results)
        self.endResetModel()

    def clear(self) -> None:
        self.set_results([])
