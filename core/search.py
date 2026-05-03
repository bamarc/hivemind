"""
Search backend for the Hivemind MCP server.

Provides pluggable web search capabilities. Currently supports
DuckDuckGo (zero-config, no API key) and SearXNG (self-hosted metasearch
engine). Brave Search API can be added by implementing the corresponding
function and adding a branch in :func:`search_web`.

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
    """Search the web using DuckDuckGo (via ``ddgs``).

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
        If ``ddgs`` is not installed (install with
        ``uv sync --extra scout`` or ``pip install ddgs``).
    """
    try:
        from ddgs import DDGS
    except ImportError:
        raise ImportError(
            "ddgs is not installed. "
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


def search_searxng(
    query: str,
    max_results: int = 10,
    categories: Optional[List[str]] = None,
) -> List[SearchResult]:
    """Search the web using a self-hosted SearXNG instance.

    Parameters
    ----------
    query:
        The search query string.
    max_results:
        Maximum number of results to return (default 10, clamped to 1–20).
    categories:
        Optional list of SearXNG search categories (e.g. ``["it", "science"]``).
        If empty or ``None``, all categories are searched.
        Ignored by non-SearXNG backends.

    Returns
    -------
    list[SearchResult]
        List of search results with title, URL, and snippet.

    Raises
    ------
    ImportError
        If ``httpx`` is not installed.
    ConnectionError
        If the SearXNG instance is unreachable or returns an error status.
    """
    try:
        import httpx
    except ImportError:
        raise ImportError(
            "httpx is not installed. "
            "Install it with: uv add httpx"
        )

    max_results = max(1, min(max_results, 20))
    searxng_url = settings.scout.searxng_url.rstrip("/")

    # Build query parameters
    params: dict = {
        "q": query,
        "format": "json",
        "pageno": 1,
    }

    # Add categories if specified (comma-separated)
    if categories:
        params["categories"] = ",".join(categories)

    results: List[SearchResult] = []

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(
                f"{searxng_url}/search",
                params=params,
            )
            response.raise_for_status()
            data = response.json()

        for item in data.get("results", []):
            results.append(
                SearchResult(
                    title=item.get("title", "Untitled"),
                    url=item.get("url", ""),
                    snippet=item.get("content", ""),
                )
            )

        # Also include any "answers" SearXNG may return
        for item in data.get("answers", []):
            results.append(
                SearchResult(
                    title="Answer",
                    url="",
                    snippet=str(item),
                )
            )

    except httpx.HTTPStatusError as exc:
        logger.error(
            "SearXNG returned HTTP %s for query %r: %s",
            exc.response.status_code,
            query,
            exc,
        )
        raise ConnectionError(
            f"SearXNG returned HTTP {exc.response.status_code}. "
            f"Check that the instance at {searxng_url} is running and JSON format is enabled."
        ) from exc
    except httpx.RequestError as exc:
        logger.error("SearXNG request failed for query %r: %s", query, exc)
        raise ConnectionError(
            f"Could not connect to SearXNG at {searxng_url}. "
            f"Check that the instance is running and reachable."
        ) from exc

    return results


def search_web(
    query: str,
    max_results: int = 10,
    backend: Optional[str] = None,
    categories: Optional[List[str]] = None,
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
    categories:
        Optional list of search categories (currently only used by
        ``"searxng"`` backend).  Ignored for other backends.

    Returns
    -------
    list[SearchResult]
        Search results with title, URL, and snippet.
    """
    backend = backend or settings.scout.search_backend

    if backend == "duckduckgo":
        return search_duckduckgo(query, max_results=max_results)

    if backend == "searxng":
        return search_searxng(query, max_results=max_results, categories=categories)

    # Future backends:
    # if backend == "brave":
    #     return search_brave(query, max_results=max_results)

    raise ValueError(
        f"Unknown search backend: {backend!r}. "
        f"Supported backends: duckduckgo, brave, searxng"
    )
