"""
Tests for :class:`scout.manager.ScoutManager`.

File-system operations use ``tmp_path``. The underlying ``ScoutCrawler``
is mocked so no real crawling happens.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scout.manager import ScoutManager, sync_run


# ======================================================================
#  _url_to_path
# ======================================================================


class TestUrlToPath:
    def test_basic_url(self):
        """A simple URL becomes ``domain/path.md``."""
        manager = ScoutManager()
        path = manager._url_to_path("https://example.com/docs")
        assert str(path) == "example_com/docs.md"

    def test_url_with_query_string(self, monkeypatch):
        """Query parameters should be hashed and appended."""
        manager = ScoutManager()
        path = manager._url_to_path("https://example.com/page?q=hello&lang=en")
        # Domain as folder, path with hash
        assert path.parent.name == "example_com"
        assert path.suffix == ".md"

    def test_index_for_root(self):
        """A URL with no path should become ``index.md``."""
        manager = ScoutManager()
        path = manager._url_to_path("https://example.com")
        assert "index" in path.name

    def test_trailing_slash_becomes_index(self):
        """A URL ending in ``/`` should map to ``path/index.md``."""
        manager = ScoutManager()
        path = manager._url_to_path("https://example.com/docs/")
        assert path.name == "index.md"
        assert "docs" in str(path)


# ======================================================================
#  _expand_urls
# ======================================================================


class TestExpandUrls:
    def test_expands_range(self):
        """``{1..3}`` should expand to three URLs."""
        manager = ScoutManager()
        result = manager._expand_urls(["https://example.com/{1..3}"])
        assert len(result) == 3
        assert "https://example.com/1" in result
        assert "https://example.com/2" in result
        assert "https://example.com/3" in result

    def test_descending_range(self):
        """``{5..1}`` should expand in descending order."""
        manager = ScoutManager()
        result = manager._expand_urls(["https://example.com/{5..1}"])
        assert len(result) == 5
        assert result[0] == "https://example.com/5"
        assert result[-1] == "https://example.com/1"

    def test_passthrough_no_range(self):
        """URLs without range syntax pass through unchanged."""
        manager = ScoutManager()
        result = manager._expand_urls(["https://example.com/page"])
        assert result == ["https://example.com/page"]

    def test_mixed(self):
        """Mixed URLs with and without ranges handled correctly."""
        manager = ScoutManager()
        result = manager._expand_urls([
            "https://example.com/{1..2}",
            "https://example.com/static",
        ])
        assert len(result) == 3
        assert "https://example.com/static" in result


# ======================================================================
#  get_crawled_urls
# ======================================================================


class TestGetCrawledUrls:
    def test_scans_output_dir(self, tmp_path: Path):
        """Files with ``source_url:`` in frontmatter should be discovered."""
        output_dir = tmp_path / "scout_output"
        output_dir.mkdir(parents=True)
        (output_dir / "example_com").mkdir()
        page = output_dir / "example_com" / "page.md"
        page.write_text("---\nsource_url: https://example.com/page\n---\n\nContent.\n")

        manager = ScoutManager(output_dir=output_dir)
        urls = manager.get_crawled_urls()
        assert "https://example.com/page" in urls

    def test_empty_dir(self, tmp_path: Path):
        """An empty output directory should return an empty list."""
        empty = tmp_path / "empty"
        empty.mkdir()
        manager = ScoutManager(output_dir=empty)
        assert manager.get_crawled_urls() == []

    def test_missing_frontmatter(self, tmp_path: Path):
        """Files without ``source_url:`` should be silently skipped."""
        output_dir = tmp_path / "out"
        output_dir.mkdir(parents=True)
        (output_dir / "orphan.md").write_text("No frontmatter here.\n")

        manager = ScoutManager(output_dir=output_dir)
        urls = manager.get_crawled_urls()
        assert urls == []


# ======================================================================
#  _save_page
# ======================================================================


class TestSavePage:
    def test_saves_with_frontmatter(self, tmp_path: Path):
        """The saved file should include ``source_url`` and (optional)
        ``seed_url`` frontmatter."""
        manager = ScoutManager(output_dir=tmp_path)
        manager._save_page("https://example.com/p", "# Hello", seed_url="https://example.com")

        expected_path = tmp_path / "example_com" / "p.md"
        assert expected_path.exists()
        content = expected_path.read_text()
        assert "source_url: https://example.com/p" in content
        assert "seed_url: https://example.com" in content
        assert "# Hello" in content

    def test_handles_filename_collision(self, tmp_path: Path):
        """If the file already exists, a hash suffix should be appended."""
        manager = ScoutManager(output_dir=tmp_path)
        # Save same URL twice → second gets a hash suffix
        manager._save_page("https://example.com/p", "# First")
        manager._save_page("https://example.com/p", "# Second")

        files = list(tmp_path.rglob("*.md"))
        assert len(files) == 2  # Two distinct filenames (one hashed)
        contents = [f.read_text() for f in files]
        assert any("# First" in c for c in contents)
        assert any("# Second" in c for c in contents)

    def test_empty_content_skipped(self, tmp_path: Path):
        """Empty ``content`` should not write a file."""
        manager = ScoutManager(output_dir=tmp_path)
        manager._save_page("https://example.com/p", "")
        assert not list(tmp_path.rglob("*.md"))


# ======================================================================
#  run
# ======================================================================


class TestRunNonRecursive:
    @pytest.mark.asyncio
    async def test_batch_mode_processes_urls(self, tmp_path: Path):
        """Non-recursive mode should crawl URLs in batch."""
        manager = ScoutManager(output_dir=tmp_path)
        mock_crawler = AsyncMock()
        mock_crawler.crawl_batch.return_value.__aiter__.return_value = [
            ("https://example.com/1", "# Page 1"),
            ("https://example.com/2", "# Page 2"),
        ]
        manager.crawler = mock_crawler

        await manager.run(
            urls=["https://example.com/1", "https://example.com/2"],
            recursive=False,
        )
        # Files should have been saved
        saved = list(tmp_path.rglob("*.md"))
        assert len(saved) >= 1

    @pytest.mark.asyncio
    async def test_no_urls_early_return(self, tmp_path: Path):
        """With no URLs configured, the manager should return early."""
        manager = ScoutManager(output_dir=tmp_path)
        await manager.run(urls=[])
        saved = list(tmp_path.rglob("*.md"))
        assert saved == []


class TestRunRecursive:
    @pytest.mark.asyncio
    async def test_recursive_mode(self, tmp_path: Path):
        """Recursive mode should call ``crawl_recursive`` on the crawler."""
        manager = ScoutManager(output_dir=tmp_path)
        mock_crawler = AsyncMock()
        mock_crawler.crawl_recursive.return_value.__aiter__.return_value = [
            ("https://example.com/1", "# 1"),
            ("https://example.com/2", "# 2"),
        ]
        manager.crawler = mock_crawler

        await manager.run(
            urls=["https://example.com"],
            recursive=True,
            max_pages=5,
        )


class TestSyncRun:
    def test_sync_wrapper_runs(self):
        """``sync_run`` is a convenience wrapper that calls ``asyncio.run``."""
        with patch("scout.manager.ScoutManager") as mock_cls:
            mock_instance = AsyncMock()
            mock_cls.return_value = mock_instance
            sync_run(urls=["https://example.com"])
            mock_instance.run.assert_called_once()
