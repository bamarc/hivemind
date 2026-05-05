"""
Tests for :mod:`core.clients`.

These tests validate the embedding API wrapper functions,
Qdrant collection initialisation, and connection health check.
All external clients (Qdrant, OpenAI) are mocked by the global
``conftest.py`` — no real infrastructure is needed.
"""

from __future__ import annotations

import logging
from unittest.mock import ANY, MagicMock

import pytest

from core.clients import (
    check_qdrant_connection,
    detect_embedding_dim,
    get_embedding,
    get_embeddings_batch,
    init_collection,
    text_to_sparse_vector,
)
from core import config
from tests.conftest import MOCK_EMBEDDING_DIM

# ======================================================================
#  text_to_sparse_vector
# ======================================================================


class TestTextToSparseVector:
    def test_returns_sparse_vector(self):
        """A text string should produce a valid SparseVector with indices and values."""
        result = text_to_sparse_vector("hello world")
        assert hasattr(result, "indices")
        assert hasattr(result, "values")
        assert len(result.indices) > 0
        assert len(result.indices) == len(result.values)

    def test_identical_text_produces_same_vector(self):
        """The same text should produce identical sparse vectors (deterministic)."""
        a = text_to_sparse_vector("def foo bar")
        b = text_to_sparse_vector("def foo bar")
        assert a.indices == b.indices
        assert a.values == b.values

    def test_different_text_produces_different_vectors(self):
        """Different text should produce different sparse vectors."""
        a = text_to_sparse_vector("hello world")
        b = text_to_sparse_vector("goodbye world")
        assert a.indices != b.indices or a.values != b.values

    def test_empty_string_returns_empty_vectors(self):
        """An empty string should produce empty indices and values."""
        result = text_to_sparse_vector("")
        assert result.indices == []
        assert result.values == []

    def test_values_are_normalized(self):
        """Values should be L2-normalized (squared sum ≈ 1.0)."""
        result = text_to_sparse_vector("hello hello world")
        squared_sum = sum(v * v for v in result.values)
        assert abs(squared_sum - 1.0) < 1e-6

    def test_vocab_size_config_respected(self):
        """The vocab_size from settings should determine the hash space."""
        from core.config import settings

        original = settings.sparse.vocab_size
        settings.sparse.vocab_size = 100  # small hash space for testing
        try:
            result = text_to_sparse_vector("hello world")
            assert all(idx < 100 for idx in result.indices)
        finally:
            settings.sparse.vocab_size = original


# ======================================================================
#  get_embeddings_batch
# ======================================================================


class TestGetEmbeddingsBatch:
    def test_single_text_returns_single_vector(self):
        """A single text should return a list with one embedding vector."""
        results = get_embeddings_batch(["hello world"])
        assert len(results) == 1
        assert len(results[0]) == MOCK_EMBEDDING_DIM

    def test_multiple_texts_return_matching_count(self):
        """N texts should produce N embedding vectors."""
        texts = ["first", "second", "third"]
        results = get_embeddings_batch(texts)
        assert len(results) == len(texts)
        for vec in results:
            assert len(vec) == MOCK_EMBEDDING_DIM

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

        batch = ["text"] * (config.settings.model.batch_size * 2 + 1)
        results = get_embeddings_batch(batch)

        assert call_count >= 2, (
            f"Expected at least 2 embedder calls for "
            f"{len(batch)} items (batch_size={config.settings.model.batch_size}), "
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
        assert len(result) == MOCK_EMBEDDING_DIM
        # All values should be floats
        assert all(isinstance(v, float) for v in result)

    def test_empty_text_returns_vector(self):
        """Even an empty string should get embedded (the mock doesn't care)."""
        result = get_embedding("")
        assert isinstance(result, list)
        assert len(result) == MOCK_EMBEDDING_DIM

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
        from core import config

        # The default mock already has the collection, so this should be a no-op
        mock_col = MagicMock()
        mock_col.name = config.settings.qdrant.collection_name
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

    def test_creates_collection_with_sparse_config(self, mock_qdrant: MagicMock):
        """When creating a new collection, sparse_vectors_config should be included."""
        mock_qdrant.get_collections.return_value = MagicMock(collections=[])

        init_collection()

        call_kwargs = mock_qdrant.create_collection.call_args.kwargs
        assert "sparse_vectors_config" in call_kwargs
        assert "code-sparse" in call_kwargs["sparse_vectors_config"]

    def test_logs_warning_when_existing_collection_lacks_sparse(
        self, mock_qdrant: MagicMock, caplog
    ):
        """Existing collections without 'code-sparse' should trigger a warning."""
        from core import config
        from tests.conftest import _collection_mock

        # Mock existing collection WITHOUT sparse_vectors.
        # Use _collection_mock so that col.name returns the collection name.
        col = _collection_mock(config.settings.qdrant.collection_name)
        mock_qdrant.get_collections.return_value = MagicMock(
            collections=[col]
        )
        mock_qdrant.get_collection.return_value = MagicMock(
            config=MagicMock(
                params=MagicMock(
                    vectors=MagicMock(size=MOCK_EMBEDDING_DIM),
                ),
            ),
        )

        with caplog.at_level(logging.WARNING):
            init_collection()

        assert "no 'code-sparse' sparse vector" in caplog.text


# ======================================================================
#  detect_embedding_dim
# ======================================================================


class TestDetectEmbeddingDim:
    """``detect_embedding_dim()`` sends a single probe request to determine
    the vector dimensionality of the configured embedding model."""

    def test_returns_dimension_from_probe(self, mock_embedder: MagicMock):
        """Should return the length of the probe embedding vector."""
        dim = detect_embedding_dim()
        assert dim == MOCK_EMBEDDING_DIM
        mock_embedder.embeddings.create.assert_called_once_with(
            input=["probe"], model=ANY,
        )

    def test_results_are_cached(self, mock_embedder: MagicMock):
        """Calling ``detect_embedding_dim()`` twice should only invoke the
        API once (``lru_cache``)."""
        detect_embedding_dim()
        detect_embedding_dim()
        mock_embedder.embeddings.create.assert_called_once()

    def test_raises_on_empty_response(self, mock_embedder: MagicMock):
        """When the API returns no data, a ``RuntimeError`` should be raised."""
        from unittest.mock import MagicMock as MM

        empty_response = MM(name="EmptyResponse")
        empty_response.data = []
        mock_embedder.embeddings.create = MM(
            return_value=empty_response,
            name="EmptyEmbeddingsCreate",
        )
        with pytest.raises(RuntimeError, match="returned no data"):
            detect_embedding_dim()
