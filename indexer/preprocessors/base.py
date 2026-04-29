from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Set

class BasePreprocessor(ABC):
    """Base class for all file pre-processors."""
    
    @property
    @abstractmethod
    def supported_extensions(self) -> Set[str]:
        """Return a set of supported file extensions (e.g., {'.pdf', '.docx'})."""
        pass

    @abstractmethod
    def preprocess(self, filepath: Path) -> str:
        """
        Process a file and return its text representation.
        
        Args:
            filepath: Path to the file to process.
            
        Returns:
            A string containing the extracted text/markdown content.
        """
        pass
