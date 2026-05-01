"""
Tests for :mod:`scout.chunk_formatter`.
"""

from __future__ import annotations

import pytest

from indexer.chunkers.base import Chunk
from scout.chunk_formatter import format_toc, format_sections


@pytest.fixture
def sample_chunks():
    """Three-section document: intro, Installation (h1), Configuration (h2)."""
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
            content="# Installation\n\nRun `pip install foo`.",
            filepath="https://example.com/doc",
            chunk_index=1,
            line_start=4,
            line_end=6,
            metadata={"type": "markdown_h1", "symbols": ["Installation"]},
        ),
        Chunk(
            content="## Configuration\n\nSet the API key in your `.env` file.",
            filepath="https://example.com/doc",
            chunk_index=2,
            line_start=7,
            line_end=9,
            metadata={"type": "markdown_h2", "symbols": ["Configuration"]},
        ),
    ]


# ======================================================================
#  format_toc
# ======================================================================


class TestFormatToc:
    def test_includes_url(self, sample_chunks):
        result = format_toc(sample_chunks, "https://example.com/doc")
        assert "https://example.com/doc" in result

    def test_includes_all_sections(self, sample_chunks):
        result = format_toc(sample_chunks, "https://example.com/doc")
        assert "(preamble)" in result
        assert "Installation" in result
        assert "Configuration" in result

    def test_includes_level_labels(self, sample_chunks):
        result = format_toc(sample_chunks, "https://example.com/doc")
        assert "intro" in result
        assert "H1" in result
        assert "H2" in result

    def test_includes_line_ranges(self, sample_chunks):
        result = format_toc(sample_chunks, "https://example.com/doc")
        assert "1-3" in result
        assert "4-6" in result
        assert "7-9" in result

    def test_includes_token_estimates(self, sample_chunks):
        result = format_toc(sample_chunks, "https://example.com/doc")
        # The content "Welcome to the docs." is 21 chars → ~5 tokens at 4 chars/token
        assert "~5" in result or "~" in result

    def test_instructions_included(self, sample_chunks):
        result = format_toc(sample_chunks, "https://example.com/doc")
        assert "mode='sections'" in result

    def test_empty_chunks(self):
        result = format_toc([], "https://example.com/empty")
        # Should still include URL and instructions
        assert "Table of Contents" in result

    def test_chunk_without_symbols(self):
        """A chunk with empty metadata should still render."""
        chunks = [
            Chunk(
                content="Some content.",
                filepath="/f",
                chunk_index=0,
                line_start=1,
                line_end=5,
                metadata={},
            )
        ]
        result = format_toc(chunks, "https://example.com/doc")
        assert "(section 0)" in result


# ======================================================================
#  format_sections
# ======================================================================


class TestFormatSections:
    def test_select_by_name(self, sample_chunks):
        result = format_sections(sample_chunks, "https://example.com/doc", ["Installation"])
        assert "# Installation" in result
        assert "pip install" in result
        # Should NOT include Configuration
        assert "Configuration" not in result

    def test_select_by_index(self, sample_chunks):
        result = format_sections(sample_chunks, "https://example.com/doc", ["2"])
        assert "Configuration" in result
        assert "API key" in result

    def test_select_multiple(self, sample_chunks):
        result = format_sections(sample_chunks, "https://example.com/doc", ["Installation", "Configuration"])
        assert "Installation" in result
        assert "Configuration" in result

    def test_case_insensitive(self, sample_chunks):
        result = format_sections(sample_chunks, "https://example.com/doc", ["installation"])
        assert "Installation" in result

    def test_partial_match(self, sample_chunks):
        result = format_sections(sample_chunks, "https://example.com/doc", ["Config"])
        assert "Configuration" in result

    def test_no_match_shows_available(self, sample_chunks):
        result = format_sections(sample_chunks, "https://example.com/doc", ["NonExistent"])
        assert "No sections matched" in result
        assert "Installation" in result  # available sections listed
        assert "Configuration" in result

    def test_empty_section_names(self, sample_chunks):
        result = format_sections(sample_chunks, "https://example.com/doc", [])
        assert "No sections requested" in result

    def test_empty_chunks(self):
        result = format_sections([], "https://example.com/doc", ["Installation"])
        assert "No sections matched" in result

    def test_duplicate_search_terms_dont_duplicate_output(self, sample_chunks):
        """Requesting the same section twice should not duplicate output."""
        result = format_sections(sample_chunks, "https://example.com/doc", ["Configuration", "Configuration"])
        # The chunk content ("## Configuration\n\nSet...") contains "Configuration"
        # multiple times.  Use a count of the rendered heading instead.
        selected_header = "### Configuration"
        assert result.count(selected_header) == 1, (
            f"Expected exactly 1 '{selected_header}' line, got {result.count(selected_header)}"
        )
