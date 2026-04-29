import logging
import pkgutil
import importlib
import inspect
from pathlib import Path
from typing import Dict, Type, Optional, Set
from .base import BasePreprocessor

logger = logging.getLogger(__name__)

class PreprocessorManager:
    """Manages dynamic discovery and dispatching of file pre-processors."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PreprocessorManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        self.preprocessors: Dict[str, BasePreprocessor] = {}
        self.supported_extensions: Set[str] = set()
        self._discover_preprocessors()
        self._initialized = True

    def _discover_preprocessors(self):
        """Dynamically discover pre-processor classes in the current package."""
        package_path = str(Path(__file__).parent)
        
        for loader, module_name, is_pkg in pkgutil.iter_modules([package_path]):
            if module_name == 'base' or module_name == 'manager':
                continue
                
            try:
                module = importlib.import_module(f".{module_name}", package='indexer.preprocessors')
                
                for name, obj in inspect.getmembers(module):
                    if inspect.isclass(obj) and issubclass(obj, BasePreprocessor) and obj is not BasePreprocessor:
                        instance = obj()
                        for ext in instance.supported_extensions:
                            if ext in self.preprocessors:
                                logger.warning(f"Extension {ext} already registered by {self.preprocessors[ext].__class__.__name__}. Overwriting with {name}.")
                            
                            self.preprocessors[ext] = instance
                            self.supported_extensions.add(ext)
                            logger.debug(f"Registered {name} for extension {ext}")
                            
            except Exception as e:
                logger.error(f"Failed to load preprocessor module {module_name}: {e}")

    def get_preprocessor(self, filepath: Path) -> Optional[BasePreprocessor]:
        """Return the appropriate pre-processor for the given file."""
        # Try suffix first (e.g., .py)
        if filepath.suffix in self.preprocessors:
            return self.preprocessors[filepath.suffix]
            
        # Try full filename (e.g., Dockerfile)
        if filepath.name in self.preprocessors:
            return self.preprocessors[filepath.name]
            
        return None

    def preprocess(self, filepath: Path) -> Optional[str]:
        """Run the appropriate pre-processor and return the text."""
        preprocessor = self.get_preprocessor(filepath)
        if preprocessor:
            try:
                return preprocessor.preprocess(filepath)
            except Exception as e:
                logger.error(f"Error preprocessing {filepath} with {preprocessor.__class__.__name__}: {e}")
                return None
        return None
