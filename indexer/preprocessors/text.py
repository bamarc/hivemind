from pathlib import Path
from typing import Set
from .base import BasePreprocessor

class TextPreprocessor(BasePreprocessor):
    """Default pre-processor for plain text files."""
    
    @property
    def supported_extensions(self) -> Set[str]:
        return {
            '.py', '.go', '.js', '.ts', '.md', '.txt', '.yaml', '.yml', '.toml',
            '.c', '.h', '.adoc', '.tsx', '.css', '.scss', '.tf', '.sh', '.conf',
            'Dockerfile'
        }

    def preprocess(self, filepath: Path) -> str:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
