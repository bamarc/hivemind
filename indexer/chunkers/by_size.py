from typing import List
from .base import ChunkingStrategy, Chunk

class BySizeChunker(ChunkingStrategy):
    def __init__(self, chunk_size: int = 500, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, content: str, filepath: str) -> List[Chunk]:
        chunks = []
        if not content:
            return chunks

        start = 0
        idx = 0
        while start < len(content):
            end = min(start + self.chunk_size, len(content))
            chunk_content = content[start:end]
            
            # Calculate line numbers
            line_start = content.count('\n', 0, start) + 1
            line_end = line_start + chunk_content.count('\n')
            
            chunks.append(Chunk(
                content=chunk_content,
                filepath=filepath,
                chunk_index=idx,
                line_start=line_start,
                line_end=line_end
            ))
            start += (self.chunk_size - self.overlap)
            idx += 1
            if start >= len(content):
                break
        return chunks
