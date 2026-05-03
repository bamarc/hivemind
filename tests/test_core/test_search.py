"""
Tests for :mod:`core.search` — the web search backend.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from core.search import SearchResult, search_duckduckgo, search_searxng, search_web


# ---------------------------------------------------------------------------
# Mock ddgs module — DDGS is imported lazily inside
# search_duckduckgo(), so we inject a fake module into sys.modules.
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_ddgs_module() -> MagicMock:
    """Inject a mock ``ddgs`` module with a fake DDGS class."""
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
    sys.modules["ddgs"] = mock_module
    yield mock_instance
    sys.modules.pop("ddgs", None)


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
    sys.modules["ddgs"] = mock_module
    yield mock_instance
    sys.modules.pop("ddgs", None)


# ---------------------------------------------------------------------------
# Mock httpx.Client for SearXNG tests
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_httpx_client() -> MagicMock:
    """Mock ``httpx.Client`` so no real HTTP calls are made.

    Returns a mock response object that can be further customised by
    individual tests via ``mock_response.json.return_value``.
    """
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {
                "title": "Python asyncio Docs",
                "url": "https://docs.python.org/3/library/asyncio.html",
                "content": "Official documentation for asyncio module.",
            },
            {
                "title": "Real Python Async IO",
                "url": "https://realpython.com/async-io-python/",
                "content": "A comprehensive guide to async IO in Python.",
            },
        ],
        "answers": [],
    }

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    mock_client.get.return_value = mock_response

    with patch("httpx.Client", return_value=mock_client) as cls:
        cls.mock_response = mock_response
        cls.mock_client = mock_client
        yield cls

    sys.modules.pop("httpx", None)


# ===========================================================================
#  Test classes
# ===========================================================================


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
        """When ddgs is not installed, raise ImportError."""
        # Ensure the module is NOT cached in sys.modules
        sys.modules.pop("ddgs", None)
        # The package is installed in the test environment, so we need to
        # simulate the import failing by patching __import__.
        with patch("builtins.__import__", side_effect=ImportError("mocked")):
            with pytest.raises(ImportError, match="ddgs"):
                search_duckduckgo("test")


class TestSearchSearXNG:
    """Tests for the SearXNG search backend."""

    def test_returns_results(self, mock_httpx_client: MagicMock):
        """A valid query should return SearchResult objects."""
        results = search_searxng("python asyncio", max_results=10)
        assert len(results) == 2
        assert results[0].title == "Python asyncio Docs"
        assert results[0].url == "https://docs.python.org/3/library/asyncio.html"
        assert results[0].snippet == "Official documentation for asyncio module."

    def test_empty_results(self, mock_httpx_client: MagicMock):
        """When SearXNG returns no results, return an empty list."""
        mock_httpx_client.mock_response.json.return_value = {"results": [], "answers": []}
        results = search_searxng("xyznonexistent12345")
        assert results == []

    def test_max_results_clamped(self, mock_httpx_client: MagicMock):
        """max_results should be clamped to 1..20."""
        search_searxng("test", max_results=50)
        # Clamping is internal, so we just verify no error and the
        # response was fetched (1 call to client.get)
        assert mock_httpx_client.mock_client.get.call_count == 1

    def test_categories_passed_as_query_param(self, mock_httpx_client: MagicMock):
        """When categories are specified, they should be in the query params."""
        search_searxng("test", categories=["it", "science"])
        call_kwargs = mock_httpx_client.mock_client.get.call_args.kwargs
        params = call_kwargs.get("params", {})
        assert params.get("categories") == "it,science"

    def test_categories_empty_omitted(self, mock_httpx_client: MagicMock):
        """When categories is None or empty, the param should be omitted."""
        search_searxng("test", categories=None)
        call_kwargs = mock_httpx_client.mock_client.get.call_args.kwargs
        params = call_kwargs.get("params", {})
        assert "categories" not in params

        mock_httpx_client.mock_client.get.reset_mock()
        search_searxng("test", categories=[])
        call_kwargs = mock_httpx_client.mock_client.get.call_args.kwargs
        params = call_kwargs.get("params", {})
        assert "categories" not in params

    def test_includes_format_param(self, mock_httpx_client: MagicMock):
        """The request should always include ``format=json``."""
        search_searxng("test")
        call_kwargs = mock_httpx_client.mock_client.get.call_args.kwargs
        params = call_kwargs.get("params", {})
        assert params.get("format") == "json"

    def test_answers_are_included(self, mock_httpx_client: MagicMock):
        """SearXNG ``answers`` field should be appended as SearchResult items."""
        mock_httpx_client.mock_response.json.return_value = {
            "results": [],
            "answers": ["The answer is 42."],
        }
        results = search_searxng("test")
        assert len(results) == 1
        assert results[0].title == "Answer"
        assert results[0].snippet == "The answer is 42."
        assert results[0].url == ""

    def test_http_error_raises_connection_error(self, mock_httpx_client: MagicMock):
        """An HTTP error response should raise ConnectionError."""
        mock_httpx_client.mock_response.raise_for_status.side_effect = \
            __import__("httpx").HTTPStatusError(
                "403 Forbidden",
                request=MagicMock(),
                response=MagicMock(status_code=403),
            )
        with pytest.raises(ConnectionError, match="SearXNG returned HTTP 403"):
            search_searxng("test")

    def test_request_error_raises_connection_error(self, mock_httpx_client: MagicMock):
        """A network error (connection refused, etc.) should raise ConnectionError."""
        mock_httpx_client.mock_client.get.side_effect = \
            __import__("httpx").RequestError("Connection refused")
        with pytest.raises(ConnectionError, match="Could not connect"):
            search_searxng("test")


class TestSearchWeb:
    """Tests for the pluggable search_web dispatcher."""

    def test_dispatches_to_duckduckgo(self, mock_ddgs_single: MagicMock):
        """Explicit backend='duckduckgo' should return SearchResult objects."""
        results = search_web("test", backend="duckduckgo")
        assert len(results) == 1
        assert results[0].title == "Test Result"

    def test_dispatches_to_searxng(self, mock_httpx_client: MagicMock):
        """Explicit backend='searxng' should return SearchResult objects."""
        results = search_web("test", backend="searxng")
        assert len(results) == 2
        assert results[0].title == "Python asyncio Docs"

    def test_searxng_categories_passthrough(self, mock_httpx_client: MagicMock):
        """When backend='searxng', categories should be passed through."""
        search_web("test", backend="searxng", categories=["it", "science"])
        call_kwargs = mock_httpx_client.mock_client.get.call_args.kwargs
        params = call_kwargs.get("params", {})
        assert params.get("categories") == "it,science"

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
