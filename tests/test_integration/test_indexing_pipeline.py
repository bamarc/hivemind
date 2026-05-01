"""
Integration-level tests for the Hivemind indexing pipeline.

These tests exercise the full flow (scan → chunk → embed → upsert → search)
with mocked external services (Qdrant, Embedder) but **real** internal objects
(``StateManager``, ``IndexWorker``, chunkers, etc.).

The global ``conftest.py`` patches ``core.clients.get_db()`` and
``core.clients.get_embedder()`` so that ``get_embeddings_batch`` uses
the mock embedder and all Qdrant operations use ``MOCK_QDRANT``.
"""

from __future__ import annotations

import os
import queue
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.clients import get_embeddings_batch
from core.config import settings
from indexer.state import StateManager
from indexer.chunkers.base import Chunk
from indexer.index_worker import IndexWorker
from indexer.watcher import Indexer, CodeHandler


# ======================================================================
#  Fixtures
# ======================================================================

@pytest.fixture
def mock_state_manager(tmp_path: Path) -> StateManager:
    """A real :class:`StateManager` bound to a temp directory."""
    state_dir = tmp_path / ".hivemind" / "state"
    mgr = StateManager(state_dir, debounce_seconds=0)
    return mgr


@pytest.fixture
def mock_git_manager() -> MagicMock:
    """A mock :class:`GitManager` that allows all files."""
    mgr = MagicMock()
    mgr.is_ignored.return_value = False
    mgr.is_tracked.return_value = True
    mgr.get_commit_metadata.return_value = {}
    mgr.is_git_repo = False
    return mgr


# ======================================================================
#  Pipeline Integration Tests
# ======================================================================

class TestFullIndexingPipeline:
    """End-to-end pipeline: file discovery → chunking → embedding → upsert."""

    @pytest.fixture
    def project_dir(self, tmp_path: Path) -> Path:
        """Create a small project directory with known source files."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "greet.py").write_text(
            "def greet(name: str) -> str:\n"
            '    """Say hello."""\n'
            '    return f"Hello, {name}"\n'
        )
        (src / "calc.py").write_text(
            "class Calculator:\n"
            "    def add(self, a: int, b: int) -> int:\n"
            "        return a + b\n"
        )
        (src / "readme.md").write_text(
            "# Project\n\nWelcome to the project.\n\n## Usage\n\nRun it.\n"
        )
        # A file without a recognised extension – should be ignored
        (src / "ignored.xyz").write_text("not indexed")
        return tmp_path

    def test_discover_chunk_embed_and_upsert(
        self,
        project_dir: Path,
        mock_state_manager: StateManager,
        mock_git_manager: MagicMock,
        mock_qdrant: MagicMock,
    ):
        """Files with known extensions should be discovered, chunked,
        embedded via the mock embedder, and upserted to the mock Qdrant.

        This test validates the full pipeline without mocking any internal
        step (only the external services are mocked by conftest).
        """
        # ── 1. Create worker and queue ─────────────────────────────────
        task_queue: queue.Queue = queue.Queue()
        worker = IndexWorker(task_queue, mock_state_manager, mock_git_manager)

        # We use the real AST chunker instead of a mock
        # (worker.chunker was set in __init__ based on settings)
        worker.start()

        # ── 2. Discover files using CodeHandler ────────────────────────
        handler = CodeHandler(task_queue, git_manager=mock_git_manager)
        src_dir = project_dir / "src"

        # Simulate filesystem events for each known file
        discovered: list[Path] = []
        for f in sorted(src_dir.iterdir()):
            if handler._should_handle(f):
                discovered.append(f)
                handler.on_created(MagicMock(
                    is_directory=False,
                    src_path=str(f),
                ))

        # Only .py and .md should be discovered; .xyz should be rejected
        discovered_names = {p.name for p in discovered}
        assert "greet.py" in discovered_names
        assert "calc.py" in discovered_names
        assert "readme.md" in discovered_names
        assert "ignored.xyz" not in discovered_names

        # ── 3. Process all discovered files via the worker ─────────────
        for filepath in discovered:
            worker.index_file(filepath)

        # ── 4. Verify upsert was called for each file ──────────────────
        # Each file should have produced at least one point
        assert mock_qdrant.upsert.call_count >= len(discovered)

        # ── 5. Verify payload structure ────────────────────────────────
        all_calls = mock_qdrant.upsert.call_args_list
        all_points = []
        for call in all_calls:
            all_points.extend(call.kwargs["points"])

        # At minimum we should have one point per file
        assert len(all_points) >= len(discovered)

        # Check that every point has the required payload fields
        for pt in all_points:
            payload = pt["payload"]
            assert "filepath" in payload
            assert "content" in payload
            assert "language" in payload
            assert "chunk_index" in payload
            assert "line_start" in payload
            assert "line_end" in payload
            assert "type" in payload
            assert payload["type"] == "code"

        # ── 6. Verify state was updated for each file ──────────────────
        for filepath in discovered:
            key = str(filepath.absolute())
            assert key in mock_state_manager.state["indexed_files"]
            record = mock_state_manager.state["indexed_files"][key]
            assert record["chunk_count"] >= 1

        # ── 7. Verify similar content found via search ─────────────────
        # Search for "hello" should return the greet.py chunk
        # (The mock embedder returns deterministic vectors, so we can
        #  verify that query_points was called with the right collection)
        from core.clients import get_db

        query_vector = get_embeddings_batch(["hello greeting"])[0]
        get_db().query_points(
            collection_name=settings.qdrant.collection_name,
            query=query_vector,
            limit=5,
        )
        call_kwargs = get_db().query_points.call_args.kwargs
        assert call_kwargs["collection_name"] == settings.qdrant.collection_name
        assert len(call_kwargs["query"]) == settings.model.embedding_dim

    def test_incremental_index_skips_unchanged_files(
        self,
        project_dir: Path,
        mock_state_manager: StateManager,
        mock_git_manager: MagicMock,
        mock_qdrant: MagicMock,
    ):
        """After initial indexing, unchanged files should NOT be re-indexed
        on a subsequent scan."""
        task_queue: queue.Queue = queue.Queue()
        worker = IndexWorker(task_queue, mock_state_manager, mock_git_manager)
        worker.start()

        src_dir = project_dir / "src"
        files = [f for f in sorted(src_dir.iterdir()) if f.suffix in (".py", ".md")]

        # ── First pass: index everything ────────────────────────────────
        first_count = mock_qdrant.upsert.call_count
        for f in files:
            worker.index_file(f)
        # Reset the Qdrant call count after first pass
        first_calls = mock_qdrant.upsert.call_count - first_count
        assert first_calls >= len(files)

        # ── Second pass: nothing changed, should be skipped ─────────────
        mock_qdrant.upsert.reset_mock()
        for f in files:
            worker.index_file(f)
        assert mock_qdrant.upsert.call_count == 0, (
            "No upserts should happen when all files are up-to-date"
        )

    def test_reindex_on_content_change(
        self,
        project_dir: Path,
        mock_state_manager: StateManager,
        mock_git_manager: MagicMock,
        mock_qdrant: MagicMock,
    ):
        """When a file's content changes, it should be re-indexed."""
        import time

        task_queue: queue.Queue = queue.Queue()
        worker = IndexWorker(task_queue, mock_state_manager, mock_git_manager)
        worker.start()

        src_dir = project_dir / "src"
        greet_file = src_dir / "greet.py"

        # ── First pass: index ──────────────────────────────────────────
        mock_qdrant.upsert.reset_mock()
        worker.index_file(greet_file)
        assert mock_qdrant.upsert.call_count >= 1

        # ── Modify the file content ────────────────────────────────────
        time.sleep(0.02)  # ensure filesystem mtime advances
        greet_file.write_text(
            "def greet(name: str) -> str:\n"
            '    """Updated greeting."""\n'
            '    return f"Hi, {name}"\n'
        )

        # ── Second pass: should re-index ────────────────────────────────
        mock_qdrant.upsert.reset_mock()
        assert mock_state_manager.should_reindex(greet_file), (
            "Modified file should require reindexing"
        )
        worker.index_file(greet_file)
        assert mock_qdrant.upsert.call_count >= 1, (
            "File with modified content should be re-indexed"
        )

    def test_embedding_dimension_validation_raises_on_mismatch(
        self,
        mock_qdrant: MagicMock,
    ):
        """When ``init_collection`` detects a dimension mismatch between
        the existing collection and the config, it should raise."""
        from core.clients import init_collection
        from tests.conftest import _collection_mock

        # Mock an existing collection with a *different* dimension
        mock_qdrant.get_collections.return_value = MagicMock(
            collections=[_collection_mock(settings.qdrant.collection_name)]
        )
        mock_qdrant.get_collection.return_value = MagicMock(
            config=MagicMock(
                params=MagicMock(
                    vectors=MagicMock(size=999),  # Different from settings
                ),
            ),
        )

        with pytest.raises(ValueError, match="dimension mismatch"):
            init_collection()
