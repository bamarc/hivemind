from typing import List, Optional
from .css_chunker import CSSChunker
from ..base import Chunk
import re

class SCSSChunker(CSSChunker):
    def __init__(self, chunk_lines: int = 100, overlap_lines: int = 10):
        super().__init__(chunk_lines, overlap_lines)

    def chunk(self, content: str, filepath: str) -> List[Chunk]:
        chunks = super().chunk(content, filepath)
        for c in chunks:
            if c.metadata and c.metadata.get("type") == "css":
                c.metadata["type"] = "scss"
            elif c.metadata and c.metadata.get("type") == "css_intro":
                c.metadata["type"] = "scss_intro"
            elif c.metadata and c.metadata.get("type") == "css_rule":
                c.metadata["type"] = "scss_rule"
        return chunks
