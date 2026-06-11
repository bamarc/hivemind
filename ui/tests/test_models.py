"""Tests for backend models and workers."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtTest import QSignalSpy

from backend.models.search_results_model import SearchResultsModel
from backend.models.repo_list_model import RepoListModel
from backend.workers.index_worker import IndexWorker
from backend.workers.search_worker import SearchWorker


# ── Models ────────────────────────────────────────────────────────────────


class TestSearchResultsModel:
    def test_empty_on_init(self):
        model = SearchResultsModel()
        assert model.rowCount() == 0

    def test_set_results(self):
        model = SearchResultsModel()
        results = [
            {"filePath": "a.py", "lineNumber": 1, "content": "x", "score": 0.9, "language": "python"}
        ]
        model.set_results(results)
        assert model.rowCount() == 1

    def test_clear(self):
        model = SearchResultsModel()
        model.set_results([{"filePath": "a.py", "lineNumber": 1, "content": "x", "score": 0.9, "language": "python"}])
        model.clear()
        assert model.rowCount() == 0

    def test_role_names_match_fields(self):
        model = SearchResultsModel()
        roles = model.roleNames()
        fields = {"filePath", "lineNumber", "content", "score", "language"}
        assert set(roles.values()) == {f.encode() for f in fields}


class TestRepoListModel:
    def test_empty_on_init(self):
        model = RepoListModel()
        assert model.rowCount() == 0

    def test_set_repos(self):
        model = RepoListModel()
        repos = [{"name": "test", "path": "/tmp", "indexed": True, "chunks": 10}]
        model.set_repos(repos)
        assert model.rowCount() == 1

    def test_role_names_match_fields(self):
        model = RepoListModel()
        roles = model.roleNames()
        fields = {"name", "path", "indexed", "chunks"}
        assert set(roles.values()) == {f.encode() for f in fields}


# ── Workers ───────────────────────────────────────────────────────────────


@pytest.fixture
def qapp():
    """Provide a QCoreApplication for signal/slot tests."""
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app


def test_index_worker_signals(qapp):
    """IndexWorker should emit progress and finished."""
    worker = IndexWorker("/tmp/test", "ast")
    progress_spy = QSignalSpy(worker.progress)
    finished_spy = QSignalSpy(worker.finished)

    worker.start()
    assert worker.wait(12000), "IndexWorker did not finish in time"

    assert progress_spy.count() == 50, f"Expected 50 progress, got {progress_spy.count()}"
    assert finished_spy.count() == 1
    ok = finished_spy.at(0)[0]
    assert ok is True


def test_index_worker_cancel(qapp):
    """IndexWorker should stop early when cancelled."""
    worker = IndexWorker("/tmp/test", "ast")
    finished_spy = QSignalSpy(worker.finished)

    worker.start()
    worker.stop()  # Request stop early
    assert worker.wait(5000), "IndexWorker did not stop"

    assert finished_spy.count() == 1
    ok = finished_spy.at(0)[0]
    assert ok is False


def test_search_worker_signals(qapp):
    """SearchWorker should emit results_ready."""
    worker = SearchWorker("auth flow", 3)
    spy = QSignalSpy(worker.results_ready)

    worker.start()
    assert worker.wait(5000), "SearchWorker did not finish in time"

    assert spy.count() == 1
    results = spy.at(0)[0]
    assert len(results) == 3
    assert results[0]["filePath"] == "src/auth/login.py"
