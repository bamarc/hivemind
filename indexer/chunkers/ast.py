from typing import List, Dict, Any, Optional
from .base import ChunkingStrategy, Chunk
from tree_sitter import Parser
from core.language_support import EXTENSION_TO_LANGUAGE, EXTENSION_TO_LANG_NAME, DEFINITION_TYPES
import os
import re


class ASTChunker(ChunkingStrategy):
    def __init__(self, chunk_lines: int = 50, overlap_lines: int = 5):
        self.chunk_lines = chunk_lines
        self.overlap_lines = overlap_lines

        self.parser = Parser()

        # Sanitization patterns
        self.base64_pattern = re.compile(r'([A-Za-z0-9+/]{100,}=*)')
        self.long_string_pattern = re.compile(r'("[^"]{500,}"|\'[^\']{500,}\')')

    def sanitize_content(self, text: str) -> str:
        """Strip 'noise' like base64 payloads or excessively long strings."""
        text = self.base64_pattern.sub("[BASE64_DATA_STRIPPED]", text)
        text = self.long_string_pattern.sub("[LONG_STRING_STRIPPED]", text)
        return text
    def _get_node_name(self, node) -> Optional[str]:
        """Extract a human-readable name for a definition node."""
        for child in node.children:
            if child.type in ("identifier", "type_identifier", "name"):
                return child.text.decode("utf8", errors="replace")
        return None

    def _create_chunks_from_text(self, text: str, filepath: str, start_line: int, base_idx: int, metadata: Dict[str, Any]) -> List[Chunk]:
        """Split a block of text into smaller chunks if it exceeds chunk_lines."""
        lines = text.splitlines()
        if len(lines) <= self.chunk_lines:
            return [Chunk(
                content=text,
                filepath=filepath,
                chunk_index=base_idx,
                line_start=start_line,
                line_end=start_line + len(lines) - 1,
                metadata=metadata
            )]

        # Sub-chunking logic
        chunks = []
        current_start = 0
        sub_idx = 0
        while current_start < len(lines):
            end = min(current_start + self.chunk_lines, len(lines))
            chunk_content = "\n".join(lines[current_start:end])
            chunks.append(Chunk(
                content=chunk_content,
                filepath=filepath,
                chunk_index=base_idx + sub_idx,
                line_start=start_line + current_start,
                line_end=start_line + end - 1,
                metadata=metadata
            ))
            current_start += (self.chunk_lines - self.overlap_lines)
            sub_idx += 1
            if current_start >= len(lines):
                break
        return chunks

    def chunk(self, content: str, filepath: str) -> List[Chunk]:
        ext = os.path.splitext(filepath)[1]
        lang = EXTENSION_TO_LANGUAGE.get(ext)

        if not lang:
            # Fallback to line-based chunking if no AST support
            return self._create_chunks_from_text(content, filepath, 1, 0, {})

        self.parser.language = lang
        tree = self.parser.parse(bytes(content, "utf8", errors="replace"))
        root = tree.root_node

        chunks = []
        current_idx = 0

        lang_name = EXTENSION_TO_LANG_NAME.get(ext, "unknown")
        target_types = DEFINITION_TYPES.get(lang_name, ())

        # Keep track of content that isn't inside a definition
        buffer_nodes = []

        def flush_buffer(nodes, start_idx):
            if not nodes:
                return [], start_idx

            start_line = nodes[0].start_point[0] + 1
            end_line = nodes[-1].end_point[0] + 1
            # Extract text for these nodes
            lines = content.splitlines()
            buffer_text = "\n".join(lines[start_line-1:end_line])

            new_chunks = self._create_chunks_from_text(
                buffer_text, filepath, start_line, start_idx, {"type": "general"}
            )
            return new_chunks, start_idx + len(new_chunks)

        for child in root.children:
            if child.type in target_types:
                # Flush buffer first
                if buffer_nodes:
                    buf_chunks, next_idx = flush_buffer(buffer_nodes, current_idx)
                    chunks.extend(buf_chunks)
                    current_idx = next_idx
                    buffer_nodes = []

                # Process definition node
                name = self._get_node_name(child)
                start_line = child.start_point[0] + 1
                node_text = child.text.decode("utf8", errors="replace")

                metadata = {
                    "type": child.type,
                    "symbols": [name] if name else []
                }

                # Sanitize before chunking
                sanitized_text = self.sanitize_content(node_text)

                node_chunks = self._create_chunks_from_text(
                    sanitized_text, filepath, start_line, current_idx, metadata
                )
                chunks.extend(node_chunks)
                current_idx += len(node_chunks)
            else:
                buffer_nodes.append(child)

        # Final flush
        if buffer_nodes:
            buf_chunks, _ = flush_buffer(buffer_nodes, current_idx)
            chunks.extend(buf_chunks)

        return chunks
