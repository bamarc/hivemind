"""Worker thread that indexes individual files in the Hivemind pipeline."""

import time
import uuid
import logging
import queue
import threading
from pathlib import Path
from typing import Optional
from qdrant_client import models
from core.clients import get_db
from core.config import settings
from .state import StateManager
from .chunkers.by_size import BySizeChunker
from .chunkers.by_lines import ByLinesChunker
from .chunkers.ast import ASTChunker
from .chunkers.markdown import MarkdownChunker
from .git_utils import GitManager
from .code_handler import EXTENSION_TO_LANG

logger = logging.getLogger(__name__)


class IndexWorker(threading.Thread):
    def __init__(self, task_queue: queue.Queue, state_manager: StateManager, git_manager: Optional[GitManager] = None):
        super().__init__(daemon=True)
        self.task_queue = task_queue
        self.state_manager = state_manager
        self.git_manager = git_manager
        from .preprocessors.manager import PreprocessorManager
        self.preprocessor_manager = PreprocessorManager()
        
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
        
        content = self.preprocessor_manager.preprocess(filepath)
        if content is None:
            logger.error(f"Failed to preprocess or read file: {filepath}")
            return
        
        # Use specialized markdown chunker for .md files.
        # For other file types (e.g. pre-processed PDFs that produce Markdown),
        # only apply the heuristic when the extension is *not* a known code
        # language — this prevents Python files whose first line is a comment
        # from being incorrectly routed to the markdown chunker.
        is_known_code_ext = filepath.suffix in EXTENSION_TO_LANG
        looks_like_markdown = content.startswith("---") or content.startswith("# ")

        if filepath.suffix == ".md" or (not is_known_code_ext and looks_like_markdown):
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
            from core.clients import get_embeddings_batch, text_to_sparse_vector
            vectors = get_embeddings_batch(texts)
            
            for i, chunk in enumerate(chunks):
                vector = vectors[i]
                point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{chunk.filepath}_chunk_{chunk.chunk_index}"))
                
                # Generate sparse vector for hybrid search (if enabled)
                if settings.sparse.enabled:
                    sparse_vector = text_to_sparse_vector(chunk.content)
                else:
                    sparse_vector = models.SparseVector(indices=[], values=[])
                
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
                    "vector": {
                        "": vector,
                        "code-sparse": sparse_vector,
                    },
                    "payload": payload
                })
        embed_time = time.perf_counter() - t1

        # 3. Upsert
        t2 = time.perf_counter()
        if points:
            get_db().upsert(
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
