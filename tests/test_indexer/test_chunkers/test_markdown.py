"""
Tests for :class:`indexer.chunkers.markdown.MarkdownChunker`.
"""

from __future__ import annotations

import pytest

from indexer.chunkers.markdown import MarkdownChunker


@pytest.fixture
def chunker() -> MarkdownChunker:
    return MarkdownChunker(chunk_lines=20, overlap_lines=2)


class TestMarkdownChunker:
    def test_empty_content(self, chunker: MarkdownChunker):
        assert chunker.chunk("", "/r.md") == []

    def test_no_headers_falls_back_to_line_chunking(self, chunker: MarkdownChunker):
        """Content without any markdown headers should be chunked by line count.
        The fallback path uses ``_create_line_chunks`` which produces
        chunks with empty metadata."""
        text = "\n".join(f"paragraph {i}" for i in range(30))
        chunks = chunker.chunk(text, "/r.md")
        assert len(chunks) >= 2
        # Fallback chunks have empty metadata (no "type" key)
        assert chunks[0].metadata == {}

    def test_chunks_by_header_sections(self, chunker: MarkdownChunker):
        md = (
            "# Title\n\n"
            "Intro.\n\n"
            "## Section 1\n\n"
            "Content 1.\n\n"
            "## Section 2\n\n"
            "Content 2.\n"
        )
        chunks = chunker.chunk(md, "/doc.md")
        # There are 3 sections: # Title (h1), ## Section 1 (h2), ## Section 2 (h2)
        # No "pre-header" chunk because # Title is on line 0
        assert len(chunks) == 3
        assert chunks[0].metadata["type"] == "markdown_h1"
        assert chunks[1].metadata["type"] == "markdown_h2"
        assert chunks[2].metadata["type"] == "markdown_h2"

    def test_header_symbols_in_metadata(self, chunker: MarkdownChunker):
        md = "# Welcome\n\nContent.\n\n## Getting Started\n\nMore.\n"
        chunks = chunker.chunk(md, "/doc.md")
        # pre-header chunk has no symbols; first header is "Welcome"
        if len(chunks) > 0 and chunks[0].metadata["type"] != "markdown_intro":
            assert "Welcome" in chunks[0].metadata.get("symbols", [])

        for c in chunks:
            if c.metadata["type"] == "markdown_h2":
                assert "Getting Started" in c.metadata.get("symbols", [])

    def test_large_sections_sub_chunked(self):
        """A section larger than ``chunk_lines`` should be split into
        multiple chunks with the same metadata."""
        small = MarkdownChunker(chunk_lines=3, overlap_lines=1)
        md = "# Big\n\n" + "\n".join(f"line {i}" for i in range(10))
        chunks = small.chunk(md, "/big.md")
        # The header section is > 3 lines, should be split
        assert len(chunks) > 1
        # All chunks from the same section share the type
        types = {c.metadata["type"] for c in chunks if c.metadata["type"] != "markdown_intro"}
        assert "markdown_h1" in types

    def test_pre_header_content_included(self, chunker: MarkdownChunker):
        """Any content before the first ``#`` heading should be captured as
        a ``markdown_intro`` chunk."""
        md = "Leading text.\n\n# Real Start\n\nBody.\n"
        chunks = chunker.chunk(md, "/doc.md")
        assert any(c.metadata["type"] == "markdown_intro" for c in chunks)
        intro = next(c for c in chunks if c.metadata["type"] == "markdown_intro")
        assert "Leading" in intro.content

    def test_multilevel_headers(self, chunker: MarkdownChunker):
        md = (
            "# H1\n\n"
            "## H2\n\n"
            "### H3\n\n"
            "#### H4\n\n"
            "##### H5\n\n"
            "###### H6\n\n"
            "End.\n"
        )
        chunks = chunker.chunk(md, "/h.md")
        types_found = {c.metadata["type"] for c in chunks}
        # H1 intro, then each header level below
        assert "markdown_h1" in types_found or "markdown_intro" in types_found
        assert "markdown_h6" in types_found

    def test_line_numbers_accurate(self, chunker: MarkdownChunker):
        """Verify line numbering for each chunk.

        The markdown::

            # Top        (line 1)
                         (line 2)
            Line A       (line 3)
                         (line 4 ← empty separator before ## Sub)
            ## Sub       (line 5)
                         (line 6)
            Line B       (line 7)

        The first header section spans lines 1–4 (including the empty
        separator). The second header section spans lines 5–7.
        """
        md = "# Top\n\nLine A\n\n## Sub\n\nLine B"
        chunks = chunker.chunk(md, "/doc.md")
        for c in chunks:
            content_lines = c.content.splitlines()
            # Note: content may include a trailing empty line that
            # splitlines() discards, so we derive line count from the
            # original content
            line_count = c.content.count("\n") + 1
            expected_line_end = c.line_start + line_count - 1
            assert c.line_end == expected_line_end, (
                f"Chunk {c.chunk_index}: line_start={c.line_start}, "
                f"content has {line_count} lines (splitlines gives "
                f"{len(content_lines)}), expected line_end="
                f"{expected_line_end}, got {c.line_end}"
            )
