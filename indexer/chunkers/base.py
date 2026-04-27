from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Chunk:
    content: str
    filepath: str
    chunk_index: int
    line_start: int
    line_end: int
    metadata: Optional[dict] = None

class ChunkingStrategy(ABC):
    @abstractmethod
    def chunk(self, content: str, filepath: str) -> List[Chunk]:
        pass
