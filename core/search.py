"""
Search backend for the Hivemind MCP server.

Provides pluggable web search capabilities. Currently supports
DuckDuckGo (zero-config, no API key). Brave Search API and SearXNG
backends can be added by implementing the corresponding function
and adding a branch in :func:`search_web`.

All HTTP / external library calls are contained within this module
so that :mod:`server.server` never touches the network directly,
respecting the component boundary defined in ``AGENTS.md``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from .config import settings

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A single web search result."""

    title: str
    url: str
    snippet: str


def search_duckduckgo(query: str, max_results: int = 10) -> List[SearchResult]:
    """Search the web using DuckDuckGo (via ``duckduckgo_search``).

    Parameters
    ----------
    query:
        The search query string.
    max_results:
        Maximum number of results to return (default 10, clamped to 1–20).

    Returns
    -------
    list[SearchResult]
        List of search results with title, URL, and snippet.

    Raises
    ------
    ImportError
        If ``duckduckgo-search`` is not installed (install with
        ``uv sync --extra scout`` or ``pip install duckduckgo-search``).
    """
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        raise ImportError(
            "duckduckgo-search is not installed. "
            "Install it with: uv sync --extra scout"
        )

    max_results = max(1, min(max_results, 20))
    results: List[SearchResult] = []

    try:
        with DDGS() as ddgs:
            for item in ddgs.text(query, max_results=max_results):
                results.append(
                    SearchResult(
                        title=item.get("title", "Untitled"),
                        url=item.get("href", ""),
                        snippet=item.get("body", ""),
                    )
                )
    except Exception as exc:
        logger.error("DuckDuckGo search failed for query %r: %s", query, exc)
        # Return partial results if any were collected before the error
        if not results:
            raise

    return results


def search_web(
    query: str,
    max_results: int = 10,
    backend: Optional[str] = None,
) -> List[SearchResult]:
    """Search the web using the configured backend.

    The backend is determined by ``ScoutSettings.search_backend`` and can
    be overridden via the *backend* parameter.

    Parameters
    ----------
    query:
        The search query string.
    max_results:
        Maximum number of results (default 10).
    backend:
        Override the configured backend. One of ``"duckduckgo"``,
        ``"brave"``, ``"searxng"``.  If ``None``, uses the value from
        :attr:`ScoutSettings.search_backend`.

    Returns
    -------
    list[SearchResult]
        Search results with title, URL, and snippet.
    """
    backend = backend or settings.scout.search_backend

    if backend == "duckduckgo":
        return search_duckduckgo(query, max_results=max_results)

    # Future backends:
    # if backend == "brave":
    #     return search_brave(query, max_results=max_results)
    # if backend == "searxng":
    #     return search_searxng(query, max_results=max_results)

    raise ValueError(
        f"Unknown search backend: {backend!r}. "
        f"Supported backends: duckduckgo, brave, searxng"
    )
