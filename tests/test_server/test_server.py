"""
Tests for :mod:`server.server` — the MCP tool definitions.

All external clients (Qdrant, Embedder, Chat) are mocked by the global
``conftest.py`` so no real infrastructure is needed.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# The MCP tools are plain functions decorated with ``@mcp.tool()``.
# We import them directly and call them like normal functions.
from server.server import (
    analyze_code_complexity,
    generate_blueprint,
    get_file_tree,
    get_index_status,
    run_verification,
    semantic_code_search,
    start_indexing,
)


class TestSemanticCodeSearch:
    def test_returns_results(self, mock_qdrant: MagicMock):
        """A successful query should return formatted markdown with results."""
        mock_qdrant.query_points.return_value = MagicMock(
            points=[
                MagicMock(
                    id=0,
                    score=0.95,
                    payload={
                        "filepath": "/proj/mod.py",
                        "content": "def foo(): pass",
                        "language": "python",
                    },
                )
            ]
        )
        result = semantic_code_search("find foo")
        assert "mod.py" in result
        assert "0.95" in result
        assert "python" in result.lower()

    def test_no_results(self, mock_qdrant: MagicMock):
        """When Qdrant returns no points, the tool should say so."""
        mock_qdrant.query_points.return_value = MagicMock(points=[])
        result = semantic_code_search("nothing")
        assert "No relevant code found" in result

    def test_filters_applied(self, mock_qdrant: MagicMock):
        """Filters (file_filter, language, is_test) should be passed to Qdrant."""
        mock_qdrant.query_points.return_value = MagicMock(points=[])
        semantic_code_search("query", file_filter="server/", language="python", is_test=False)
        call_kwargs = mock_qdrant.query_points.call_args.kwargs
        assert call_kwargs.get("query_filter") is not None

    def test_error_handling(self, mock_qdrant: MagicMock):
        """An exception should be caught and returned as a string, not propagated."""
        mock_qdrant.query_points.side_effect = RuntimeError("Qdrant down")
        result = semantic_code_search("test")
        assert "Error executing semantic search" in result


class TestGetFileTree:
    def test_valid_path(self, tmp_path: Path):
        """A real directory should produce a tree."""
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "file.py").touch()
        result = get_file_tree(root_path=str(tmp_path), depth=3)
        assert tmp_path.name in result
        assert "sub" in result
        assert "file.py" in result

    def test_invalid_path(self):
        """A non-existent path should return an error."""
        result = get_file_tree(root_path="/nonexistent/path")
        assert "Error" in result
        assert "not exist" in result.lower()

    def test_depth_control(self, tmp_path: Path):
        """Deeply nested directories beyond ``depth`` should be omitted."""
        deep = tmp_path / "a" / "b" / "c" / "d"
        deep.mkdir(parents=True)
        shallow = get_file_tree(root_path=str(tmp_path), depth=1)
        assert "b" not in shallow
        deep_tree = get_file_tree(root_path=str(tmp_path), depth=4)
        assert "d" in deep_tree


class TestGetIndexStatus:
    def test_indexed(self, mock_qdrant: MagicMock):
        """When a metadata point with ``indexing_complete`` exists, show status."""
        mock_qdrant.retrieve.return_value = [
            MagicMock(
                payload={
                    "indexing_complete": True,
                    "last_indexed_at": "2025-01-01T00:00:00",
                }
            )
        ]
        result = get_index_status()
        assert "Complete" in result
        assert "2025-01-01" in result

    def test_not_indexed(self, mock_qdrant: MagicMock):
        """When no metadata point exists, report 'Not Indexed'."""
        mock_qdrant.retrieve.return_value = []
        result = get_index_status()
        assert "Not Indexed" in result


class TestStartIndexing:
    @patch("subprocess.Popen")
    def test_triggers_subprocess(self, mock_popen: MagicMock, tmp_path: Path):
        """``start_indexing`` should launch ``hivemind indexer start --detach``."""
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_popen.return_value = mock_proc
        # Create a minimal directory so the existence check passes
        result = start_indexing(root_path=str(tmp_path))
        assert "Indexing started" in result
        assert "12345" in result
        mock_popen.assert_called_once()

    def test_nonexistent_path(self):
        """A non-existent path should return an error."""
        result = start_indexing(root_path="/does/not/exist")
        assert "Error" in result


class TestAnalyzeCodeComplexity:
    def test_valid_file(self, sample_python_file: Path):
        """A real Python file should produce a complexity report."""
        result = analyze_code_complexity(str(sample_python_file))
        assert "Score" in result
        assert "greet" in result or "Complexity" in result

    def test_nonexistent_file(self):
        """A non-existent file should return an error."""
        result = analyze_code_complexity("/no/file.py")
        assert "Error" in result


class TestGenerateBlueprint:
    def test_returns_json(self):
        """The blueprint should be returned as a JSON string."""
        result = generate_blueprint("add logging", "context here")
        assert "blueprint" in result or "file" in result
        assert result.startswith("{") or result.startswith("[")


class TestRunVerification:
    @patch("subprocess.run")
    def test_pytest_passed(self, mock_run: MagicMock, tmp_path: Path):
        """A passing pytest run should return PASSED status."""
        # Create pyproject.toml so the tool detects a Python project
        (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\n")
        mock_run.return_value = MagicMock(returncode=0, stdout="all ok", stderr="")
        with patch("server.server.settings") as mock_settings:
            mock_settings.workspace_path = tmp_path
            result = run_verification()
        assert "PASSED" in result
        assert "all ok" in result

    @patch("subprocess.run")
    def test_pytest_failed(self, mock_run: MagicMock, tmp_path: Path):
        """A failing pytest run should return FAILED status."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\n")
        mock_run.return_value = MagicMock(returncode=1, stdout="FAILURES", stderr="")
        with patch("server.server.settings") as mock_settings:
            mock_settings.workspace_path = tmp_path
            result = run_verification()
        assert "FAILED" in result

    @patch("subprocess.run")
    def test_timeout_handled(self, mock_run: MagicMock, tmp_path: Path):
        """A subprocess timeout should be reported gracefully."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\n")
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["pytest"], timeout=60)
        with patch("server.server.settings") as mock_settings:
            mock_settings.workspace_path = tmp_path
            result = run_verification()
        assert "timed out" in result.lower()

    def test_no_project_file(self, tmp_path: Path):
        """When no package.json or pyproject.toml exists, show an error."""
        with patch("server.server.settings") as mock_settings:
            mock_settings.workspace_path = tmp_path
            result = run_verification()
        assert "Error" in result or "Could not detect" in result
