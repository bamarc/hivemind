from typing import List, Optional
import re
from ..base import Chunk
from .base import MarkupChunker

class XMLChunker(MarkupChunker):
    def __init__(self, chunk_lines: int = 100, overlap_lines: int = 10):
        super().__init__(chunk_lines, overlap_lines)
        self.tag_pattern = re.compile(r'^<([a-zA-Z0-9_:-]+)[^>]*>', re.MULTILINE)

    def chunk(self, content: str, filepath: str) -> List[Chunk]:
        lines = content.splitlines()
        if not lines:
            return []

        # Find top level elements (heuristically by tags at start of line)
        headers = []
        for i, line in enumerate(lines):
            match = self.tag_pattern.match(line)
            if match and not match.group(1).startswith("?xml") and not match.group(1).startswith("!--"):
                headers.append({
                    "line": i,
                    "tag": match.group(1)
                })

        if not headers:
            return self._create_line_chunks(lines, filepath, 0, 1, {"type": "xml"})

        chunks = []
        current_idx = 0

        if headers[0]["line"] > 0:
            pre_header_lines = lines[:headers[0]["line"]]
            new_chunks = self._create_line_chunks(pre_header_lines, filepath, current_idx, 1, {"type": "xml_intro"})
            chunks.extend(new_chunks)
            current_idx += len(new_chunks)

        for i in range(len(headers)):
            start_line_idx = headers[i]["line"]
            end_line_idx = headers[i+1]["line"] if i + 1 < len(headers) else len(lines)

            section_lines = lines[start_line_idx:end_line_idx]

            metadata = {
                "type": f"xml_{headers[i]['tag']}"
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
