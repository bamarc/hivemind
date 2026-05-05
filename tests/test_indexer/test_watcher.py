"""
Tests for :mod:`indexer.watcher`.

The module contains three main classes:

* :class:`CodeHandler` — a watchdog ``FileSystemEventHandler`` that filters
  files and enqueues them for processing.
* :class:`IndexWorker` — a ``threading.Thread`` that consumes a task queue
  and runs the full indexing pipeline (preprocess → chunk → embed → upsert).
* :class:`Indexer` — orchestrates workers, directory scanning, and
  filesystem watching.

External dependencies (``core.clients.db``, ``core.clients.get_embeddings_batch``)
are already mocked by the global ``conftest.py``.
"""

from __future__ import annotations

import os
import signal
import queue
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch, call, ANY

import pytest

from indexer.chunkers.base import Chunk
from indexer.watcher import CodeHandler, IndexWorker, Indexer, EXTENSION_TO_LANG


# ======================================================================
#  Fixtures – shared mocks
# ======================================================================

@pytest.fixture
def mock_queue() -> MagicMock:
    """A mock :class:`queue.Queue`."""
    return MagicMock(spec=queue.Queue)


@pytest.fixture
def mock_state_manager() -> MagicMock:
    """A mock :class:`StateManager` that always recommends reindexing."""
    mgr = MagicMock()
    mgr.should_reindex.return_value = True
    mgr.update_file_state.return_value = None
    mgr.flush.return_value = None
    mgr.write_pid.return_value = None
    mgr.remove_pid.return_value = None
    return mgr


@pytest.fixture
def mock_git_manager() -> MagicMock:
    """A mock :class:`GitManager` that allows all files."""
    mgr = MagicMock()
    mgr.is_ignored.return_value = False
    mgr.is_tracked.return_value = True
    mgr.get_commit_metadata.return_value = {}
    return mgr


@pytest.fixture
def mock_chunk() -> Chunk:
    """A single :class:`Chunk` instance for pipeline tests."""
    return Chunk(
        content="def foo(): pass",
        filepath="/tmp/test.py",
        chunk_index=0,
        line_start=1,
        line_end=1,
    )


# ======================================================================
#  CodeHandler
# ======================================================================

class TestCodeHandler:
    """Tests for the watchdog event handler."""

    def test_should_handle_known_extension(self, mock_queue: MagicMock):
        """A ``.py`` file should pass the extension filter."""
        handler = CodeHandler(mock_queue, git_manager=None)
        assert handler._should_handle(Path("test.py")) is True

    def test_should_handle_dockerfile(self, mock_queue: MagicMock):
        """The ``Dockerfile`` (no suffix) should be accepted."""
        handler = CodeHandler(mock_queue, git_manager=None)
        assert handler._should_handle(Path("Dockerfile")) is True

    def test_should_not_handle_unknown_extension(self, mock_queue: MagicMock):
        """A ``.xyz`` file (no preprocessor) should be rejected."""
        handler = CodeHandler(mock_queue, git_manager=None)
        assert handler._should_handle(Path("document.xyz")) is False

    def test_should_not_handle_venv_directory(self, mock_queue: MagicMock):
        """Files inside ``.venv`` should be rejected."""
        handler = CodeHandler(mock_queue, git_manager=None)
        assert handler._should_handle(Path("/project/.venv/lib/site-packages/pkg.py")) is False

    def test_should_not_handle_git_directory(self, mock_queue: MagicMock):
        """Files inside ``.git`` should be rejected."""
        handler = CodeHandler(mock_queue, git_manager=None)
        assert handler._should_handle(Path("/project/.git/objects/abc123")) is False

    def test_should_not_handle_gitignored_file(
        self, mock_queue: MagicMock, mock_git_manager: MagicMock
    ):
        """When the git manager says a file is ignored, it should be rejected."""
        mock_git_manager.is_ignored.return_value = True
        handler = CodeHandler(mock_queue, mock_git_manager)
        assert handler._should_handle(Path("secret.log")) is False

    def test_on_modified_enqueues_file(self, mock_queue: MagicMock):
        """``on_modified`` should put the source path onto the queue."""
        handler = CodeHandler(mock_queue, git_manager=None)
        event = MagicMock()
        event.is_directory = False
        event.src_path = "/tmp/test.py"
        handler.on_modified(event)
        mock_queue.put.assert_called_once_with(Path("/tmp/test.py"))

    def test_on_modified_skips_directories(self, mock_queue: MagicMock):
        """Directory modifications should not be enqueued."""
        handler = CodeHandler(mock_queue, git_manager=None)
        event = MagicMock()
        event.is_directory = True
        handler.on_modified(event)
        mock_queue.put.assert_not_called()

    def test_on_created_enqueues_file(self, mock_queue: MagicMock):
        """``on_created`` should put the source path onto the queue."""
        handler = CodeHandler(mock_queue, git_manager=None)
        event = MagicMock()
        event.is_directory = False
        event.src_path = "/tmp/new.py"
        handler.on_created(event)
        mock_queue.put.assert_called_once_with(Path("/tmp/new.py"))


# ======================================================================
#  IndexWorker
# ======================================================================

class TestIndexWorker:
    """Tests for the indexing worker thread.

    We test ``index_file`` directly (rather than ``run``) to avoid the
    infinite loop and threading complexity.
    """

    @patch("indexer.preprocessors.manager.PreprocessorManager")
    @patch("core.clients.get_embeddings_batch")
    def test_index_file_full_pipeline(
        self,
        mock_get_emb: MagicMock,
        mock_preproc_cls: MagicMock,
        mock_queue: MagicMock,
        mock_state_manager: MagicMock,
        mock_git_manager: MagicMock,
        mock_chunk: Chunk,
    ):
        """The full pipeline (preprocess → chunk → embed → upsert) should
        be called for a file that needs reindexing."""
        # ── Arrange ──────────────────────────────────────────────────────
        mock_preproc = MagicMock()
        mock_preproc.preprocess.return_value = "def foo(): pass"
        mock_preproc_cls.return_value = mock_preproc

        mock_get_emb.return_value = [[0.1] * 2500]  # single embedding

        worker = IndexWorker(mock_queue, mock_state_manager, mock_git_manager)

        # Patch the worker's chunker to return a known chunk
        worker.chunker = MagicMock()
        worker.chunker.chunk.return_value = [mock_chunk]
        worker.markdown_chunker = MagicMock()

        # ── Act ──────────────────────────────────────────────────────────
        test_file = Path("/tmp/test.py")
        worker.index_file(test_file)

        # ── Assert ───────────────────────────────────────────────────────
        # 1. should_reindex was checked
        mock_state_manager.should_reindex.assert_called_once_with(test_file)
        # 2. preprocessor was called
        mock_preproc.preprocess.assert_called_once_with(test_file)
        # 3. chunker was called
        worker.chunker.chunk.assert_called_once()
        # 4. embeddings were fetched
        mock_get_emb.assert_called_once()
        # 5. db.upsert was called (get_db returns the global mock from conftest)
        from indexer.watcher import get_db
        get_db().upsert.assert_called_once()
        # 6. state was updated
        mock_state_manager.update_file_state.assert_called_once_with(test_file, 1)

    @patch("indexer.preprocessors.manager.PreprocessorManager")
    def test_index_file_skips_unchanged(
        self,
        mock_preproc_cls: MagicMock,
        mock_queue: MagicMock,
        mock_state_manager: MagicMock,
        mock_git_manager: MagicMock,
    ):
        """If ``should_reindex`` returns ``False``, the file should be
        skipped entirely."""
        mock_state_manager.should_reindex.return_value = False
        mock_preproc_cls.return_value = MagicMock()

        worker = IndexWorker(mock_queue, mock_state_manager, mock_git_manager)
        worker.chunker = MagicMock()

        test_file = Path("/tmp/unchanged.py")
        worker.index_file(test_file)

        # Preprocessor should NOT be called
        worker.preprocessor_manager.preprocess.assert_not_called()
        # Chunker should NOT be called
        worker.chunker.chunk.assert_not_called()
        # State should NOT be updated
        mock_state_manager.update_file_state.assert_not_called()

    @patch("indexer.preprocessors.manager.PreprocessorManager")
    @patch("core.clients.get_embeddings_batch")
    def test_index_file_uses_markdown_chunker_for_md(
        self,
        mock_get_emb: MagicMock,
        mock_preproc_cls: MagicMock,
        mock_queue: MagicMock,
        mock_state_manager: MagicMock,
        mock_git_manager: MagicMock,
        mock_chunk: Chunk,
    ):
        """``.md`` files should use the dedicated markdown chunker."""
        mock_preproc = MagicMock()
        mock_preproc.preprocess.return_value = "# Heading\n\nSome text"
        mock_preproc_cls.return_value = mock_preproc
        mock_get_emb.return_value = [[0.2] * 2500]

        worker = IndexWorker(mock_queue, mock_state_manager, mock_git_manager)
        worker.chunker = MagicMock()
        worker.markdown_chunker = MagicMock()
        worker.markdown_chunker.chunk.return_value = [mock_chunk]

        worker.index_file(Path("/tmp/readme.md"))

        # Regular chunker should NOT be called for .md
        worker.chunker.chunk.assert_not_called()
        # Markdown chunker SHOULD be called
        worker.markdown_chunker.chunk.assert_called_once()
        mock_get_emb.assert_called_once()

    @patch("indexer.preprocessors.manager.PreprocessorManager")
    def test_index_file_preprocess_failure(
        self,
        mock_preproc_cls: MagicMock,
        mock_queue: MagicMock,
        mock_state_manager: MagicMock,
        mock_git_manager: MagicMock,
    ):
        """If preprocessing returns ``None``, the file should be skipped."""
        mock_preproc = MagicMock()
        mock_preproc.preprocess.return_value = None
        mock_preproc_cls.return_value = mock_preproc

        worker = IndexWorker(mock_queue, mock_state_manager, mock_git_manager)
        worker.chunker = MagicMock()

        worker.index_file(Path("/tmp/broken.py"))
        worker.chunker.chunk.assert_not_called()

    @patch("indexer.preprocessors.manager.PreprocessorManager")
    def test_index_file_uses_git_metadata(
        self,
        mock_preproc_cls: MagicMock,
        mock_queue: MagicMock,
        mock_state_manager: MagicMock,
        mock_git_manager: MagicMock,
        mock_chunk: Chunk,
        monkeypatch,
    ):
        """When ``settings.git_enabled`` is True and a git_manager is
        provided, commit metadata should be added to the Qdrant payload."""
        from core.config import settings

        monkeypatch.setattr(settings, "git_enabled", True)

        mock_preproc = MagicMock()
        mock_preproc.preprocess.return_value = "x = 1"
        mock_preproc_cls.return_value = mock_preproc

        mock_git_manager.get_commit_metadata.return_value = {
            "commit_hash": "abc123",
            "commit_author": "Test",
        }

        worker = IndexWorker(mock_queue, mock_state_manager, mock_git_manager)
        worker.chunker = MagicMock()
        worker.chunker.chunk.return_value = [mock_chunk]

        with patch("core.clients.get_embeddings_batch", return_value=[[0.1] * 2500]):
            worker.index_file(Path("/tmp/test.py"))

        # Verify the upsert payload includes git metadata
        from indexer.watcher import get_db

        call_args = get_db().upsert.call_args
        points = call_args.kwargs["points"]
        assert "commit_hash" in points[0]["payload"]
        assert points[0]["payload"]["commit_hash"] == "abc123"

    def test_run_processes_queue_then_stops(self):
        """``run()`` should process items from the queue and exit when a
        ``None`` sentinel is received."""
        q: queue.Queue = queue.Queue()
        state_mgr = MagicMock()
        state_mgr.should_reindex.return_value = False  # skip processing
        git_mgr = MagicMock()

        worker = IndexWorker(q, state_mgr, git_mgr)
        worker.chunker = MagicMock()
        worker.preprocessor_manager = MagicMock()

        # Put two items and a sentinel
        q.put(Path("/tmp/a.py"))
        q.put(Path("/tmp/b.py"))
        q.put(None)

        worker.run()  # Will exit when it encounters None

        # Both files should have been dequeued
        assert q.empty()

    def test_run_calls_progress_callback(self):
        """The progress callback should be invoked after each file."""
        q: queue.Queue = queue.Queue()
        state_mgr = MagicMock()
        state_mgr.should_reindex.return_value = False
        git_mgr = MagicMock()

        callback = MagicMock()
        worker = IndexWorker(q, state_mgr, git_mgr)
        worker.chunker = MagicMock()
        worker.preprocessor_manager = MagicMock()
        worker.progress_callback = callback

        q.put(Path("/tmp/a.py"))
        q.put(None)

        worker.run()

        # Callback should have been called once (for a.py)
        callback.assert_called_once()


# ======================================================================
#  Indexer
# ======================================================================

class TestIndexer:
    """Tests for the top-level orchestrator."""

    @patch("indexer.watcher.signal.signal")  # prevent real signal registration
    @patch("indexer.watcher.Observer")        # prevent real watchdog observer
    def test_init_creates_workers(
        self,
        mock_observer_cls: MagicMock,
        mock_signal: MagicMock,
    ):
        """The number of workers should match ``settings.indexer_workers``."""
        from core.config import settings

        idx = Indexer()
        assert len(idx.workers) == settings.indexer_workers

    @patch("indexer.watcher.signal.signal")
    @patch("indexer.watcher.Observer")
    def test_stop_graceful(
        self,
        mock_observer_cls: MagicMock,
        mock_signal: MagicMock,
    ):
        """``stop()`` should stop the observer, send sentinels to all
        workers, join them, flush state, and remove the PID file."""
        idx = Indexer()
        # Replace task_queue with a mock so we can assert on .put
        idx.task_queue = MagicMock()
        # Replace state_manager with a mock
        idx.state_manager = MagicMock()
        # Replace workers with real mocks
        worker_mocks = [MagicMock() for _ in range(len(idx.workers))]
        idx.workers = worker_mocks

        idx.stop()

        # Observer should be stopped
        idx.observer.stop.assert_called_once()
        # Each worker should receive a None sentinel
        for _w in worker_mocks:
            idx.task_queue.put.assert_any_call(None)
        # Each worker should be joined
        for w in worker_mocks:
            w.join.assert_called_once()
        # State should be flushed
        idx.state_manager.flush.assert_called_once()
        idx.state_manager.remove_pid.assert_called_once()

    @patch("indexer.watcher.signal.signal")
    @patch("indexer.watcher.Observer")
    @patch("indexer.watcher.os.walk")
    def test_scan_directory_finds_files(
        self,
        mock_walk: MagicMock,
        mock_observer_cls: MagicMock,
        mock_signal: MagicMock,
    ):
        """``_scan_directory`` should walk the directory tree and enqueue
        files with known extensions."""
        idx = Indexer()
        # Replace the task_queue with a mock so we can capture calls
        idx.task_queue = MagicMock()
        idx.task_queue.unfinished_tasks = 0  # allow the wait loop to exit
        idx.state_manager = MagicMock()
        idx.state_manager.should_reindex.return_value = True
        # Disable git filtering so project config (git_only_tracked) doesn't
        # reject mock paths that aren't real git-tracked files.
        idx.git_manager = None

        mock_walk.return_value = [
            ("/project", ["subdir"], ["main.py", "data.xyz", "readme.md"]),
            ("/project/subdir", [], ["util.go"]),
        ]

        idx._scan_directory(Path("/project"))

        # .py, .md, .go should be enqueued; .xyz is not in preprocessor extensions
        enqueued = [call_args[0][0] for call_args in idx.task_queue.put.call_args_list]
        enqueued_names = [p.name for p in enqueued]
        assert "main.py" in enqueued_names
        assert "util.go" in enqueued_names
        assert "readme.md" in enqueued_names
        assert "data.xyz" not in enqueued_names

    @patch("indexer.watcher.signal.signal")
    @patch("indexer.watcher.Observer")
    @patch("indexer.watcher.os.walk")
    def test_scan_directory_skips_git_and_venv(
        self,
        mock_walk: MagicMock,
        mock_observer_cls: MagicMock,
        mock_signal: MagicMock,
    ):
        """The ``.git`` and ``.venv`` directories should be pruned from
        the walk."""
        idx = Indexer()
        idx.task_queue = MagicMock()
        idx.task_queue.unfinished_tasks = 0
        idx.state_manager = MagicMock()
        idx.state_manager.should_reindex.return_value = True

        # os.walk receives a mutable list of directory names; we verify
        # that .git and .venv are removed.
        dirs_list = ["lib", ".git", ".venv", "src"]
        mock_walk.return_value = [
            ("/project", dirs_list, ["main.py"]),
        ]

        idx._scan_directory(Path("/project"))

        # .git and .venv should have been removed from the dirs list
        assert ".git" not in dirs_list
        assert ".venv" not in dirs_list
        assert "lib" in dirs_list
        assert "src" in dirs_list

    @patch("indexer.watcher.signal.signal")
    @patch("indexer.watcher.Observer")
    def test_handle_exit_calls_stop(
        self,
        mock_observer_cls: MagicMock,
        mock_signal: MagicMock,
    ):
        """``_handle_exit`` should call ``stop()`` on the indexer."""
        idx = Indexer()
        idx.stop = MagicMock()

        with patch("sys.exit") as mock_exit:
            idx._handle_exit(signal.SIGTERM, None)

        idx.stop.assert_called_once()
        mock_exit.assert_called_once_with(0)

    @patch("indexer.watcher.signal.signal")
    @patch("indexer.watcher.Observer")
    @patch("indexer.watcher.os.walk")
    def test_scan_directory_indexing_metadata(
        self,
        mock_walk: MagicMock,
        mock_observer_cls: MagicMock,
        mock_signal: MagicMock,
    ):
        """After scanning, indexing metadata should be upserted to Qdrant."""
        idx = Indexer()
        idx.task_queue = MagicMock()
        idx.task_queue.unfinished_tasks = 0
        idx.state_manager = MagicMock()
        idx.state_manager.should_reindex.return_value = True
        idx.workers = [MagicMock() for _ in idx.workers]
        # Disable git filtering so project config (git_only_tracked) doesn't
        # reject mock paths that aren't real git-tracked files.
        idx.git_manager = None

        mock_walk.return_value = [
            ("/project", [], ["main.py"]),
        ]

        with patch("core.clients.get_embeddings_batch", return_value=[[0.0] * 2500]):
            idx._scan_directory(Path("/project"))

        from indexer.watcher import get_db

        # Should have upserted metadata at the end
        # The last upsert call should be the metadata point
        assert get_db().upsert.call_count >= 1
