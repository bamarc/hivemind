"""Tests for backend managers."""

from __future__ import annotations

import pytest

from backend.managers.config_manager import ConfigManager
from backend.managers.search_manager import SearchManager
from backend.managers.server_manager import ServerManager


class TestConfigManager:
    def test_init(self):
        mgr = ConfigManager()
        repos = mgr.get_repos()
        assert len(repos) > 0

    def test_add_and_remove_repo(self):
        mgr = ConfigManager()
        before = len(mgr.get_repos())
        mgr.add_repo("/tmp/test-project", "ast")
        assert len(mgr.get_repos()) == before + 1
        mgr.remove_repo("/tmp/test-project")
        assert len(mgr.get_repos()) == before

    def test_settings_returns_dict(self):
        mgr = ConfigManager()
        settings = mgr.get_settings()
        assert "qdrantHost" in settings
        assert "collectionName" in settings

    def test_reindex_existing(self):
        mgr = ConfigManager()
        repos = mgr.get_repos()
        if repos:
            assert mgr.reindex_repo(repos[0]["path"]) is True

    def test_reindex_nonexistent(self):
        mgr = ConfigManager()
        assert mgr.reindex_repo("/nonexistent/path") is False


class TestSearchManager:
    @pytest.mark.timeout(10)
    def test_search_returns_list(self):
        mgr = SearchManager()
        results = mgr.search("authentication", 3)
        assert isinstance(results, list)
        assert len(results) <= 3

    @pytest.mark.timeout(10)
    def test_search_result_fields(self):
        mgr = SearchManager()
        results = mgr.search("auth", 1)
        if results:
            r = results[0]
            assert "filePath" in r
            assert "content" in r
            assert "score" in r
            assert "language" in r


class TestServerManager:
    def test_initial_state(self):
        mgr = ServerManager()
        assert mgr.is_running is False

    def test_start_stop(self):
        mgr = ServerManager()
        assert mgr.start() is True
        assert mgr.is_running is True
        assert mgr.stop() is True
        assert mgr.is_running is False

    def test_stats_stopped(self):
        mgr = ServerManager()
        stats = mgr.get_stats()
        assert stats["status"] == "stopped"

    def test_stats_running(self):
        mgr = ServerManager()
        mgr.start()
        stats = mgr.get_stats()
        assert stats["status"] == "running"
        assert "tools" in stats
        mgr.stop()
