from typing import List, Optional
import re
from ..base import Chunk
from .base import MarkupChunker

class AsciidocChunker(MarkupChunker):
    def __init__(self, chunk_lines: int = 100, overlap_lines: int = 10):
        super().__init__(chunk_lines, overlap_lines)
        # Matches == Header, === Header, etc.
        self.header_pattern = re.compile(r'^(=+)\s+(.+)$', re.MULTILINE)

    def chunk(self, content: str, filepath: str) -> List[Chunk]:
        lines = content.splitlines()
        if not lines:
            return []

        headers = []
        for i, line in enumerate(lines):
            match = self.header_pattern.match(line)
            if match:
                headers.append({
                    "line": i,
                    "level": len(match.group(1)),
                    "text": match.group(2)
                })

        if not headers:
            return self._create_line_chunks(lines, filepath, 0, 1, {"type": "asciidoc"})

        chunks = []
        current_idx = 0

        if headers[0]["line"] > 0:
            pre_header_lines = lines[:headers[0]["line"]]
            new_chunks = self._create_line_chunks(pre_header_lines, filepath, current_idx, 1, {"type": "asciidoc_intro"})
            chunks.extend(new_chunks)
            current_idx += len(new_chunks)

        for i in range(len(headers)):
            start_line_idx = headers[i]["line"]
            end_line_idx = headers[i+1]["line"] if i + 1 < len(headers) else len(lines)

            section_lines = lines[start_line_idx:end_line_idx]

            metadata = {
                "type": f"asciidoc_h{headers[i]['level']}",
                "symbols": [headers[i]["text"]]
            }

            new_chunks = self._create_line_chunks(
                section_lines,
                filepath,
                current_idx,
                start_line_idx + 1,
                metadata
            )
            chunks.extend(new_chunks)
            current_idx += len(new_chunks)

        return chunks
