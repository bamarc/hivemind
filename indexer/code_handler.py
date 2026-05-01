"""File system event handler for the Hivemind indexer."""

import queue
from pathlib import Path
from typing import Optional
from watchdog.events import FileSystemEventHandler
from core.config import settings
from core.filesystem import EXCLUDED_DIRS
from .git_utils import GitManager

EXTENSION_TO_LANG = {
    '.py': 'python',
    '.go': 'go',
    '.js': 'javascript',
    '.ts': 'typescript',
    '.tsx': 'typescript',
    '.md': 'markdown',
    '.yaml': 'yaml',
    '.yml': 'yaml',
    '.toml': 'toml',
    '.c': 'c',
    '.h': 'c',
    '.sh': 'shell',
    '.tf': 'hcl',
    '.css': 'css',
    '.scss': 'scss',
    '.conf': 'config',
    'Dockerfile': 'dockerfile'
}


class CodeHandler(FileSystemEventHandler):
    def __init__(self, task_queue: queue.Queue, git_manager: Optional[GitManager] = None):
        self.task_queue = task_queue
        self.git_manager = git_manager
        from .preprocessors.manager import PreprocessorManager
        self.preprocessor_manager = PreprocessorManager()
        self.extensions = self.preprocessor_manager.supported_extensions
        self.filenames = ('Dockerfile',)

    def _should_handle(self, filepath: Path) -> bool:
        if not (filepath.suffix in self.extensions or filepath.name in self.filenames):
            return False
        
        if settings.git_enabled and self.git_manager:
            if self.git_manager.is_ignored(filepath):
                return False
            if settings.git_only_tracked and not self.git_manager.is_tracked(filepath):
                return False
        
        # Reject files inside excluded directories (derived from core/filesystem.py)
        if any(part in EXCLUDED_DIRS for part in filepath.parts):
            return False
            
        return True

    def on_modified(self, event):
        if not event.is_directory and self._should_handle(Path(event.src_path)):
            self.task_queue.put(Path(event.src_path))

    def on_created(self, event):
        if not event.is_directory and self._should_handle(Path(event.src_path)):
            self.task_queue.put(Path(event.src_path))
