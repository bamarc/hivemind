from typing import List
from .base import ChunkingStrategy, Chunk

class ByLinesChunker(ChunkingStrategy):
    def __init__(self, chunk_lines: int = 50, overlap_lines: int = 5):
        self.chunk_lines = chunk_lines
        self.overlap_lines = overlap_lines

    def chunk(self, content: str, filepath: str) -> List[Chunk]:
        chunks = []
        lines = content.splitlines()
        if not lines:
            return chunks

        start = 0
        idx = 0
        while start < len(lines):
            end = min(start + self.chunk_lines, len(lines))
            chunk_content = "\n".join(lines[start:end])
            chunks.append(Chunk(
                content=chunk_content,
                filepath=filepath,
                chunk_index=idx,
                line_start=start + 1,  # 1-indexed
                line_end=end
            ))
            start += (self.chunk_lines - self.overlap_lines)
            idx += 1
            if start >= len(lines):
                break
        return chunks
