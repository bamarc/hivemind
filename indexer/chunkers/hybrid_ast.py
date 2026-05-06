"""
Hybrid AST chunker: line-based window + AST symbol enrichment.

Unlike the original :class:`ASTChunker` which defines chunk boundaries at
function/class definition edges (producing tiny leftover fragments), this
chunker first creates uniform line-based windows and then enriches each
window with symbol names extracted from the AST.  The result is consistent
chunk sizes with rich semantic metadata that improves both dense and sparse
(hyrbid) search relevance.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

from tree_sitter import Parser, Node

from .base import ChunkingStrategy, Chunk
from core.language_support import (
    EXTENSION_TO_LANGUAGE,
    EXTENSION_TO_LANG_NAME,
    DEFINITION_TYPES,
)


@dataclass
class _Symbol:
    """A named definition extracted from the AST."""

    name: str
    kind: str  # "function", "class", etc.
    start_line: int
    end_line: int


class ASTEnrichedByLinesChunker(ChunkingStrategy):
    """Line-based chunker that enriches each chunk with AST symbol metadata.

    Parameters
    ----------
    chunk_lines:
        Number of lines per chunk window (default 50).
    overlap_lines:
        Number of overlapping lines between adjacent chunks (default 5).
    """

    def __init__(self, chunk_lines: int = 50, overlap_lines: int = 5):
        self.chunk_lines = chunk_lines
        self.overlap_lines = overlap_lines
        self._parser: Optional[Parser] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chunk(self, content: str, filepath: str) -> List[Chunk]:
        """Split *content* into line-based windows enriched with AST symbols.

        For files whose language is not supported by tree-sitter, falls back
        to plain line-based chunking.
        """
        ext = os.path.splitext(filepath)[1]
        lang = EXTENSION_TO_LANGUAGE.get(ext)
        lang_name = EXTENSION_TO_LANG_NAME.get(ext)

        symbols: List[_Symbol] = []
        if lang is not None and lang_name is not None:
            symbols = self._extract_symbols(content, lang, lang_name)

        return self._build_chunks(content, filepath, symbols)

    # ------------------------------------------------------------------
    # AST symbol extraction
    # ------------------------------------------------------------------

    def _get_parser(self) -> Parser:
        if self._parser is None:
            self._parser = Parser()
        return self._parser

    def _extract_symbols(
        self,
        content: str,
        lang,
        lang_name: str,
    ) -> List[_Symbol]:
        """Parse *content* and return every top-level definition symbol."""
        parser = self._get_parser()
        parser.language = lang
        tree = parser.parse(bytes(content, "utf8", errors="replace"))

        target_types = DEFINITION_TYPES.get(lang_name, ())
        if not target_types:
            return []

        symbols: List[_Symbol] = []
        self._collect_symbols(tree.root_node, target_types, symbols)
        return symbols

    def _collect_symbols(
        self,
        node: Node,
        target_types: Tuple[str, ...],
        symbols: List[_Symbol],
    ) -> None:
        """Recursively walk *node* and collect definition symbols."""
        for child in node.children:
            if child.type in target_types:
                name = self._get_node_name(child)
                if name:
                    symbols.append(
                        _Symbol(
                            name=name,
                            kind=child.type,
                            start_line=child.start_point[0] + 1,
                            end_line=child.end_point[0] + 1,
                        )
                    )
            # Recurse into children (catches nested class methods etc.)
            self._collect_symbols(child, target_types, symbols)

    # ------------------------------------------------------------------
    # Line-based chunking + enrichment
    # ------------------------------------------------------------------

    def _build_chunks(
        self,
        content: str,
        filepath: str,
        symbols: List[_Symbol],
    ) -> List[Chunk]:
        """Create line-based chunks and enrich with relevant symbols."""
        lines = content.splitlines()
        if not lines:
            return []

        chunks: List[Chunk] = []
        start = 0
        idx = 0
        step = self.chunk_lines - self.overlap_lines

        while start < len(lines):
            end = min(start + self.chunk_lines, len(lines))
            chunk_start_line = start + 1  # 1-indexed
            chunk_end_line = end

            chunk_lines_slice = lines[start:end]
            chunk_content = "\n".join(chunk_lines_slice)

            # Find symbols whose definition *starts* inside this chunk
            chunk_symbols = [
                s
                for s in symbols
                if chunk_start_line <= s.start_line <= chunk_end_line
            ]

            # Enrich content with symbol names so the dense embedding
            # captures them and sparse/hybrid search can match them.
            # We use a language-agnostic marker (doc-comment style) that
            # blends into most source languages without disturbing the AST.
            if chunk_symbols:
                symbol_hint = "/* Symbols: " + ", ".join(
                    f"{s.kind.split('_')[0]}:{s.name}" for s in chunk_symbols
                ) + " */"
                enriched_content = chunk_content + "\n\n" + symbol_hint
            else:
                enriched_content = chunk_content

            chunks.append(
                Chunk(
                    content=enriched_content,
                    filepath=filepath,
                    chunk_index=idx,
                    line_start=chunk_start_line,
                    line_end=chunk_end_line,
                    metadata={
                        "type": "code",
                        "symbols": [s.name for s in chunk_symbols],
                    },
                )
            )

            start += step
            idx += 1
            if start >= len(lines):
                break

        return chunks

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_node_name(node: Node) -> Optional[str]:
        """Extract the declared name from a definition node."""
        for child in node.children:
            if child.type in ("identifier", "type_identifier", "name"):
                return child.text.decode("utf8")
        return None
