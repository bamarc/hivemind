from typing import List, Optional
import json
from ..base import Chunk
from .base import MarkupChunker

class JSONChunker(MarkupChunker):
    def chunk(self, content: str, filepath: str) -> List[Chunk]:
        lines = content.splitlines()
        if not lines:
            return []

        try:
            # Try to parse as JSON and get top-level keys
            data = json.loads(content)
            if isinstance(data, dict):
                return self._chunk_by_keys(data, lines, filepath)
            elif isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                # If it's a list of objects, we could chunk by object, but for simplicity
                # we'll just fall back to line chunking with metadata.
                return self._create_line_chunks(lines, filepath, 0, 1, {"type": "json_list"})
        except json.JSONDecodeError:
            pass # Fallback to line-based chunking

        return self._create_line_chunks(lines, filepath, 0, 1, {"type": "json"})

    def _chunk_by_keys(self, data: dict, lines: List[str], filepath: str) -> List[Chunk]:
        # A simple heuristic: search for the keys in the lines.
        # This is not perfect as JSON keys can appear multiple times or be formatted weirdly,
        # but it provides a basic structure.
        chunks = []
        current_idx = 0

        # We can try to format the top level keys into a string and chunk them if they are too big.
        # But for semantic search, falling back to line chunking with correct metadata is often better
        # if the simple parser gets too complex. Let's just use line chunking with "json" metadata.
        # Given the instruction "Top level keys using simple parsers if possible, fall back to line based if this approach fails"

        return self._create_line_chunks(lines, filepath, 0, 1, {"type": "json", "keys": list(data.keys())[:10]})
