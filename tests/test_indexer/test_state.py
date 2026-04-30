"""
Tests for :mod:`indexer.state`.

The :class:`StateManager` tracks which files have been indexed, their
modification times, SHA-256 checksums, and provides debounced persistence
to a YAML file.  All tests use ``tmp_path`` so no real filesystem state
is touched.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
import yaml

from indexer.state import StateManager


@pytest.fixture
def state_dir(tmp_path: Path) -> Path:
    """Return a temporary directory for the state file."""
    return tmp_path / ".hivemind" / "state"


@pytest.fixture
def manager(state_dir: Path) -> StateManager:
    """Return a fresh :class:`StateManager` bound to the temp directory."""
    return StateManager(state_dir)


# ======================================================================
#  Initialisation
# ======================================================================


class TestInit:
    def test_creates_state_dir_on_first_load(self, state_dir: Path):
        """The state directory should be created when the manager is
        instantiated for the first time."""
        assert not state_dir.exists()
        StateManager(state_dir)
        assert state_dir.is_dir()

    def test_loads_existing_state_file(self, state_dir: Path):
        """If a ``state.yaml`` already exists, it should be loaded."""
        state_dir.mkdir(parents=True)
        state_file = state_dir / "state.yaml"
        state_file.write_text(
            yaml.safe_dump({"indexed_files": {"test.py": {"chunk_count": 5}}})
        )

        m = StateManager(state_dir)
        assert m.state["indexed_files"]["test.py"]["chunk_count"] == 5

    def test_loads_corrupted_state_gracefully(self, state_dir: Path, caplog):
        """If the state file is corrupted, it should fall back to an empty
        state and log a warning."""
        state_dir.mkdir(parents=True)
        (state_dir / "state.yaml").write_text("{invalid_yaml: [broken")

        import logging

        with caplog.at_level(logging.ERROR):
            m = StateManager(state_dir)
        assert m.state == {"indexed_files": {}}
        assert "Failed to load" in caplog.text

    def test_default_state_structure(self, manager: StateManager):
        """A fresh manager should have the expected dict structure."""
        assert "indexed_files" in manager.state
        assert isinstance(manager.state["indexed_files"], dict)


# ======================================================================
#  PID management
# ======================================================================


class TestPidManagement:
    def test_write_pid_creates_file(self, manager: StateManager):
        """``write_pid`` should create a PID file with the current process
        ID."""
        manager.write_pid()
        assert manager.pid_file.exists()
        assert int(manager.pid_file.read_text().strip()) == os.getpid()

    def test_remove_pid_deletes_file(self, manager: StateManager):
        manager.write_pid()
        manager.remove_pid()
        assert not manager.pid_file.exists()

    def test_get_pid_returns_int(self, manager: StateManager):
        manager.write_pid()
        assert manager.get_pid() == os.getpid()

    def test_get_pid_returns_none_when_missing(self, manager: StateManager):
        assert manager.get_pid() is None

    def test_get_pid_returns_none_on_corrupt(self, manager: StateManager):
        manager.pid_file.parent.mkdir(parents=True, exist_ok=True)
        manager.pid_file.write_text("not_a_number")
        assert manager.get_pid() is None


# ======================================================================
#  should_reindex
# ======================================================================


class TestShouldReindex:
    def test_unknown_file_should_reindex(self, manager: StateManager, tmp_path: Path):
        """A file that has never been indexed should return ``True``."""
        f = tmp_path / "new.py"
        f.write_text("print('hello')")
        assert manager.should_reindex(f) is True

    def test_unchanged_file_should_not_reindex(
        self, manager: StateManager, tmp_path: Path
    ):
        """A file whose mtime and checksum match the stored state should
        return ``False``."""
        f = tmp_path / "stable.py"
        f.write_text("x = 1")
        # Index it once
        manager.update_file_state(f, 1)
        # Should now consider it up-to-date
        assert manager.should_reindex(f) is False

    def test_changed_content_triggers_reindex(
        self, manager: StateManager, tmp_path: Path
    ):
        """If the file content changes (different checksum), it should
        reindex."""
        import time
        f = tmp_path / "changing.py"
        f.write_text("initial")
        # Ensure mtime has advanced before indexing
        time.sleep(0.02)
        manager.update_file_state(f, 1)
        # Ensure mtime advances again before modifying
        time.sleep(0.02)
        f.write_text("modified content")
        assert manager.should_reindex(f) is True

    def test_mtime_alone_does_not_trigger_reindex(
        self, manager: StateManager, tmp_path: Path
    ):
        """If only the mtime changes but the content stays the same,
        should NOT reindex (checksum match wins)."""
        f = tmp_path / "touched.py"
        f.write_text("same content")
        manager.update_file_state(f, 1)

        # Touch the file (update mtime without changing content)
        old_mtime = f.stat().st_mtime
        new_mtime = old_mtime + 60
        os.utime(f, (new_mtime, new_mtime))

        assert manager.should_reindex(f) is False


# ======================================================================
#  update_file_state
# ======================================================================


class TestUpdateFileState:
    def test_stores_correct_metadata(
        self, manager: StateManager, tmp_path: Path
    ):
        """After updating, the state should contain the correct metadata."""
        f = tmp_path / "foo.py"
        f.write_text("content")
        manager.update_file_state(f, 3)

        key = str(f.absolute())
        assert key in manager.state["indexed_files"]
        record = manager.state["indexed_files"][key]
        assert record["chunk_count"] == 3
        assert "checksum" in record
        assert "last_modified" in record
        assert "indexed_at" in record

    def test_multiple_files_tracked_independently(
        self, manager: StateManager, tmp_path: Path
    ):
        """Updates to different files should not interfere with each other."""
        a = tmp_path / "a.py"
        b = tmp_path / "b.py"
        a.write_text("aaa")
        b.write_text("bbb")

        manager.update_file_state(a, 1)
        manager.update_file_state(b, 2)

        assert (
            manager.state["indexed_files"][str(a.absolute())]["chunk_count"] == 1
        )
        assert (
            manager.state["indexed_files"][str(b.absolute())]["chunk_count"] == 2
        )

    def test_update_triggers_save(self, manager: StateManager, tmp_path: Path):
        """After an update, the state should eventually be persisted to
        disk (may be debounced)."""
        f = tmp_path / "save_test.py"
        f.write_text("content")

        # The update triggers a debounced save
        manager.update_file_state(f, 1)
        # Force flush so we can verify on-disk state
        manager.flush()

        assert manager.state_file.exists()
        with open(manager.state_file) as fh:
            loaded = yaml.safe_load(fh)
        assert str(f.absolute()) in loaded["indexed_files"]


# ======================================================================
#  Persistence / debounce
# ======================================================================


class TestSaveState:
    def test_debounce_skips_rapid_saves(self, manager: StateManager):
        """Multiple rapid saves within the debounce window should only
        write once to disk."""
        # Initial save
        manager.save_state(force=True)
        last_save = manager.last_save_time

        # Immediately call again (no force)
        manager.save_state(force=False)
        assert manager.last_save_time == last_save  # Should not have advanced

    def test_force_bypasses_debounce(self, manager: StateManager):
        manager.save_state(force=True)
        t1 = manager.last_save_time

        # A small delay to ensure time advances
        time.sleep(0.01)
        manager.save_state(force=True)
        assert manager.last_save_time > t1

    def test_flush_persists_to_disk(self, manager: StateManager, tmp_path: Path):
        """``flush()`` should force-save the state file to disk."""
        f = tmp_path / "flush_test.py"
        f.write_text("data")
        manager.update_file_state(f, 2)
        manager.flush()

        assert manager.state_file.exists()
        with open(manager.state_file) as fh:
            loaded = yaml.safe_load(fh)
        assert str(f.absolute()) in loaded["indexed_files"]


# ======================================================================
#  Thread safety (optional smoke test)
# ======================================================================


class TestThreadSafety:
    def test_concurrent_updates_dont_corrupt(
        self, manager: StateManager, tmp_path: Path
    ):
        """Multiple threads updating the state concurrently should not
        cause data loss."""
        import threading

        files = []
        for i in range(20):
            f = tmp_path / f"concurrent_{i}.py"
            f.write_text(f"content_{i}")
            files.append(f)

        def update(path: Path):
            manager.update_file_state(path, 1)

        threads = [threading.Thread(target=update, args=(f,)) for f in files]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        manager.flush()
        # All 20 files should be present
        assert len(manager.state["indexed_files"]) == 20
