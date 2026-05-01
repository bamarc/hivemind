"""
Tests for :mod:`core.filesystem` — shared filesystem traversal utilities.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from core.filesystem import get_file_tree, file_contents, EXCLUDED_DIRS, _is_excluded


class TestExcludedDirs:
    """The shared exclusion set must contain common tool directories."""

    def test_excluded_dirs_contains_common_dirs(self):
        assert ".git" in EXCLUDED_DIRS
        assert ".venv" in EXCLUDED_DIRS
        assert "node_modules" in EXCLUDED_DIRS
        assert "__pycache__" in EXCLUDED_DIRS
        assert "build" in EXCLUDED_DIRS

    def test_is_excluded_rejects_dot_dirs(self):
        assert _is_excluded(".git") is True
        assert _is_excluded(".venv") is True

    def test_is_excluded_allows_normal_dirs(self):
        assert _is_excluded("src") is False
        assert _is_excluded("tests") is False
        assert _is_excluded("docs") is False


class TestGetFileTree:
    def test_basic_tree(self, tmp_path: Path):
        """A simple directory tree should produce expected output."""
        (tmp_path / "README.md").write_text("# Readme")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("pass")

        tree = get_file_tree(str(tmp_path), depth=3)

        assert f"# File Tree for {tmp_path.name}" in tree
        assert "README.md" in tree
        assert "src/" in tree
        assert "main.py" in tree

    def test_excludes_git_and_venv(self, tmp_path: Path):
        """Excluded directories should not appear in the tree."""
        (tmp_path / ".git").mkdir()
        (tmp_path / ".venv").mkdir()
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("pass")

        tree = get_file_tree(str(tmp_path), depth=3)

        assert ".git" not in tree
        assert ".venv" not in tree
        assert "src/" in tree
        assert "main.py" in tree

    def test_nonexistent_path_returns_error(self):
        result = get_file_tree("/nonexistent/path/xyz")
        assert result.startswith("Error:")
        assert "does not exist" in result

    def test_file_path_returns_error(self, tmp_path: Path):
        """Passing a file (not a directory) should return an error."""
        f = tmp_path / "file.txt"
        f.write_text("hello")
        result = get_file_tree(str(f))
        assert result.startswith("Error:")
        assert "not a directory" in result

    def test_respects_depth(self, tmp_path: Path):
        """Depth should limit how deep the tree goes."""
        # Create a deep structure: a/b/c/d/e
        current = tmp_path
        for name in ("a", "b", "c", "d", "e"):
            current = current / name
            current.mkdir()
            (current / "file.txt").write_text("x")

        tree_shallow = get_file_tree(str(tmp_path), depth=1)
        tree_deep = get_file_tree(str(tmp_path), depth=5)

        # Shallow: should see "a/" but not deeper
        assert "a/" in tree_shallow
        # Deep: should see multiple levels
        assert tree_deep.count("├──") > tree_shallow.count("├──") or \
               tree_deep.count("└──") > tree_shallow.count("└──")

    def test_empty_directory(self, tmp_path: Path):
        """An empty directory should produce a minimal tree."""
        tree = get_file_tree(str(tmp_path), depth=2)
        assert f"# File Tree for {tmp_path.name}" in tree
        # Only the header line, no entries
        lines = tree.strip().split("\n")
        assert len(lines) == 1  # just the header


class TestFileContents:
    def test_reads_text_file(self, tmp_path: Path):
        f = tmp_path / "hello.txt"
        f.write_text("Hello, world!")
        assert file_contents(str(f)) == "Hello, world!"

    def test_returns_none_for_missing_file(self):
        assert file_contents("/nonexistent/file.txt") is None

    def test_handles_binary_file(self, tmp_path: Path):
        """Binary content should be readable via errors='replace'."""
        f = tmp_path / "binary.bin"
        f.write_bytes(b"\x00\x01\x02\xff\xfe")
        result = file_contents(str(f))
        # Should not return None — it reads with errors='replace'
        assert result is not None

    def test_reads_empty_file(self, tmp_path: Path):
        f = tmp_path / "empty.txt"
        f.write_text("")
        assert file_contents(str(f)) == ""
