"""RepoListModel — QAbstractListModel for the repositories list.

Roles exposed to QML:
- ``name`` — repository name (last path segment)
- ``path`` — filesystem path
- ``indexed`` — whether the repo has been indexed (bool)
- ``chunks`` — number of indexed chunks
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt


class RepoListModel(QAbstractListModel):
    """Model backing the repositories CardsListView in QML."""

    RoleNames = {
        0: b"name",
        1: b"path",
        2: b"indexed",
        3: b"chunks",
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

    def set_repos(self, repos: list[dict[str, Any]]) -> None:
        """Replace all items and notify the view."""
        self.beginResetModel()
        self._items = list(repos)
        self.endResetModel()

    def clear(self) -> None:
        self.set_repos([])
