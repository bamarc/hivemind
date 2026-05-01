from typing import List
from .base import ChunkingStrategy, Chunk

class BySizeChunker(ChunkingStrategy):
    def __init__(self, chunk_size: int = 500, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap

    @staticmethod
    def _compute_line_offsets(content: str) -> List[int]:
        """Return a list where ``offsets[i]`` is the byte offset of
        the *i*-th line (0-indexed).

        The last entry is ``len(content)`` so that callers can iterate
        with ``offsets[i] : offsets[i+1]``.
        """
        offsets = [0]
        for pos, ch in enumerate(content):
            if ch == '\n':
                offsets.append(pos + 1)
        # Make sure we end at the content length
        if offsets[-1] != len(content):
            offsets.append(len(content))
        return offsets

    @staticmethod
    def _byte_offset_to_line_number(offsets: List[int], byte_pos: int) -> int:
        """Convert a byte offset *byte_pos* into a 1-indexed line number
        using the pre-computed *offsets* array (binary search)."""
        import bisect
        return bisect.bisect_right(offsets, byte_pos)

    def chunk(self, content: str, filepath: str) -> List[Chunk]:
        chunks = []
        if not content:
            return chunks

        # Pre-compute line offsets once – O(n) instead of O(n²)
        line_offsets = self._compute_line_offsets(content)
        total_len = len(content)

        start = 0
        idx = 0
        while start < total_len:
            end = min(start + self.chunk_size, total_len)
            chunk_content = content[start:end]

            # O(log n) line-number lookup using binary search
            line_start = self._byte_offset_to_line_number(line_offsets, start)
            line_end = line_start + chunk_content.count('\n')

            chunks.append(Chunk(
                content=chunk_content,
                filepath=filepath,
                chunk_index=idx,
                line_start=line_start,
                line_end=line_end,
            ))
            start += self.chunk_size - self.overlap
            idx += 1
            if start >= total_len:
                break

        return chunks
