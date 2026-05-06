import signal
import time
import uuid
import logging
import queue
import threading
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from watchdog.observers import Observer
from qdrant_client import models
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
from rich.live import Live
from rich.console import Console
from core.clients import get_db, get_embeddings_batch, detect_embedding_dim
from core.config import settings
from core.filesystem import EXCLUDED_DIRS
from .state import StateManager
from .git_utils import GitManager
from .preprocessors.manager import PreprocessorManager
from .index_worker import IndexWorker
from .code_handler import CodeHandler, EXTENSION_TO_LANG

logger = logging.getLogger(__name__)


class Indexer:
    def __init__(self, console: Optional[Console] = None):
        # Bounded queue provides natural backpressure: when the queue is
        # full, the file scanner blocks, preventing unbounded memory growth
        # during large initial scans.
        maxsize = settings.indexer_workers * 100
        self.task_queue = queue.Queue(maxsize=maxsize)
        self.state_manager = StateManager(settings.state.directory)
        self.git_manager = GitManager(Path.cwd()) if settings.git_enabled else None
        self.console = console or Console()
        self.preprocessor_manager = PreprocessorManager()
        
        self.workers = []
        for _ in range(settings.indexer_workers):
            self.workers.append(IndexWorker(self.task_queue, self.state_manager, self.git_manager))
            
        self.observer = Observer()
        
        # Signal handling for graceful shutdown (SIGTERM)
        signal.signal(signal.SIGTERM, self._handle_exit)

    def _handle_exit(self, signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.stop()
        import sys
        sys.exit(0)

    def start(self, path: Path, watch: bool = True, detach_callback=None):
        self.state_manager.write_pid()
        self.git_manager = GitManager(path) if settings.git_enabled else None
        
        # Start input monitor for 'd' key
        self._stop_event = threading.Event()
        if detach_callback:
            threading.Thread(target=self._monitor_input, args=(detach_callback,), daemon=True).start()
        
        for w in self.workers:
            w.git_manager = self.git_manager
            w.start()
        
        # Startup Scan
        self._scan_directory(path)
        
        if watch:
            event_handler = CodeHandler(self.task_queue, self.git_manager)
            self.observer.schedule(event_handler, str(path), recursive=True)
            self.observer.start()
            logger.info(f"Watching for changes in {path}")
            try:
                while not self._stop_event.is_set():
                    self.observer.join(1)
            except KeyboardInterrupt:
                self.stop()
        else:
            try:
                while self.task_queue.unfinished_tasks > 0 and not self._stop_event.is_set():
                    time.sleep(0.1)
            except KeyboardInterrupt:
                logger.info("Scan interrupted by user")
            self.stop()

    def _monitor_input(self, detach_callback):
        """Monitor stdin for 'd' key to detach."""
        import sys
        import tty
        import termios
        
        fd = sys.stdin.fileno()
        if not os.isatty(fd):
            return

        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            while not self._stop_event.is_set():
                char = sys.stdin.read(1)
                if char.lower() == 'd':
                    self._stop_event.set()
                    # Restore terminal before callback, so the
                    # background child does not inherit raw mode.
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                    detach_callback()
                    return
                if char == '\x03': # Ctrl-C
                    return
        except Exception as exc:
            logger.debug("Input monitor error (non-fatal): %s", exc)
        finally:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            except Exception:
                pass

    def _scan_directory(self, path: Path):
        extensions = self.preprocessor_manager.supported_extensions
        filenames = ('Dockerfile',)
        
        files_to_index = []
        
        # UI with Rich
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=self.console,
            expand=True
        )

        with Live(progress, console=self.console, refresh_per_second=10, vertical_overflow="visible"):
            scan_task = progress.add_task("[cyan]Scanning files...", total=None)
            
            for root, dirs, files in os.walk(path):
                root_path = Path(root)
                
                # Prune ignored/blacklisted directories from recursion
                for d in list(dirs):
                    dir_path = root_path / d
                    # Skip hidden directories (starting with '.') — includes .hivemind,
                    # .git (already in EXCLUDED_DIRS), .venv, etc.
                    if d.startswith("."):
                        dirs.remove(d)
                        continue
                    if d in EXCLUDED_DIRS:
                        dirs.remove(d)
                        continue
                    if settings.git_enabled and self.git_manager:
                        if self.git_manager.is_ignored(dir_path):
                            dirs.remove(d)
                            continue

                for f in files:
                    file_path = root_path / f
                    
                    try:
                        rel_path = file_path.relative_to(path)
                    except ValueError:
                        rel_path = file_path
                        
                    progress.update(scan_task, description=f"[cyan]Scanning: [dim]{rel_path}[/dim]")

                    if not (file_path.suffix in extensions or file_path.name in filenames):
                        continue
                    
                    if settings.git_enabled and self.git_manager:
                        if self.git_manager.is_ignored(file_path):
                            continue
                        if settings.git_only_tracked and not self.git_manager.is_tracked(file_path):
                            continue
                    
                    if self.state_manager.should_reindex(file_path):
                        files_to_index.append(file_path)

            progress.remove_task(scan_task)
            
            if not files_to_index:
                logger.info("All files are up to date!")
                return

            index_task = progress.add_task(f"[green]Indexing {len(files_to_index)} files...", total=len(files_to_index))
            
            # Give workers a way to update this bar
            for w in self.workers:
                w.progress_callback = lambda: progress.update(index_task, advance=1)
            
            for file_path in files_to_index:
                self.task_queue.put(file_path)
                
            # Wait for the initial batch to finish
            try:
                while self.task_queue.unfinished_tasks > 0 and not self._stop_event.is_set():
                    time.sleep(0.1)
            except KeyboardInterrupt:
                raise
        
        # Clear callbacks
        for w in self.workers:
            w.progress_callback = None
            
        # Mark indexing as complete in Qdrant
        self._upsert_indexing_metadata(path, complete=True)

    def _upsert_indexing_metadata(self, workspace_path: Path, complete: bool = True):
        """Upsert a metadata point to Qdrant to track indexing status."""
        # Create a deterministic ID for this workspace's metadata
        meta_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{workspace_path.resolve().absolute()}_indexing_metadata"))

        # Use a zero vector for the metadata point (not used for search)
        vector = {
            "": [0.0] * detect_embedding_dim(),
            "code-sparse": models.SparseVector(indices=[], values=[]),
        }
        
        payload = {
            "type": "metadata",
            "workspace_path": str(workspace_path),
            "indexing_complete": complete,
            "last_indexed_at": datetime.now().isoformat(),
        }
        
        try:
            get_db().upsert(
                collection_name=settings.qdrant.collection_name,
                points=[
                    models.PointStruct(
                        id=meta_id,
                        vector=vector,
                        payload=payload
                    )
                ]
            )
            logger.info(f"Indexing metadata updated: complete={complete}")
        except Exception as e:
            logger.error(f"Failed to update indexing metadata: {e}")

    def stop(self):
        self.observer.stop()
        for _ in self.workers:
            self.task_queue.put(None)
        for w in self.workers:
            w.join()
        self.state_manager.flush()
        self.state_manager.remove_pid()
