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
from watchdog.events import FileSystemEventHandler
from qdrant_client import models
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
from rich.live import Live
from rich.console import Console
from core.clients import db, get_embedding, get_embeddings_batch
from core.config import settings
from .state import StateManager
from .chunkers.by_size import BySizeChunker
from .chunkers.by_lines import ByLinesChunker
from .chunkers.ast import ASTChunker
from .chunkers.markdown import MarkdownChunker
from .git_utils import GitManager

logger = logging.getLogger(__name__)

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
    '.sh': 'shell',
    '.conf': 'config',
    'Dockerfile': 'dockerfile'
}

class IndexWorker(threading.Thread):
    def __init__(self, task_queue: queue.Queue, state_manager: StateManager, git_manager: Optional[GitManager] = None):
        super().__init__(daemon=True)
        self.task_queue = task_queue
        self.state_manager = state_manager
        self.git_manager = git_manager
        
        # Select chunker based on config
        if settings.chunking.strategy == "by_lines":
            self.chunker = ByLinesChunker(
                chunk_lines=settings.chunking.by_lines.chunk_lines,
                overlap_lines=settings.chunking.by_lines.overlap_lines
            )
        elif settings.chunking.strategy == "ast":
            self.chunker = ASTChunker(
                chunk_lines=settings.chunking.ast.chunk_lines,
                overlap_lines=settings.chunking.ast.overlap_lines
            )
        else:
            self.chunker = BySizeChunker(
                chunk_size=settings.chunking.by_size.chunk_size,
                overlap=settings.chunking.by_size.overlap
            )
        
        # Dedicated Markdown chunker
        self.markdown_chunker = MarkdownChunker()
        self.progress_callback = None

    def run(self):
        while True:
            filepath = self.task_queue.get()
            if filepath is None:
                break
            try:
                self.index_file(filepath)
            except Exception as e:
                logger.error(f"Error indexing {filepath}: {e}")
            finally:
                if self.progress_callback:
                    self.progress_callback()
                self.task_queue.task_done()

    def index_file(self, filepath: Path):
        if not self.state_manager.should_reindex(filepath):
            logger.debug(f"Skipping unchanged file: {filepath}")
            return

        start_total = time.perf_counter()
        logger.info(f"Indexing: {filepath}")
        
        # 1. Read and Chunk
        t0 = time.perf_counter()
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Use specialized markdown chunker for .md files
        if filepath.suffix == ".md":
            chunks = self.markdown_chunker.chunk(content, str(filepath))
        else:
            chunks = self.chunker.chunk(content, str(filepath))
            
        chunk_time = time.perf_counter() - t0
        
        # Get git metadata if enabled
        git_metadata = {}
        if settings.git_enabled and self.git_manager:
            git_metadata = self.git_manager.get_commit_metadata(filepath)

        # Determine file-level metadata
        extension = filepath.suffix
        language = EXTENSION_TO_LANG.get(extension if extension else filepath.name, "unknown")
        is_test = any(pattern in filepath.name.lower() for pattern in ("test", "spec", "_test"))

        # 2. Embed
        t1 = time.perf_counter()
        points = []
        if chunks:
            # Batch fetch embeddings
            texts = [chunk.content for chunk in chunks]
            vectors = get_embeddings_batch(texts)
            
            for i, chunk in enumerate(chunks):
                vector = vectors[i]
                point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{chunk.filepath}_chunk_{chunk.chunk_index}"))
                
                # Process path segments for hierarchical filtering
                rel_path = chunk.filepath
                try:
                    # Attempt to get path relative to current working directory
                    rel_path = str(Path(chunk.filepath).relative_to(Path.cwd()))
                except ValueError:
                    pass
                
                path_segments = {
                    str(i): segment 
                    for i, segment in enumerate(Path(rel_path).parts[:5])
                }
                
                payload = {
                    "filepath": chunk.filepath,
                    "content": chunk.content,
                    "chunk_index": chunk.chunk_index,
                    "language": language,
                    "line_start": chunk.line_start,
                    "line_end": chunk.line_end,
                    "is_test": is_test,
                    "symbols": chunk.metadata.get("symbols", []) if chunk.metadata else [],
                    "type": "code",
                    "path_segments": path_segments,
                    **git_metadata
                }
                
                points.append({
                    "id": point_id,
                    "vector": vector,
                    "payload": payload
                })
        embed_time = time.perf_counter() - t1

        # 3. Upsert
        t2 = time.perf_counter()
        if points:
            db.upsert(
                collection_name=settings.qdrant.collection_name,
                points=points
            )
        upsert_time = time.perf_counter() - t2
        
        total_time = time.perf_counter() - start_total
        self.state_manager.update_file_state(filepath, len(chunks))
        
        logger.info(
            f"Indexed {filepath}: {len(chunks)} chunks in {total_time:.2f}s "
            f"(chunk: {chunk_time:.2f}s, embed: {embed_time:.2f}s, upsert: {upsert_time:.2f}s)"
        )

class CodeHandler(FileSystemEventHandler):
    def __init__(self, task_queue: queue.Queue, git_manager: Optional[GitManager] = None):
        self.task_queue = task_queue
        self.git_manager = git_manager
        self.extensions = (
            '.py', '.go', '.js', '.ts', '.md', '.txt', '.yaml', '.yml', '.toml',
            '.c', '.h', '.adoc', '.tsx', '.css', '.scss', '.tf', '.sh', '.conf'
        )
        self.filenames = ('Dockerfile',)

    def _should_handle(self, filepath: Path) -> bool:
        if not (filepath.suffix in self.extensions or filepath.name in self.filenames):
            return False
        
        if settings.git_enabled and self.git_manager:
            if self.git_manager.is_ignored(filepath):
                return False
            if settings.git_only_tracked and not self.git_manager.is_tracked(filepath):
                return False
        
        # Hardcoded safety checks
        if ".venv" in filepath.parts or ".git" in filepath.parts:
            return False
            
        return True

    def on_modified(self, event):
        if not event.is_directory and self._should_handle(Path(event.src_path)):
            self.task_queue.put(Path(event.src_path))

    def on_created(self, event):
        if not event.is_directory and self._should_handle(Path(event.src_path)):
            self.task_queue.put(Path(event.src_path))

class Indexer:
    def __init__(self, console: Optional[Console] = None):
        self.task_queue = queue.Queue()
        self.state_manager = StateManager(settings.state.directory)
        self.git_manager = GitManager(Path.cwd()) if settings.git_enabled else None
        self.console = console or Console()
        
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
                    # Restore terminal before callback
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                    detach_callback()
                    return
                if char == '\x03': # Ctrl-C
                    return
        except Exception:
            pass
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def _scan_directory(self, path: Path):
        extensions = (
            '.py', '.go', '.js', '.ts', '.md', '.txt', '.yaml', '.yml', '.toml',
            '.c', '.h', '.adoc', '.tsx', '.css', '.scss', '.tf', '.sh', '.conf'
        )
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
                    if d in (".git", ".venv", "__pycache__"):
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
        meta_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{workspace_path}_indexing_metadata"))
        
        # Use a zero vector for the metadata point (not used for search)
        vector = [0.0] * settings.model.embedding_dim
        
        payload = {
            "type": "metadata",
            "workspace_path": str(workspace_path),
            "indexing_complete": complete,
            "last_indexed_at": datetime.now().isoformat(),
        }
        
        try:
            db.upsert(
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
