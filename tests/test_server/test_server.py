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
    answer_code_question,
    deep_research,
    generate_blueprint,
    get_file_tree,
    get_git_history,
    get_index_status,
    read_file,
    run_verification,
    scout_urls,
    search_web,
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

    # ================================================================
    #  Mode tests (dense / sparse / hybrid)
    # ================================================================

    def test_dense_mode_default(self, mock_qdrant: MagicMock):
        """Default mode='auto' should use pure dense vector search."""
        mock_qdrant.query_points.return_value = MagicMock(
            points=[MagicMock(id=0, score=0.9, payload={"filepath": "f.py", "content": "c", "language": "py"})]
        )
        result = semantic_code_search("test", mode="auto")
        assert "f.py" in result
        call_kwargs = mock_qdrant.query_points.call_args.kwargs
        # Dense mode: query is a vector (list), no prefetch or fusion
        assert "query" in call_kwargs and isinstance(call_kwargs["query"], list)
        assert "prefetch" not in call_kwargs
        assert "query_filter" in call_kwargs

    def test_dense_mode_explicit(self, mock_qdrant: MagicMock):
        """Explicit mode='dense' should behave the same as 'auto'."""
        mock_qdrant.query_points.return_value = MagicMock(
            points=[MagicMock(id=0, score=0.9, payload={"filepath": "f.py", "content": "c", "language": "py"})]
        )
        result = semantic_code_search("test", mode="dense")
        assert "f.py" in result
        call_kwargs = mock_qdrant.query_points.call_args.kwargs
        assert "query" in call_kwargs and isinstance(call_kwargs["query"], list)
        assert "prefetch" not in call_kwargs

    def test_sparse_mode(self, mock_qdrant: MagicMock):
        """mode='sparse' should use ``using='code-sparse'`` with a SparseVector query."""
        mock_qdrant.query_points.return_value = MagicMock(
            points=[MagicMock(id=0, score=0.8, payload={"filepath": "f.py", "content": "c", "language": "py"})]
        )
        result = semantic_code_search("hello world", mode="sparse")
        assert "f.py" in result
        call_kwargs = mock_qdrant.query_points.call_args.kwargs
        # Sparse mode: query is a SparseVector, using="code-sparse"
        assert call_kwargs.get("using") == "code-sparse"
        query = call_kwargs.get("query")
        assert hasattr(query, "indices")
        assert hasattr(query, "values")
        assert "prefetch" not in call_kwargs

    def test_hybrid_mode(self, mock_qdrant: MagicMock):
        """mode='hybrid' should use prefetch with dense + sparse + FusionQuery."""
        mock_qdrant.query_points.return_value = MagicMock(
            points=[MagicMock(id=0, score=0.85, payload={"filepath": "f.py", "content": "c", "language": "py"})]
        )
        result = semantic_code_search("hello world", mode="hybrid")
        assert "f.py" in result
        call_kwargs = mock_qdrant.query_points.call_args.kwargs
        # Hybrid mode: has prefetch and FusionQuery
        assert "prefetch" in call_kwargs
        assert len(call_kwargs["prefetch"]) == 2
        assert "fusion" in str(call_kwargs.get("query", "")) or "FusionQuery" in str(type(call_kwargs.get("query")))


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


class TestSearchWeb:
    """Tests for the ``search_web`` MCP tool."""

    @pytest.fixture(autouse=True)
    def _mock_core_search(self):
        """Mock ``core_search_web`` so we don't hit the network."""
        with patch("server.server.core_search_web") as mock_fn:
            mock_fn.return_value = [
                MagicMock(
                    title="Python Docs",
                    url="https://docs.python.org/3/",
                    snippet="Official Python documentation.",
                ),
                MagicMock(
                    title="Real Python",
                    url="https://realpython.com/",
                    snippet="Python tutorials.",
                ),
            ]
            yield mock_fn

    def test_returns_formatted_results(self):
        """A successful search should return markdown-formatted results."""
        result = search_web("python")
        assert "# Web Search Results" in result
        assert "Python Docs" in result
        assert "https://docs.python.org/3/" in result
        assert "Official Python documentation" in result
        assert "Real Python" in result

    def test_no_results(self):
        """When the backend returns nothing, show a message."""
        with patch("server.server.core_search_web", return_value=[]):
            result = search_web("xyznothing")
        assert "No web results found" in result

    def test_import_error_handled(self):
        """When ddgs is missing, show a helpful message."""
        with patch(
            "server.server.core_search_web",
            side_effect=ImportError("ddgs not installed"),
        ):
            result = search_web("test")
        assert "Error" in result
        assert "ddgs" in result

    def test_categories_passed_to_core(self):
        """The ``categories`` parameter should be passed to core_search_web."""
        with patch("server.server.core_search_web") as mock_fn:
            mock_fn.return_value = [MagicMock(title="T", url="https://x.com", snippet="S")]
            search_web("python", categories=["it", "science"])
        call_kwargs = mock_fn.call_args.kwargs
        assert call_kwargs.get("categories") == ["it", "science"]

    def test_categories_none_by_default(self):
        """When ``categories`` is not provided, it should be None."""
        with patch("server.server.core_search_web") as mock_fn:
            mock_fn.return_value = [MagicMock(title="T", url="https://x.com", snippet="S")]
            search_web("python")
        call_kwargs = mock_fn.call_args.kwargs
        assert call_kwargs.get("categories") is None


class TestScoutUrls:
    """Tests for the ``scout_urls`` MCP tool."""

    # A markdown document with multiple header sections for chunking tests.
    _MULTI_SECTION_MD = (
        "# Project Overview\n\n"
        "Welcome to the project.\n\n"
        "## Installation\n\n"
        "Run `pip install foo`.\n\n"
        "## Configuration\n\n"
        "Set the API key.\n\n"
        "## Usage\n\n"
        "Run `foo --help`.\n"
    )

    @pytest.fixture(autouse=True)
    def _mock_scout_crawler(self):
        """Mock ScoutCrawler to avoid real HTTP calls.
        
        ScoutCrawler is imported lazily inside scout_urls(), so we patch
        the class at its definition site: ``scout.crawler.ScoutCrawler``.
        """
        with patch("scout.crawler.ScoutCrawler") as mock_cls:
            mock_crawler = MagicMock()

            async def fake_crawl_batch(urls, **_kw):
                for u in urls:
                    yield u, self._MULTI_SECTION_MD

            mock_crawler.crawl_batch = fake_crawl_batch
            mock_cls.return_value = mock_crawler
            yield mock_crawler

    async def test_crawls_single_url(self):
        """A single URL should be crawled and returned."""
        result = await scout_urls(["https://example.com"])
        assert "Scouted Pages" in result
        assert "https://example.com" in result
        assert "Project Overview" in result

    async def test_crawls_multiple_urls(self):
        """Multiple URLs should be crawled in a single call."""
        result = await scout_urls(["https://a.com", "https://b.com"])
        assert "https://a.com" in result
        assert "https://b.com" in result

    async def test_max_results_limit(self):
        """max_results should cap the number of URLs processed."""
        urls = [f"https://example.com/{i}" for i in range(20)]
        result = await scout_urls(urls, max_results=2)
        # Should only have 2 URLs worth of content, not 20
        assert result.count("Source:") == 2

    async def test_empty_urls_error(self):
        """An empty URL list should return an error."""
        result = await scout_urls([])
        assert "Error" in result
        assert "No URLs" in result

    async def test_import_error_handled(self):
        """When scout deps are missing, show a helpful message."""
        with patch(
            "scout.crawler.ScoutCrawler",
            side_effect=ImportError("No module named crawl4ai"),
        ):
            result = await scout_urls(["https://example.com"])
        assert "Error" in result
        assert "crawl4ai" in result

    # ================================================================
    #  TOC mode
    # ================================================================

    async def test_toc_mode_returns_table_of_contents(self):
        """``mode='toc'`` should return a Table of Contents with sections."""
        result = await scout_urls(["https://example.com"], mode="toc")
        assert "Table of Contents" in result
        assert "Project Overview" in result
        assert "Installation" in result
        assert "Configuration" in result
        assert "Usage" in result
        # Should NOT include raw markdown content like "pip install"
        assert "pip install" not in result

    async def test_toc_mode_includes_token_estimates(self):
        """TOC should show estimated token counts per section."""
        result = await scout_urls(["https://example.com"], mode="toc")
        assert "~" in result  # token estimate marker
        assert "tokens" in result.lower()

    async def test_toc_mode_includes_section_instructions(self):
        """TOC should tell the agent how to use sections mode."""
        result = await scout_urls(["https://example.com"], mode="toc")
        assert "mode='sections'" in result

    # ================================================================
    #  Sections mode
    # ================================================================

    async def test_sections_mode_by_name(self):
        """``mode='sections'`` should return content for matching sections."""
        result = await scout_urls(
            ["https://example.com"],
            mode="sections",
            sections={"https://example.com": ["Installation"]},
        )
        assert "Selected Sections" in result
        assert "pip install" in result  # content from Installation chunk
        # Should NOT include other sections
        assert "API key" not in result

    async def test_sections_mode_by_index(self):
        """Sections can be referenced by numeric index from the TOC."""
        result = await scout_urls(
            ["https://example.com"],
            mode="sections",
            sections={"https://example.com": ["2"]},
        )
        assert "Configuration" in result or "API key" in result

    async def test_sections_mode_multiple(self):
        """Multiple section names can be requested at once."""
        result = await scout_urls(
            ["https://example.com"],
            mode="sections",
            sections={"https://example.com": ["Installation", "Usage"]},
        )
        assert "pip install" in result
        assert "foo --help" in result

    async def test_sections_mode_case_insensitive(self):
        """Section matching should be case-insensitive."""
        result = await scout_urls(
            ["https://example.com"],
            mode="sections",
            sections={"https://example.com": ["installation"]},
        )
        assert "pip install" in result

    async def test_sections_mode_no_match(self):
        """Unmatched sections should show available options."""
        result = await scout_urls(
            ["https://example.com"],
            mode="sections",
            sections={"https://example.com": ["NonExistent"]},
        )
        assert "No sections matched" in result
        # Should list available sections
        assert "Installation" in result

    async def test_sections_mode_empty_list(self):
        """Empty sections list should return a message."""
        result = await scout_urls(
            ["https://example.com"],
            mode="sections",
            sections={"https://example.com": []},
        )
        assert "No sections requested" in result

    async def test_sections_mode_per_url_different_sections(self):
        """Different URLs can request different sections."""
        result = await scout_urls(
            ["https://a.com", "https://b.com"],
            mode="sections",
            sections={
                "https://a.com": ["Installation"],
                "https://b.com": ["Usage"],
            },
        )
        assert "Installation" in result or "pip install" in result
        # Each URL's sections should be in the output
        assert "https://a.com" in result
        assert "https://b.com" in result

    async def test_sections_mode_url_not_in_dict(self):
        """URLs not in the sections dict get empty list (no sections)."""
        result = await scout_urls(
            ["https://example.com"],
            mode="sections",
            sections={},  # URL not in dict
        )
        assert "No sections requested" in result

    async def test_sections_mode_backward_compat_none(self):
        """Passing sections=None should still work (no sections for any URL)."""
        result = await scout_urls(
            ["https://example.com"],
            mode="sections",
            sections=None,
        )
        assert "No sections requested" in result

    # ================================================================
    #  Full mode (backward compat)
    # ================================================================

    async def test_full_mode_default(self):
        """Default mode='full' should return raw markdown content."""
        result = await scout_urls(["https://example.com"])
        assert "Scouted Pages" in result
        assert "pip install" in result  # raw content present
        assert "foo --help" in result

    async def test_full_mode_explicit(self):
        """Explicit ``mode='full'`` should behave the same as default."""
        result = await scout_urls(["https://example.com"], mode="full")
        assert "Scouted Pages" in result
        assert "pip install" in result


class TestDeepResearch:
    """Tests for the ``deep_research`` MCP tool."""

    _MULTI_SECTION_MD = (
        "# Project Overview\n\n"
        "Welcome to the project.\n\n"
        "## Installation\n\n"
        "Run `pip install foo`.\n\n"
    )

    @pytest.fixture(autouse=True)
    def _mock_dependencies(self):
        """Mock both search_web and ScoutCrawler."""
        with patch("server.server.core_search_web") as mock_search, \
             patch("scout.crawler.ScoutCrawler") as mock_crawler_cls:

            mock_search.return_value = [
                MagicMock(
                    title="Python Docs",
                    url="https://docs.python.org/3/",
                    snippet="Official Python documentation.",
                ),
                MagicMock(
                    title="Real Python",
                    url="https://realpython.com/",
                    snippet="Python tutorials.",
                ),
            ]

            mock_crawler = MagicMock()
            async def fake_crawl_batch(urls, **_kw):
                for u in urls:
                    yield u, self._MULTI_SECTION_MD
            mock_crawler.crawl_batch = fake_crawl_batch
            mock_crawler_cls.return_value = mock_crawler
            yield

    async def test_searches_and_crawls(self):
        """deep_research should search, crawl, and return combined results."""
        result = await deep_research("python docs")
        assert "Deep Research" in result
        assert "Search Results" in result
        assert "Python Docs" in result
        assert "Crawled Content" in result
        assert "Project Overview" in result

    async def test_no_search_results(self):
        """When search returns nothing, show a message."""
        with patch("server.server.core_search_web", return_value=[]):
            result = await deep_research("xyznothing")
        assert "No web results found" in result

    async def test_empty_urls_in_results(self):
        """Results without URLs should be skipped gracefully."""
        with patch("server.server.core_search_web") as mock_search:
            mock_search.return_value = [
                MagicMock(title="No URL", url="", snippet="No link."),
            ]
            result = await deep_research("test")
        assert "No valid URLs" in result

    async def test_search_import_error(self):
        """When ddgs is missing, show helpful message."""
        with patch("server.server.core_search_web",
                   side_effect=ImportError("ddgs not installed")):
            result = await deep_research("test")
        assert "Error" in result
        assert "ddgs" in result

    async def test_scout_import_error(self):
        """When crawl4ai is missing, show helpful message."""
        with patch("scout.crawler.ScoutCrawler",
                   side_effect=ImportError("No module named crawl4ai")):
            result = await deep_research("test")
        assert "Error" in result
        assert "crawl4ai" in result

    async def test_categories_passed_to_core(self):
        """The ``categories`` parameter should be forwarded to core_search_web."""
        with patch("server.server.core_search_web") as mock_search, \
             patch("scout.crawler.ScoutCrawler") as mock_crawler_cls:
            mock_search.return_value = [
                MagicMock(title="T", url="https://x.com", snippet="S"),
            ]
            mock_crawler = MagicMock()
            async def fake_crawl(urls, **_kw):
                for u in urls:
                    yield u, "# Doc\nContent."
            mock_crawler.crawl_batch = fake_crawl
            mock_crawler_cls.return_value = mock_crawler

            await deep_research("test", categories=["news"])
        call_kwargs = mock_search.call_args.kwargs
        assert call_kwargs.get("categories") == ["news"]


    async def test_max_results_clamps_urls(self):
        """max_results should limit how many search results are considered."""
        with patch("server.server.core_search_web") as mock_search:
            mock_search.return_value = [
                MagicMock(title=f"Result {i}", url=f"https://example.com/{i}", snippet="")
                for i in range(5)
            ]
            result = await deep_research("test", max_results=3, max_urls=2)
        assert result.count("Source:") == 2


class TestReadFile:
    """Tests for the ``read_file`` MCP tool."""

    def test_reads_file_contents(self, tmp_path: Path):
        """A valid file should be read and returned with line numbers."""
        f = tmp_path / "test.py"
        f.write_text("line 1\nline 2\nline 3\n")
        with patch("server.server.settings") as mock_settings:
            mock_settings.workspace_path = tmp_path
            result = read_file(str(f))
        assert "test.py" in result
        assert "line 1" in result
        assert "line 2" in result
        assert "line 3" in result

    def test_start_line_offset(self, tmp_path: Path):
        """start_line should skip lines."""
        f = tmp_path / "test.py"
        f.write_text("a\nb\nc\nd\ne\n")
        with patch("server.server.settings") as mock_settings:
            mock_settings.workspace_path = tmp_path
            result = read_file(str(f), start_line=3)
        assert "a" not in result.split("|")[1] if "|" in result else True
        # At minimum, line 1 and 2 should not be the first numbered line
        assert "     3 | c" in result

    def test_max_lines_truncation(self, tmp_path: Path):
        """max_lines should limit output."""
        lines = [f"line {i}" for i in range(100)]
        f = tmp_path / "big.py"
        f.write_text("\n".join(lines))
        with patch("server.server.settings") as mock_settings:
            mock_settings.workspace_path = tmp_path
            result = read_file(str(f), max_lines=10)
        # Should have exactly 10 numbered lines
        numbered_lines = [l for l in result.split("\n") if l.strip().startswith(tuple("0123456789"))]
        assert len(numbered_lines) == 10

    def test_nonexistent_file(self):
        """A non-existent file should return an error."""
        result = read_file("/does/not/exist.txt")
        assert "Error" in result

    def test_excluded_directory(self, tmp_path: Path):
        """Files in excluded directories should be rejected."""
        excluded = tmp_path / ".git" / "config"
        excluded.parent.mkdir()
        excluded.write_text("secret")
        with patch("server.server.settings") as mock_settings:
            mock_settings.workspace_path = tmp_path
            result = read_file(str(excluded))
        assert "Error" in result
        assert "excluded" in result.lower()


class TestGetGitHistory:
    """Tests for the ``get_git_history`` MCP tool."""

    def test_not_a_git_repo(self, tmp_path: Path):
        """A non-git directory should return a clear message."""
        f = tmp_path / "test.py"
        f.write_text("code")
        with patch("server.server.settings") as mock_settings:
            mock_settings.workspace_path = tmp_path
            result = get_git_history(str(f))
        assert "Not a git repository" in result

    def test_file_not_found(self):
        """A non-existent file should return an error."""
        with patch("server.server.settings") as mock_settings:
            mock_settings.workspace_path = Path("/tmp")
            result = get_git_history("/nonexistent/file.py")
        assert "Error" in result
        assert "not found" in result.lower()

    def test_returns_git_metadata(self, tmp_path: Path):
        """When git metadata is available, it should be formatted.
        
        GitManager is imported lazily inside get_git_history(), so we
        patch the class at its definition site: ``indexer.git_utils.GitManager``.
        """
        f = tmp_path / "test.py"
        f.write_text("code")
        with patch("indexer.git_utils.GitManager") as mock_gm_cls:
            mock_gm = MagicMock()
            mock_gm.is_git_repo = True
            mock_gm.get_commit_metadata.return_value = {
                "commit_hash": "abc123def456",
                "commit_author": "Alice",
                "commit_email": "alice@example.com",
                "commit_date": "2025-01-15",
                "commit_subject": "Initial commit",
            }
            mock_gm_cls.return_value = mock_gm

            with patch("server.server.settings") as mock_settings:
                mock_settings.workspace_path = tmp_path
                result = get_git_history(str(f))

        assert "Git History" in result
        assert "abc123def456" in result
        assert "Alice" in result
        assert "alice@example.com" in result
        assert "2025-01-15" in result
        assert "Initial commit" in result

    def test_no_metadata_for_untracked(self, tmp_path: Path):
        """Untracked files should return a message."""
        f = tmp_path / "new.py"
        f.write_text("new")
        with patch("indexer.git_utils.GitManager") as mock_gm_cls:
            mock_gm = MagicMock()
            mock_gm.is_git_repo = True
            mock_gm.get_commit_metadata.return_value = {}
            mock_gm_cls.return_value = mock_gm

            with patch("server.server.settings") as mock_settings:
                mock_settings.workspace_path = tmp_path
                result = get_git_history(str(f))

        assert "No git history found" in result


class TestAnswerCodeQuestion:
    """Tests for the ``answer_code_question`` MCP tool."""

    @pytest.fixture(autouse=True)
    def _setup_search_results(self, mock_qdrant: MagicMock):
        """Set up Qdrant to return one code chunk hit by default."""
        mock_qdrant.query_points.return_value = MagicMock(
            points=[
                MagicMock(
                    id=0,
                    score=0.95,
                    payload={
                        "filepath": "/proj/auth.py",
                        "content": "def authenticate(user, pwd): ...",
                        "language": "python",
                        "line_start": 10,
                        "line_end": 25,
                    },
                )
            ]
        )
        yield

    @staticmethod
    def _make_chat_response(text: str) -> MagicMock:
        """Build a mock chat completion that returns *text* as the answer."""
        choice = MagicMock()
        choice.message.content = text
        completion = MagicMock()
        completion.choices = [choice]
        return completion

    def test_returns_answer_with_sources(
        self, mock_qdrant: MagicMock, mock_chat_client: MagicMock
    ):
        """A successful query should return ``## Answer`` and ``## Sources`` sections."""
        mock_chat_client.chat.completions.create = MagicMock(
            return_value=self._make_chat_response(
                "Authentication is handled in auth.py."
            )
        )
        result = answer_code_question("How does auth work?")
        assert "## Answer" in result
        assert "## Sources" in result
        assert "Authentication is handled in auth.py." in result
        assert "auth.py" in result
        assert "0.95" in result

    def test_no_results_message(self, mock_qdrant: MagicMock):
        """When Qdrant returns no results, return a helpful message."""
        mock_qdrant.query_points.return_value = MagicMock(points=[])
        result = answer_code_question("How does auth work?")
        assert "couldn't find any relevant code" in result
        assert "start_indexing" in result

    def test_context_injected_into_system_prompt(
        self, mock_qdrant: MagicMock, mock_chat_client: MagicMock
    ):
        """The optional ``context`` parameter should appear in the system prompt."""
        mock_create = MagicMock(
            return_value=self._make_chat_response("Answer.")
        )
        mock_chat_client.chat.completions.create = mock_create
        answer_code_question(
            "How does auth work?",
            context="I'm adding OAuth support.",
        )
        call_args = mock_create.call_args
        messages = call_args.kwargs["messages"]
        system_msg = messages[0]["content"]
        assert "OAuth support" in system_msg
        assert "Answer the user's question based ONLY" in system_msg

    def test_user_prompt_contains_question_and_chunks(
        self, mock_qdrant: MagicMock, mock_chat_client: MagicMock
    ):
        """The user prompt should include the question and formatted code chunks."""
        mock_create = MagicMock(
            return_value=self._make_chat_response("Answer.")
        )
        mock_chat_client.chat.completions.create = mock_create
        answer_code_question("How does auth work?")
        call_args = mock_create.call_args
        messages = call_args.kwargs["messages"]
        user_msg = messages[1]["content"]
        assert "How does auth work?" in user_msg
        assert "auth.py" in user_msg
        assert "def authenticate" in user_msg

    def test_citations_include_filepath_and_score(
        self, mock_qdrant: MagicMock, mock_chat_client: MagicMock
    ):
        """Citations should contain filepath with line numbers and score."""
        mock_chat_client.chat.completions.create.return_value = (
            self._make_chat_response("Answer.")
        )
        result = answer_code_question("How does auth work?")
        assert "/proj/auth.py" in result
        assert "0.95" in result
        assert "lines 10-25" in result

    def test_temperature_is_low(
        self, mock_qdrant: MagicMock, mock_chat_client: MagicMock
    ):
        """The chat completion should use a low temperature for deterministic answers."""
        mock_create = MagicMock(
            return_value=self._make_chat_response("Answer.")
        )
        mock_chat_client.chat.completions.create = mock_create
        answer_code_question("How does auth work?")
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs.get("temperature") == 0.3

    def test_error_handling(self, mock_qdrant: MagicMock):
        """An exception should be caught and returned as a string, not propagated."""
        mock_qdrant.query_points.side_effect = RuntimeError("Qdrant down")
        result = answer_code_question("test")
        assert "Error answering question" in result
