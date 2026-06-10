from typing import List
from ..base import ChunkingStrategy, Chunk

class MarkupChunker(ChunkingStrategy):
    def __init__(self, chunk_lines: int = 100, overlap_lines: int = 10):
        self.chunk_lines = chunk_lines
        self.overlap_lines = overlap_lines

    def _create_line_chunks(self, lines: List[str], filepath: str, base_idx: int, start_line: int, metadata: dict) -> List[Chunk]:
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
