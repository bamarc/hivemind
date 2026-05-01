"""
Tests for :class:`scout.chunk_cache.ChunkCache`.
"""

from __future__ import annotations

import time
import pytest

from indexer.chunkers.base import Chunk
from scout.chunk_cache import ChunkCache


@pytest.fixture
def cache():
    """Return a fresh ChunkCache with a short TTL (0.1s) for fast testing."""
    c = ChunkCache(ttl=0.1)
    yield c
    c.clear()


@pytest.fixture
def sample_chunks():
    """Sample chunked document with two header sections."""
    return [
        Chunk(
            content="Welcome to the docs.",
            filepath="https://example.com/doc",
            chunk_index=0,
            line_start=1,
            line_end=3,
            metadata={"type": "markdown_intro"},
        ),
        Chunk(
            content="# Installation\nRun `pip install foo`.",
            filepath="https://example.com/doc",
            chunk_index=1,
            line_start=4,
            line_end=6,
            metadata={"type": "markdown_h1", "symbols": ["Installation"]},
        ),
        Chunk(
            content="## Configuration\nSet the API key.",
            filepath="https://example.com/doc",
            chunk_index=2,
            line_start=7,
            line_end=9,
            metadata={"type": "markdown_h2", "symbols": ["Configuration"]},
        ),
    ]


# ======================================================================
#  store / get
# ======================================================================


class TestStoreAndGet:
    def test_store_and_retrieve(self, cache, sample_chunks):
        cache.store("https://example.com/doc", sample_chunks)
        retrieved = cache.get("https://example.com/doc")
        assert retrieved is not None
        assert len(retrieved) == 3
        assert retrieved[0].content == "Welcome to the docs."

    def test_store_overwrite(self, cache, sample_chunks):
        cache.store("https://example.com/doc", sample_chunks[:1])
        cache.store("https://example.com/doc", sample_chunks)
        retrieved = cache.get("https://example.com/doc")
        assert retrieved is not None
        assert len(retrieved) == 3  # latest write wins

    def test_missing_url(self, cache):
        assert cache.get("https://example.com/missing") is None

    def test_different_urls_independent(self, cache, sample_chunks):
        cache.store("https://example.com/a", sample_chunks[:1])
        cache.store("https://example.com/b", sample_chunks[1:])
        assert len(cache.get("https://example.com/a")) == 1
        assert len(cache.get("https://example.com/b")) == 2


# ======================================================================
#  TTL eviction
# ======================================================================


class TestEviction:
    def test_expired_entry_not_returned(self, cache, sample_chunks):
        cache.store("https://example.com/doc", sample_chunks)
        # Wait longer than TTL
        time.sleep(0.15)
        assert cache.get("https://example.com/doc") is None

    def test_expired_entry_removed_from_store(self, cache, sample_chunks):
        cache.store("https://example.com/doc", sample_chunks)
        time.sleep(0.15)
        cache.evict_expired()
        assert len(cache) == 0

    def test_non_expired_entry_survives(self, cache, sample_chunks):
        cache.store("https://example.com/doc", sample_chunks)
        # get() calls evict_expired internally, so this should still work
        time.sleep(0.05)
        assert cache.get("https://example.com/doc") is not None


# ======================================================================
#  get_toc / get_sections
# ======================================================================


class TestFormatting:
    def test_get_toc_returns_string(self, cache, sample_chunks):
        cache.store("https://example.com/doc", sample_chunks)
        toc = cache.get_toc("https://example.com/doc")
        assert toc is not None
        assert "Table of Contents" in toc
        assert "Installation" in toc
        assert "Configuration" in toc

    def test_get_toc_missing_url(self, cache):
        assert cache.get_toc("https://example.com/missing") is None

    def test_get_sections_by_name(self, cache, sample_chunks):
        cache.store("https://example.com/doc", sample_chunks)
        result = cache.get_sections("https://example.com/doc", ["Configuration"])
        assert result is not None
        assert "## Configuration" in result or "Configuration" in result
        # Should NOT include Installation preamble
        assert "Welcome to the docs" not in (result or "")

    def test_get_sections_by_index(self, cache, sample_chunks):
        cache.store("https://example.com/doc", sample_chunks)
        # Index "1" corresponds to the Installation chunk
        result = cache.get_sections("https://example.com/doc", ["1"])
        assert result is not None
        assert "Installation" in result

    def test_get_sections_case_insensitive(self, cache, sample_chunks):
        cache.store("https://example.com/doc", sample_chunks)
        result = cache.get_sections("https://example.com/doc", ["configuration"])
        assert result is not None
        assert "Configuration" in result

    def test_get_sections_no_match_returns_available(self, cache, sample_chunks):
        cache.store("https://example.com/doc", sample_chunks)
        result = cache.get_sections("https://example.com/doc", ["NonExistent"])
        assert result is not None
        assert "No sections matched" in result

    def test_get_sections_missing_url(self, cache):
        assert cache.get_sections("https://example.com/missing", ["test"]) is None

    def test_get_sections_empty_list(self, cache, sample_chunks):
        cache.store("https://example.com/doc", sample_chunks)
        result = cache.get_sections("https://example.com/doc", [])
        assert result is not None
        assert "No sections requested" in result


# ======================================================================
#  clear
# ======================================================================


class TestClear:
    def test_clear_removes_all(self, cache, sample_chunks):
        cache.store("https://example.com/a", sample_chunks)
        cache.store("https://example.com/b", sample_chunks)
        cache.clear()
        assert len(cache) == 0
        assert cache.get("https://example.com/a") is None

    def test_clear_then_store(self, cache, sample_chunks):
        cache.store("https://example.com/a", sample_chunks)
        cache.clear()
        cache.store("https://example.com/a", sample_chunks)
        assert cache.get("https://example.com/a") is not None


# ======================================================================
#  Thread safety (lightweight smoke test)
# ======================================================================


class TestThreadSafety:
    def test_concurrent_store_and_get(self, cache, sample_chunks):
        import threading

        errors = []

        def writer():
            try:
                for i in range(20):
                    cache.store(f"https://example.com/{i}", sample_chunks)
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for i in range(20):
                    cache.get(f"https://example.com/{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer) for _ in range(3)]
        threads += [threading.Thread(target=reader) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread safety errors: {errors}"
