"""
Tests for :class:`indexer.chunkers.by_lines.ByLinesChunker`.
"""

from __future__ import annotations

import pytest

from indexer.chunkers.by_lines import ByLinesChunker


@pytest.fixture
def chunker() -> ByLinesChunker:
    return ByLinesChunker(chunk_lines=5, overlap_lines=1)


class TestByLinesChunker:
    def test_empty_content_returns_empty_list(self, chunker: ByLinesChunker):
        assert chunker.chunk("", "/f.py") == []

    def test_fewer_lines_than_limit(self, chunker: ByLinesChunker):
        text = "\n".join(f"line {i}" for i in range(3))  # 3 lines
        chunks = chunker.chunk(text, "/f.py")
        assert len(chunks) == 1
        assert chunks[0].line_start == 1
        assert chunks[0].line_end == 3

    def test_more_lines_than_limit(self, chunker: ByLinesChunker):
        text = "\n".join(f"line {i}" for i in range(12))  # 12 lines
        chunks = chunker.chunk(text, "/f.py")
        assert len(chunks) >= 2
        assert all(c.filepath == "/f.py" for c in chunks)

    def test_line_numbers_one_indexed(self, chunker: ByLinesChunker):
        text = "\n".join(f"line {i}" for i in range(10))
        chunks = chunker.chunk(text, "/f.py")
        # First chunk: lines 1-5
        assert chunks[0].line_start == 1
        assert chunks[0].line_end == 5
        # Second chunk should start at (5 - overlap + 1) = 5
        if len(chunks) > 1:
            assert chunks[1].line_start == 5

    def test_overlap_between_chunks(self, chunker: ByLinesChunker):
        text = "\n".join(f"line {i}" for i in range(10))
        chunks = chunker.chunk(text, "/f.py")
        if len(chunks) >= 2:
            # With chunk_lines=5, overlap_lines=1:
            # chunk0 spans lines 0-4, chunk1 starts at line 4
            # So line 4 (0-indexed) = "line 4" should appear in both
            overlap_line = "line 4"
            assert overlap_line in chunks[0].content
            assert overlap_line in chunks[1].content

    def test_exact_line_count_with_overlap_creates_two_chunks(self, chunker: ByLinesChunker):
        """With ``chunk_lines=5, overlap_lines=1`` and exactly 5 lines of
        input, the overlap offset (``chunk_lines - overlap_lines = 4``)
        still advances, creating a partial second chunk with the overlap
        line."""
        text = "\n".join(f"line {i}" for i in range(5))
        chunks = chunker.chunk(text, "/f.py")
        # first chunk: lines 0-4, second chunk starts at line 4 (overlap)
        assert len(chunks) == 2
        assert chunks[0].line_start == 1
        assert chunks[0].line_end == 5
        assert chunks[1].line_start == 5
        assert chunks[1].line_end == 5

    def test_single_line_file(self, chunker: ByLinesChunker):
        chunks = chunker.chunk("just one line", "/f.py")
        assert len(chunks) == 1
        assert chunks[0].line_start == 1
        assert chunks[0].line_end == 1

    def test_chunk_index_increments(self, chunker: ByLinesChunker):
        text = "\n".join(f"line {i}" for i in range(20))
        chunks = chunker.chunk(text, "/f.py")
        for i, c in enumerate(chunks):
            assert c.chunk_index == i
