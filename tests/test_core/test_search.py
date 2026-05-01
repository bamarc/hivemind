"""
Tests for :mod:`core.search` — the web search backend.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from core.search import SearchResult, search_duckduckgo, search_web


# ---------------------------------------------------------------------------
# Mock duckduckgo_search module — DDGS is imported lazily inside
# search_duckduckgo(), so we inject a fake module into sys.modules.
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_ddgs_module() -> MagicMock:
    """Inject a mock ``duckduckgo_search`` module with a fake DDGS class."""
    mock_ddgs = MagicMock()
    mock_instance = MagicMock()
    mock_instance.__enter__.return_value = mock_instance
    mock_instance.__exit__.return_value = None
    mock_instance.text.return_value = [
        {
            "title": "Python asyncio Docs",
            "href": "https://docs.python.org/3/library/asyncio.html",
            "body": "Official documentation for asyncio module.",
        },
        {
            "title": "Real Python Async IO",
            "href": "https://realpython.com/async-io-python/",
            "body": "A comprehensive guide to async IO in Python.",
        },
    ]
    mock_ddgs.return_value = mock_instance
    mock_module = MagicMock()
    mock_module.DDGS = mock_ddgs
    sys.modules["duckduckgo_search"] = mock_module
    yield mock_instance
    sys.modules.pop("duckduckgo_search", None)


@pytest.fixture
def mock_ddgs_single() -> MagicMock:
    """Mock with a single result (for dispatcher tests)."""
    mock_ddgs = MagicMock()
    mock_instance = MagicMock()
    mock_instance.__enter__.return_value = mock_instance
    mock_instance.__exit__.return_value = None
    mock_instance.text.return_value = [
        {
            "title": "Test Result",
            "href": "https://example.com",
            "body": "A test result.",
        },
    ]
    mock_ddgs.return_value = mock_instance
    mock_module = MagicMock()
    mock_module.DDGS = mock_ddgs
    sys.modules["duckduckgo_search"] = mock_module
    yield mock_instance
    sys.modules.pop("duckduckgo_search", None)


class TestSearchDuckDuckGo:
    """Tests for the DuckDuckGo search backend."""

    def test_returns_results(self, mock_ddgs_module: MagicMock):
        """A valid query should return SearchResult objects."""
        results = search_duckduckgo("python asyncio", max_results=10)
        assert len(results) == 2
        assert results[0].title == "Python asyncio Docs"
        assert results[0].url == "https://docs.python.org/3/library/asyncio.html"
        assert results[0].snippet == "Official documentation for asyncio module."

    def test_empty_results(self, mock_ddgs_module: MagicMock):
        """When DuckDuckGo returns nothing, return an empty list."""
        mock_ddgs_module.text.return_value = []
        results = search_duckduckgo("xyznonexistent12345")
        assert results == []

    def test_max_results_clamped(self, mock_ddgs_module: MagicMock):
        """max_results should be clamped to 1..20."""
        search_duckduckgo("test", max_results=50)
        call_kwargs = mock_ddgs_module.text.call_args.kwargs
        assert call_kwargs["max_results"] == 20

        mock_ddgs_module.text.reset_mock()
        search_duckduckgo("test", max_results=0)
        call_kwargs = mock_ddgs_module.text.call_args.kwargs
        assert call_kwargs["max_results"] == 1

    def test_error_returns_partial(self, mock_ddgs_module: MagicMock):
        """If DDGS returns a single result, handle normally."""
        mock_ddgs_module.text.return_value = [
            {
                "title": "Result 1",
                "href": "https://example.com/1",
                "body": "First result",
            },
        ]
        results = search_duckduckgo("test")
        assert len(results) == 1

    def test_import_error(self):
        """When duckduckgo-search is not installed, raise ImportError."""
        # Ensure the module is NOT cached in sys.modules
        sys.modules.pop("duckduckgo_search", None)
        # The package is installed in the test environment, so we need to
        # simulate the import failing by patching __import__.
        with patch("builtins.__import__", side_effect=ImportError("mocked")):
            with pytest.raises(ImportError, match="duckduckgo-search"):
                search_duckduckgo("test")


class TestSearchWeb:
    """Tests for the pluggable search_web dispatcher."""

    def test_dispatches_to_duckduckgo(self, mock_ddgs_single: MagicMock):
        """Default backend should be duckduckgo."""
        results = search_web("test")
        assert len(results) == 1
        assert results[0].title == "Test Result"

    def test_explicit_backend(self, mock_ddgs_single: MagicMock):
        """Explicit backend='duckduckgo' should work."""
        results = search_web("test", backend="duckduckgo")
        assert len(results) == 1

    def test_unknown_backend_raises(self):
        """An unknown backend should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown search backend"):
            search_web("test", backend="nonexistent")


class TestSearchResult:
    """Tests for the SearchResult dataclass."""

    def test_creation(self):
        """Should create a SearchResult with title, url, snippet."""
        result = SearchResult(
            title="Docs",
            url="https://example.com",
            snippet="Some docs.",
        )
        assert result.title == "Docs"
        assert result.url == "https://example.com"
        assert result.snippet == "Some docs."
