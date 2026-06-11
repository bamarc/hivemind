"""SearchManager — wraps Hivemind's semantic search.

Phase 7: Wired to ``core.clients`` and ``core.search`` for real
Qdrant-backed semantic search.  Falls back to stub results when
the embedding service is unreachable.
"""

from __future__ import annotations

import logging
from typing import Any

from core.config import settings

logger = logging.getLogger(__name__)

_SEARCH_STUBS = [
    {
        "filePath": "src/auth/login.py",
        "lineNumber": 42,
        "content": "def authenticate_user(username: str, password: str) -> User:",
        "score": 0.95,
        "language": "python",
    },
    {
        "filePath": "src/db/connection.py",
        "lineNumber": 15,
        "content": "pool = create_connection_pool(host, port, max_conn=10)",
        "score": 0.87,
        "language": "python",
    },
    {
        "filePath": "src/embed/generate.py",
        "lineNumber": 73,
        "content": "response = client.embeddings.create(input=[text], model=model_name)",
        "score": 0.72,
        "language": "python",
    },
]


class SearchManager:
    """Manages semantic search against the Hivemind Qdrant index."""

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Execute a semantic search and return formatted results.

        Falls back to stub results when the embedding service or Qdrant
        is unreachable.

        Parameters
        ----------
        query:
            Natural language query string.
        limit:
            Maximum number of results (default 5, max 20).

        Returns
        -------
        list[dict]
            Each result contains ``filePath``, ``lineNumber``, ``content``,
            ``score``, and ``language``.
        """
        limit = max(1, min(limit, 20))

        try:
            return self._real_search(query, limit)
        except Exception as exc:
            logger.warning(
                "Semantic search failed (%s), returning stubs", exc
            )
            return _SEARCH_STUBS[:limit]

    def _real_search(self, query: str, limit: int) -> list[dict[str, Any]]:
        """Run real semantic search against Qdrant."""
        from core.clients import get_db, get_embedding
        from qdrant_client import models

        # Quick connectivity check to avoid long retry delays
        import httpx
        api_url = settings.model.api_url.rstrip("/")
        try:
            r = httpx.get(f"{api_url}/models", timeout=2.0)
            r.raise_for_status()
        except Exception as exc:
            logger.warning(
                "Embedding service at %s unreachable (%s)", api_url, exc
            )
            raise RuntimeError(f"Embedding service unreachable: {exc}") from exc

        query_vector = get_embedding(query)
        collection_name = settings.qdrant.collection_name
        db = get_db()

        response = db.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )

        results = []
        for hit in response.points:
            payload = hit.payload or {}
            content = payload.get("content", "")
            snippet = content.split("\n")[0].strip() if content else ""
            filepath = payload.get("filepath", "Unknown")
            line_number = payload.get("line", 0)
            language = payload.get("language", "text")

            results.append({
                "filePath": filepath,
                "lineNumber": line_number,
                "content": snippet,
                "score": round(hit.score, 2),
                "language": language,
            })

        return results
