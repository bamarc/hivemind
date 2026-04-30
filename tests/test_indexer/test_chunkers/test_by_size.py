"""
Tests for :class:`indexer.chunkers.by_size.BySizeChunker`.
"""

from __future__ import annotations

import pytest

from indexer.chunkers.by_size import BySizeChunker


@pytest.fixture
def chunker() -> BySizeChunker:
    return BySizeChunker(chunk_size=20, overlap=5)


class TestBySizeChunker:
    def test_empty_content_returns_empty_list(self, chunker: BySizeChunker):
        assert chunker.chunk("", "/dev/null") == []

    def test_content_smaller_than_chunk_size(self, chunker: BySizeChunker):
        text = "hello world"  # 11 chars
        chunks = chunker.chunk(text, "/f.py")
        assert len(chunks) == 1
        assert chunks[0].content == text
        assert chunks[0].chunk_index == 0

    def test_content_larger_than_chunk_size(self, chunker: BySizeChunker):
        # 70 chars — with chunk_size=20, overlap=5 → ~4 chunks
        text = "a" * 70
        chunks = chunker.chunk(text, "/f.py")
        assert len(chunks) >= 3
        assert all(c.filepath == "/f.py" for c in chunks)
        assert chunks[0].chunk_index == 0
        assert chunks[1].chunk_index == 1

    def test_exact_chunk_size_with_overlap_creates_two_chunks(self, chunker: BySizeChunker):
        """When content is exactly ``chunk_size`` long, the overlap offset
        (``chunk_size - overlap``) still advances, creating a partial second
        chunk of ``overlap`` characters."""
        text = "a" * 20
        chunks = chunker.chunk(text, "/f.py")
        # overlap = 5, so start advances by 15, and the last 5 chars become a second chunk
        assert len(chunks) == 2
        assert len(chunks[0].content) == 20
        assert len(chunks[1].content) == 5

    def test_overlap_preserves_content(self, chunker: BySizeChunker):
        """Adjacent chunks should share ``overlap`` characters."""
        text = "a" * 30
        chunks = chunker.chunk(text, "/f.py")
        assert len(chunks) >= 2
        # overlap is 5 chars; chunk1 should start at char 15, so the last
        # 5 chars of chunk0 should appear at the start of chunk1
        overlap_region = chunks[0].content[-5:]
        assert chunks[1].content.startswith(overlap_region)

    def test_line_numbers_start_at_one(self, chunker: BySizeChunker):
        text = "line1\nline2\nline3"
        chunks = chunker.chunk(text, "/f.py")
        assert chunks[0].line_start == 1
        assert chunks[0].line_end == 3

    def test_different_filepath_in_metadata(self, chunker: BySizeChunker):
        chunks = chunker.chunk("some code", "/project/src/mod.py")
        assert all(c.filepath == "/project/src/mod.py" for c in chunks)
