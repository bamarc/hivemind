"""
Tests for :mod:`core.clients`.

These tests validate the embedding API wrapper functions,
Qdrant collection initialisation, and connection health check.
All external clients (Qdrant, OpenAI) are mocked by the global
``conftest.py`` — no real infrastructure is needed.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from core.clients import (
    check_qdrant_connection,
    get_embedding,
    get_embeddings_batch,
    init_collection,
)
from core.config import settings

# ======================================================================
#  get_embeddings_batch
# ======================================================================


class TestGetEmbeddingsBatch:
    def test_single_text_returns_single_vector(self):
        """A single text should return a list with one embedding vector."""
        results = get_embeddings_batch(["hello world"])
        assert len(results) == 1
        assert len(results[0]) == settings.model.embedding_dim

    def test_multiple_texts_return_matching_count(self):
        """N texts should produce N embedding vectors."""
        texts = ["first", "second", "third"]
        results = get_embeddings_batch(texts)
        assert len(results) == len(texts)
        for vec in results:
            assert len(vec) == settings.model.embedding_dim

    def test_empty_input_returns_empty_list(self):
        """An empty list should short-circuit and return ``[]``."""
        assert get_embeddings_batch([]) == []

    def test_batch_split_respected(self, mock_embedder: MagicMock):
        """When the input exceeds ``batch_size``, the embedder should be
        called multiple times."""
        original_create = mock_embedder.embeddings.create

        call_count = 0

        def tracking_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return original_create(*args, **kwargs)

        mock_embedder.embeddings.create = tracking_create

        batch = ["text"] * (settings.model.batch_size * 2 + 1)
        results = get_embeddings_batch(batch)

        assert call_count >= 2, (
            f"Expected at least 2 embedder calls for "
            f"{len(batch)} items (batch_size={settings.model.batch_size}), "
            f"got {call_count}"
        )
        assert len(results) == len(batch)

        mock_embedder.embeddings.create = original_create  # restore

    def test_retry_on_transient_failure(self, mock_embedder: MagicMock):
        """The tenacity retry decorator should re-try when the API raises
        a transient exception."""
        original_create = mock_embedder.embeddings.create
        attempt = 0

        def flaky_create(*args, **kwargs):
            nonlocal attempt
            attempt += 1
            if attempt < 2:
                raise ConnectionError("Transient error")
            return original_create(*args, **kwargs)

        mock_embedder.embeddings.create = flaky_create

        results = get_embeddings_batch(["retry me"])
        assert len(results) == 1
        assert attempt >= 2

        mock_embedder.embeddings.create = original_create

    def test_raises_after_retries_exhausted(self, mock_embedder: MagicMock):
        """After all retry attempts are exhausted the original exception
        should propagate."""
        def always_fail(*_args, **_kwargs):
            raise RuntimeError("Always failing")

        mock_embedder.embeddings.create = always_fail

        with pytest.raises(RuntimeError, match="Always failing"):
            get_embeddings_batch(["fail"])

# ======================================================================
#  get_embedding
# ======================================================================


class TestGetEmbedding:
    def test_single_text_returns_vector(self):
        """Wrapper should return a single embedding vector (not a list of lists)."""
        result = get_embedding("test query")
        assert isinstance(result, list)
        assert len(result) == settings.model.embedding_dim
        # All values should be floats
        assert all(isinstance(v, float) for v in result)

    def test_empty_text_returns_vector(self):
        """Even an empty string should get embedded (the mock doesn't care)."""
        result = get_embedding("")
        assert isinstance(result, list)
        assert len(result) == settings.model.embedding_dim

# ======================================================================
#  check_qdrant_connection
# ======================================================================


class TestCheckQdrantConnection:
    def test_healthy_when_get_collections_succeeds(self, mock_qdrant: MagicMock):
        """``check_qdrant_connection`` should return ``True`` when the
        Qdrant client responds successfully."""
        mock_qdrant.get_collections.return_value = MagicMock()
        assert check_qdrant_connection() is True

    def test_unhealthy_when_get_collections_fails(self, mock_qdrant: MagicMock):
        """It should return ``False`` when the Qdrant call raises an
        exception."""
        mock_qdrant.get_collections.side_effect = ConnectionError("Down")
        assert check_qdrant_connection() is False

# ======================================================================
#  init_collection
# ======================================================================


class TestInitCollection:
    def test_creates_collection_when_missing(self, mock_qdrant: MagicMock):
        """If the collection does not exist, ``init_collection`` should
        create it and set up payload indexes."""
        # Simulate an empty collection list
        mock_qdrant.get_collections.return_value = MagicMock(collections=[])

        init_collection()

        mock_qdrant.create_collection.assert_called_once()
        # Should create payload indexes for "type" and "path_segments"
        assert mock_qdrant.create_payload_index.call_count >= 2
        # One of them should be for "type"
        type_calls = [
            c for c in mock_qdrant.create_payload_index.call_args_list
            if c.kwargs.get("field_name") == "type"
        ]
        assert len(type_calls) == 1

    def test_skips_when_collection_exists(self, mock_qdrant: MagicMock):
        """If the collection already exists, no create calls should be made."""
        from core.config import settings

        # The default mock already has the collection, so this should be a no-op
        mock_col = MagicMock()
        mock_col.name = settings.qdrant.collection_name
        mock_qdrant.get_collections.return_value = MagicMock(
            collections=[mock_col]
        )

        init_collection()

        mock_qdrant.create_collection.assert_not_called()
        mock_qdrant.create_payload_index.assert_not_called()

    def test_raises_on_unexpected_error(self, mock_qdrant: MagicMock, caplog):
        """Unexpected errors during init should be logged and re-raised."""
        mock_qdrant.get_collections.side_effect = RuntimeError("Unexpected")

        with caplog.at_level(logging.ERROR):
            with pytest.raises(RuntimeError, match="Unexpected"):
                init_collection()

        assert "Failed to initialize" in caplog.text
