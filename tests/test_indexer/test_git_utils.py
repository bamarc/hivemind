"""
Tests for :mod:`indexer.git_utils`.

The :class:`GitManager` wraps ``subprocess.run`` calls to git and
``pathspec``-based ``.gitignore`` matching.  All git subprocess calls are
mocked to avoid depending on a real git repository.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from indexer.git_utils import GitManager


# ======================================================================
#  Fixtures
# ======================================================================

@pytest.fixture
def mock_subprocess() -> MagicMock:
    """Patch ``subprocess.run`` so no real git commands are executed."""
    with patch("indexer.git_utils.subprocess.run") as mock:
        # By default, simulate "inside a git repo"
        mock.return_value = MagicMock(returncode=0, stdout="true", stderr="")
        yield mock


def make_manager(
    root: Path,
    mock_sub: MagicMock,
    git_repo: bool = True,
    has_gitignore: bool = False,
) -> GitManager:
    """Helper: create a :class:`GitManager` with controlled conditions."""
    if not git_repo:
        mock_sub.return_value = MagicMock(returncode=128, stdout="", stderr="fatal: not a git repository")

    if has_gitignore:
        (root / ".gitignore").write_text("*.log\n.env\n__pycache__/\n")

    return GitManager(root)


# ======================================================================
#  _check_is_git_repo
# ======================================================================

class TestCheckIsGitRepo:
    def test_inside_git_repo(self, tmp_path: Path, mock_subprocess: MagicMock):
        """When ``git rev-parse`` returns 0, ``is_git_repo`` should be True."""
        mgr = make_manager(tmp_path, mock_subprocess, git_repo=True)
        assert mgr.is_git_repo is True
        mock_subprocess.assert_any_call(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=tmp_path, capture_output=True, text=True, check=False
        )

    def test_outside_git_repo(self, tmp_path: Path, mock_subprocess: MagicMock):
        """When ``git rev-parse`` returns non-zero, ``is_git_repo`` should be False."""
        mgr = make_manager(tmp_path, mock_subprocess, git_repo=False)
        assert mgr.is_git_repo is False

    def test_git_not_installed(self, tmp_path: Path):
        """When ``FileNotFoundError`` is raised (git not installed), ``is_git_repo`` should be False."""
        with patch("indexer.git_utils.subprocess.run", side_effect=FileNotFoundError):
            mgr = GitManager(tmp_path)
        assert mgr.is_git_repo is False


# ======================================================================
#  _load_gitignore
# ======================================================================

class TestLoadGitignore:
    def test_loads_existing_gitignore(self, tmp_path: Path, mock_subprocess: MagicMock):
        """When ``.gitignore`` exists, it should be loaded and compiled into a ``PathSpec``."""
        mgr = make_manager(tmp_path, mock_subprocess, has_gitignore=True)
        assert mgr.spec is not None
        # A file matching the pattern should be ignored
        assert mgr.is_ignored(tmp_path / "test.log") is True
        assert mgr.is_ignored(tmp_path / "main.py") is False

    def test_missing_gitignore_returns_none(self, tmp_path: Path, mock_subprocess: MagicMock):
        """When no ``.gitignore`` exists, ``spec`` should be ``None``."""
        mgr = make_manager(tmp_path, mock_subprocess, has_gitignore=False)
        assert mgr.spec is None

    def test_corrupted_gitignore_logged(self, tmp_path: Path, mock_subprocess: MagicMock, caplog):
        """If loading the ``.gitignore`` raises, it should be logged and ``spec`` remains ``None``."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("")  # valid empty
        with patch.object(Path, "exists", return_value=True):
            # Force a read failure
            with patch("builtins.open", side_effect=PermissionError("no read")):
                mgr = make_manager(tmp_path, mock_subprocess, has_gitignore=False)
        assert mgr.spec is None


# ======================================================================
#  is_ignored
# ======================================================================

class TestIsIgnored:
    def test_matched_by_pattern(self, tmp_path: Path, mock_subprocess: MagicMock):
        """A file whose relative path matches a ``.gitignore`` pattern is ignored."""
        mgr = make_manager(tmp_path, mock_subprocess, has_gitignore=True)
        assert mgr.is_ignored(tmp_path / ".env") is True

    def test_not_ignored_when_no_spec(self, tmp_path: Path, mock_subprocess: MagicMock):
        """When ``spec`` is ``None`` (no ``.gitignore``), nothing is ignored."""
        mgr = make_manager(tmp_path, mock_subprocess, has_gitignore=False)
        assert mgr.is_ignored(tmp_path / "random.log") is False

    def test_outside_root_returns_false(self, tmp_path: Path, mock_subprocess: MagicMock):
        """A file that cannot be relativized to ``root_path`` should not be ignored."""
        mgr = make_manager(tmp_path, mock_subprocess, has_gitignore=True)
        outside = Path("/tmp/some_file.log")
        assert mgr.is_ignored(outside) is False


# ======================================================================
#  is_tracked
# ======================================================================

class TestIsTracked:
    def test_tracked_file(self, tmp_path: Path, mock_subprocess: MagicMock):
        """When ``git ls-files --error-unmatch`` returns 0, the file is tracked."""
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="", stderr="")
        mgr = make_manager(tmp_path, mock_subprocess)
        assert mgr.is_tracked(tmp_path / "main.py") is True

    def test_untracked_file(self, tmp_path: Path, mock_subprocess: MagicMock):
        """When ``git ls-files`` returns non-zero, the file is NOT tracked."""
        mgr = make_manager(tmp_path, mock_subprocess)  # init with default returncode=0 -> is_git_repo=True
        # Now change mock for the is_tracked call
        mock_subprocess.return_value = MagicMock(returncode=128, stdout="", stderr="fatal: ...")
        assert mgr.is_tracked(tmp_path / "new.py") is False

    def test_not_a_repo_assumes_tracked(self, tmp_path: Path, mock_subprocess: MagicMock):
        """If the manager is NOT in a git repo, ``is_tracked`` should return ``True``."""
        mgr = make_manager(tmp_path, mock_subprocess, git_repo=False)
        assert mgr.is_tracked(tmp_path / "any.py") is True

    def test_exception_returns_false(self, tmp_path: Path, mock_subprocess: MagicMock):
        """If ``subprocess.run`` raises an exception, ``is_tracked`` should return ``False``."""
        mgr = make_manager(tmp_path, mock_subprocess)  # init with default mock
        mock_subprocess.side_effect = PermissionError("no exec")
        assert mgr.is_tracked(tmp_path / "fails.py") is False


# ======================================================================
#  get_commit_metadata
# ======================================================================

class TestGetCommitMetadata:
    COMMIT_OUTPUT = (
        "abc123def\n"
        "John Doe\n"
        "john@example.com\n"
        "2025-06-15 10:30:00 +0000\n"
        "Fix critical bug in chunker\n"
    )

    def test_parses_metadata(self, tmp_path: Path, mock_subprocess: MagicMock):
        """When git log returns well-formed output, the metadata dict should be correctly parsed."""
        mock_subprocess.return_value = MagicMock(
            returncode=0, stdout=self.COMMIT_OUTPUT, stderr=""
        )
        mgr = make_manager(tmp_path, mock_subprocess)
        meta = mgr.get_commit_metadata(tmp_path / "file.py")
        assert meta["commit_hash"] == "abc123def"
        assert meta["commit_author"] == "John Doe"
        assert meta["commit_email"] == "john@example.com"
        assert meta["commit_date"] == "2025-06-15 10:30:00 +0000"
        assert meta["commit_subject"] == "Fix critical bug in chunker"

    def test_not_a_git_repo(self, tmp_path: Path, mock_subprocess: MagicMock):
        """Outside a git repo, ``get_commit_metadata`` should return an empty dict."""
        mgr = make_manager(tmp_path, mock_subprocess, git_repo=False)
        assert mgr.get_commit_metadata(tmp_path / "file.py") == {}

    def test_no_commits_returns_empty(self, tmp_path: Path, mock_subprocess: MagicMock):
        """When git log returns empty stdout, the result should be an empty dict."""
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="", stderr="")
        mgr = make_manager(tmp_path, mock_subprocess)
        assert mgr.get_commit_metadata(tmp_path / "new.py") == {}

    def test_incomplete_output_returns_empty(self, tmp_path: Path, mock_subprocess: MagicMock):
        """If git log returns fewer than 5 lines, fall back to empty dict."""
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="only_hash\n", stderr="")
        mgr = make_manager(tmp_path, mock_subprocess)
        assert mgr.get_commit_metadata(tmp_path / "file.py") == {}

    def test_exception_returns_empty(self, tmp_path: Path, mock_subprocess: MagicMock, caplog):
        """If ``subprocess.run`` raises, log the error and return empty dict."""
        mgr = make_manager(tmp_path, mock_subprocess)  # init with default mock
        mock_subprocess.side_effect = RuntimeError("git crashed")
        import logging
        with caplog.at_level(logging.ERROR):
            meta = mgr.get_commit_metadata(tmp_path / "file.py")
        assert meta == {}
        assert "Failed to get git metadata" in caplog.text
