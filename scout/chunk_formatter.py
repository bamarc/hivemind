"""Markdown formatting utilities for chunked scout content.

Provides two formatting functions used by the Map-Reduce pattern in
``scout_urls``:

* :func:`format_toc` — generates a Table of Contents from chunk metadata.
* :func:`format_sections` — returns verbatim content for selected sections.
"""

from __future__ import annotations

from typing import List

from indexer.chunkers.base import Chunk

# Rough estimate: 1 token ≈ 4 characters (conservative for markdown).
_CHARS_PER_TOKEN = 4


def format_toc(chunks: List[Chunk], url: str) -> str:
    """Build a Table of Contents markdown string from a list of chunks.

    The TOC shows each section's header text, heading level, line range,
    and approximate token count so the agent can decide which sections
    are worth reading.

    Args:
        chunks: The chunked content (output of :class:`MarkdownChunker`).
        url: The source URL (used as the TOC title).

    Returns:
        A formatted markdown string.
    """
    lines = [
        f"## Table of Contents: {url}\n",
        "| # | Section | Level | Lines | ~Tokens |",
        "|---|---------|-------|-------|---------|",
    ]

    for i, chunk in enumerate(chunks):
        section_name = _section_label(chunk)
        level = _level_label(chunk)
        line_range = f"{chunk.line_start}-{chunk.line_end}"
        est_tokens = len(chunk.content) // _CHARS_PER_TOKEN

        lines.append(
            f"| {i} | {section_name} | {level} | {line_range} | {est_tokens} |"
        )

    lines.append("")
    lines.append(
        "---\n"
        "To read specific sections, call ``scout_urls`` with ``mode='sections'``\n"
        "and pass the section names or numbers as ``sections=[...]``.\n"
    )

    return "\n".join(lines)


def format_sections(
    chunks: List[Chunk],
    url: str,
    section_names: List[str],
) -> str:
    """Return content only for chunks whose section matches *section_names*.

    Matching is **case-insensitive substring** match against the section
    name (header text) and the numeric index (e.g. ``"2"`` matches the
    third chunk).  This gives the agent flexibility when referring back
    to the TOC.

    Args:
        chunks: The chunked content (output of :class:`MarkdownChunker`).
        url: The source URL.
        section_names: List of section names or indices to include.

    Returns:
        Formatted markdown containing only the requested sections.
    """
    if not section_names:
        return "No sections requested."

    # Normalise search terms: lower-case, stripped.
    terms = [s.strip().lower() for s in section_names]

    selected: List[Chunk] = []
    seen_indices: set[int] = set()

    for i, chunk in enumerate(chunks):
        idx_str = str(i)
        label = _section_label(chunk).lower()

        # Match if any term matches the index (exact) or the label (substring).
        for term in terms:
            if term == idx_str or term in label:
                if i not in seen_indices:
                    selected.append(chunk)
                    seen_indices.add(i)
                break

    if not selected:
        return (
            f"No sections matched the given names: {section_names}\n\n"
            f"Available sections were:\n"
            + "\n".join(f"  [{i}] {_section_label(c)}" for i, c in enumerate(chunks))
        )

    result_lines = [
        f"## Selected Sections from: {url}\n"
        f"({len(selected)} of {len(chunks)} chunks returned)\n"
    ]

    for chunk in selected:
        label = _section_label(chunk)
        level = _level_label(chunk)
        est_tokens = len(chunk.content) // _CHARS_PER_TOKEN

        result_lines.append(f"---")
        result_lines.append(f"### {label}  ({level}, ~{est_tokens} tokens)")
        result_lines.append("")
        result_lines.append(chunk.content)
        result_lines.append("")

    return "\n".join(result_lines)


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _section_label(chunk: Chunk) -> str:
    """Derive a human-readable section label from chunk metadata."""
    meta = chunk.metadata or {}
    symbols = meta.get("symbols", [])
    if symbols:
        # Some headers might have formatting stripped; use first symbol.
        return symbols[0]
    chunk_type = meta.get("type", "")
    if chunk_type == "markdown_intro":
        return "(preamble)"
    return f"(section {chunk.chunk_index})"


def _level_label(chunk: Chunk) -> str:
    """Derive a human-readable level label (e.g. ``'H2'``, ``'intro'``)."""
    meta = chunk.metadata or {}
    chunk_type = meta.get("type", "")
    if chunk_type == "markdown_intro":
        return "intro"
    if chunk_type.startswith("markdown_h"):
        # "markdown_h3" → "H3"
        return chunk_type[-2:].upper()
    return chunk_type
