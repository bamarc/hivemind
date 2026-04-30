"""
Tests for :mod:`server.api` — the FastAPI REST endpoints.

Uses FastAPI's ``TestClient`` to send real HTTP requests through the
middleware stack while Qdrant and the embedder remain mocked at the
``core.clients`` module level by the global ``conftest.py``.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from server.api import app

client = TestClient(app)


class TestHealth:
    def test_healthy(self, mock_qdrant: MagicMock):
        """When Qdrant is reachable, the endpoint should report 'healthy'."""
        mock_qdrant.get_collections.return_value = MagicMock()
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["components"]["qdrant"]["status"] == "connected"

    def test_degraded(self, mock_qdrant: MagicMock):
        """When Qdrant is unreachable, the endpoint should report 'degraded'."""
        mock_qdrant.get_collections.side_effect = ConnectionError("Down")
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["components"]["qdrant"]["status"] == "disconnected"


class TestEmbed:
    def test_returns_embedding(self):
        """POST /embed with a text should return a vector and model name."""
        resp = client.post("/embed", json={"text": "hello world"})
        assert resp.status_code == 200
        data = resp.json()
        assert "embedding" in data
        assert isinstance(data["embedding"], list)
        assert len(data["embedding"]) > 0
        assert "model" in data

    def test_handles_server_error(self, mock_embedder: MagicMock):
        """When the embedder fails, the endpoint should return 500."""
        def failing_embed(*args, **kwargs):
            raise RuntimeError("API down")
        mock_embedder.embeddings.create = failing_embed
        resp = client.post("/embed", json={"text": "fail"})
        assert resp.status_code == 500


class TestSearch:
    def test_returns_results(self, mock_qdrant: MagicMock):
        """POST /search with a query should return ranked results."""
        mock_qdrant.query_points.return_value = MagicMock(
            points=[
                MagicMock(
                    id=1,
                    score=0.95,
                    payload={
                        "filepath": "/test.py",
                        "content": "def foo(): pass",
                        "chunk_index": 0,
                    },
                )
            ]
        )
        resp = client.post("/search", json={"query": "find foo"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["filepath"] == "/test.py"
        assert data["results"][0]["score"] == 0.95

    def test_empty_results(self, mock_qdrant: MagicMock):
        """When Qdrant returns no points, the endpoint should return an empty list."""
        mock_qdrant.query_points.return_value = MagicMock(points=[])
        resp = client.post("/search", json={"query": "nothing"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["results"] == []

    def test_handles_exception(self, mock_qdrant: MagicMock):
        """When an exception occurs, the endpoint should return 500."""
        mock_qdrant.query_points.side_effect = RuntimeError("Search crashed")
        resp = client.post("/search", json={"query": "error"})
        assert resp.status_code == 500


class TestMetrics:
    def test_metrics_enabled(self, mock_qdrant: MagicMock):
        """When observability is enabled, the metrics endpoint should return data."""
        mock_qdrant.get_collection.return_value = MagicMock(points_count=42)
        with patch("server.api.settings.observability_metrics_enabled", True):
            resp = client.get("/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_chunks_in_db" in data
        assert data["total_chunks_in_db"] == 42
