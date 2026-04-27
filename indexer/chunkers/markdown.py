import re
from typing import List
from .base import ChunkingStrategy, Chunk

class MarkdownChunker(ChunkingStrategy):
    def __init__(self, chunk_lines: int = 100, overlap_lines: int = 10):
        self.chunk_lines = chunk_lines
        self.overlap_lines = overlap_lines
        # Matches # Header, ## Header, etc.
        self.header_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)

    def chunk(self, content: str, filepath: str) -> List[Chunk]:
        lines = content.splitlines()
        if not lines:
            return []

        # Find all header positions
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
            # Fallback to line-based chunking if no headers
            return self._create_line_chunks(lines, filepath, 0, 1, {})

        chunks = []
        current_idx = 0
        
        # Handle content before first header
        if headers[0]["line"] > 0:
            pre_header_lines = lines[:headers[0]["line"]]
            new_chunks = self._create_line_chunks(pre_header_lines, filepath, current_idx, 1, {"type": "markdown_intro"})
            chunks.extend(new_chunks)
            current_idx += len(new_chunks)

        # Process each header section
        for i in range(len(headers)):
            start_line_idx = headers[i]["line"]
            end_line_idx = headers[i+1]["line"] if i + 1 < len(headers) else len(lines)
            
            section_lines = lines[start_line_idx:end_line_idx]
            section_text = "\n".join(section_lines)
            
            metadata = {
                "type": f"markdown_h{headers[i]['level']}",
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

    def _create_line_chunks(self, lines: List[str], filepath: str, base_idx: int, start_line: int, metadata: dict) -> List[Chunk]:
        """Helper to split a list of lines into chunks."""
        if not lines:
            return []
            
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
