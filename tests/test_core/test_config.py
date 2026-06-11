"""
Tests for :mod:`core.config`.

These tests verify the Pydantic-based settings hierarchy, YAML file
loading, environment variable overrides, and default value behaviour.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from core.config import (
    ApiSettings,
    ByLinesSettings,
    BySizeSettings,
    ChunkingSettings,
    EmbeddingSettings,
    LoggingSettings,
    QdrantSettings,
    ScoutSettings,
    SecuritySettings,
    Settings,
    StateSettings,
)


class TestQdrantSettings:
    def test_default_url(self):
        s = QdrantSettings()
        assert s.url == "http://localhost:6333"

    def test_default_collection_name(self):
        s = QdrantSettings()
        assert s.collection_name == "hivemind_code"

    def test_api_key_optional(self):
        s = QdrantSettings()
        assert s.api_key is None


class TestEmbeddingSettings:
    def test_default_api_url(self):
        s = EmbeddingSettings()
        # The default is http://localhost:1234/v1
        assert "localhost" in s.api_url

    def test_default_model_name(self):
        s = EmbeddingSettings()
        assert isinstance(s.model_name, str)
        assert len(s.model_name) > 0

    def test_embedding_dim_default_is_none(self):
        """``embedding_dim`` defaults to ``None`` — auto-detected at runtime."""
        s = EmbeddingSettings()
        assert s.embedding_dim is None

    def test_batch_size_positive(self):
        s = EmbeddingSettings()
        assert s.batch_size > 0


class TestScoutSettings:
    def test_default_max_pages(self):
        s = ScoutSettings()
        assert s.max_pages_per_domain == 50

    def test_default_concurrency(self):
        s = ScoutSettings()
        assert s.concurrency_limit == 5

    def test_default_exclude_patterns(self):
        s = ScoutSettings()
        assert "*login*" in s.exclude_patterns
        assert "*pricing*" in s.exclude_patterns

    def test_base_delay_is_tuple(self):
        s = ScoutSettings()
        assert isinstance(s.base_delay, tuple)
        assert len(s.base_delay) == 2
        assert all(isinstance(v, float) for v in s.base_delay)


class TestChunkingSettings:
    def test_default_strategy(self):
        s = ChunkingSettings()
        assert s.strategy in ("by_size", "by_lines", "ast")

    def test_nested_settings_have_defaults(self):
        s = ChunkingSettings()
        assert s.by_size.chunk_size == 500
        assert s.by_lines.chunk_lines == 50
        assert s.ast.chunk_lines == 50


class TestApiSettings:
    def test_default_host(self):
        s = ApiSettings()
        assert s.host == "0.0.0.0"

    def test_default_port(self):
        s = ApiSettings()
        assert s.port == 8001

    def test_default_cors_allows_all(self):
        s = ApiSettings()
        assert "*" in s.cors_origins


class TestLoggingSettings:
    def test_default_level(self):
        s = LoggingSettings()
        assert s.level == "INFO"

    def test_file_path_none_by_default(self):
        s = LoggingSettings()
        assert s.file_path is None


class TestSecuritySettings:
    def test_default_header(self):
        s = SecuritySettings()
        assert s.api_key_header == "X-API-Key"


class TestStateSettings:
    def test_directory_contains_hivemind(self):
        """The default state directory should be ``.hivemind/state``."""
        s = StateSettings()
        assert str(s.directory) == ".hivemind/state"


class TestSettings:
    @pytest.fixture(autouse=True)
    def _backup_env(self, monkeypatch):
        """Isolate from the user's global config and env vars."""
        import core.config as cfg
        # Point global config to a non-existent file so this test class
        # only sees project YAML and built-in defaults.
        monkeypatch.setattr(cfg, "_GLOBAL_CONFIG_PATH", Path("/nonexistent/global.yaml"))
        yield

    def test_default_project_name(self):
        s = Settings()
        # Should match the current working directory name
        assert s.project_name == Path(os.getcwd()).name

    def test_has_all_subsections(self):
        s = Settings()
        assert s.qdrant is not None
        assert s.model is not None
        assert s.chat is not None
        assert s.chunking is not None
        assert s.api is not None
        assert s.logging is not None
        assert s.state is not None
        assert s.security is not None
        assert s.scout is not None
        assert s.preprocessor is not None

    def test_git_enabled_default(self):
        s = Settings()
        assert s.git_enabled is True

    def test_indexer_workers_default(self):
        s = Settings()
        assert s.indexer_workers == 4

    def test_observability_metrics_default(self):
        s = Settings()
        assert s.observability_metrics_enabled is True

    def test_workspace_path_default(self):
        s = Settings()
        assert isinstance(s.workspace_path, Path)
        assert s.workspace_path.exists()


class TestSettingsYamlLoading:
    def test_yaml_overrides_defaults(self, tmp_project: Path):
        """When ``config.yaml`` exists in the project directory, values
        from that file should override built-in defaults."""
        # tmp_project creates a config.yaml with qdrant.collection_name = "test_collection"
        # and changes os.getcwd() to tmp_project.  Settings() reads from
        # os.getcwd()/config.yaml at construction time.
        s = Settings()
        assert s.qdrant.collection_name == "test_collection"

    def test_global_fallback_source_fills_missing_keys(self, tmp_path: Path):
        """``_GlobalFallbackYamlSource`` merges global YAML into gaps
        left by the project config."""
        import yaml
        import core.config as cfg

        # Project config: only sets model.api_url
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        hive_dir = project_dir / ".hivemind"
        hive_dir.mkdir()
        project_yaml = hive_dir / "config.yaml"
        project_yaml.write_text(yaml.dump({
            "model": {"api_url": "http://project:1234/v1"},
        }))

        # Global config: has model.model_name and qdrant
        global_dir = tmp_path / ".hivemind"
        global_dir.mkdir(parents=True)
        global_yaml = global_dir / "config.yaml"
        global_yaml.write_text(yaml.dump({
            "model": {"api_url": "http://global:1234/v1", "model_name": "global-model"},
            "qdrant": {"collection_name": "global_collection"},
        }))

        # Point _GLOBAL_CONFIG_PATH at our fake global file
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(cfg, "_GLOBAL_CONFIG_PATH", global_yaml)

        # Walk into the project dir so project yaml is found
        cwd = Path.cwd()
        try:
            os.chdir(str(project_dir))
            src = cfg._GlobalFallbackYamlSource(Settings)

            # Project value should win
            assert src.yaml_data["model"]["api_url"] == "http://project:1234/v1"
            # Global value should fill the gap
            assert src.yaml_data["model"]["model_name"] == "global-model"
            # Global-only section should be present
            assert src.yaml_data["qdrant"]["collection_name"] == "global_collection"
        finally:
            os.chdir(str(cwd))
            monkeypatch.undo()

    def test_global_fallback_source_logs_warning_on_error(self, tmp_path: Path, caplog):
        """``_GlobalFallbackYamlSource`` logs a warning if the global config file
        exists but fails to load (e.g. invalid YAML or permission error)."""
        import core.config as cfg

        global_yaml = tmp_path / "bad_config.yaml"
        # Write invalid YAML
        global_yaml.write_text("invalid: [yaml: content")

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(cfg, "_GLOBAL_CONFIG_PATH", global_yaml)

        try:
            with caplog.at_level("WARNING"):
                src = cfg._GlobalFallbackYamlSource(Settings)

            # The config object should still initialize successfully,
            # but we should see a warning in the logs.
            assert any("Failed to load global config from" in record.message for record in caplog.records)
            assert any("bad_config.yaml" in record.message for record in caplog.records)
        finally:
            monkeypatch.undo()

    def test_env_var_override(self, monkeypatch):
        """Environment variables prefixed with ``HIVEMIND_`` should
        override YAML and defaults."""
        monkeypatch.setenv("HIVEMIND_QDRANT__URL", "http://custom:6333")
        monkeypatch.setenv("HIVEMIND_QDRANT__COLLECTION_NAME", "env_collection")

        s = Settings()
        # The env vars are read by pydantic-settings because the
        # ``model_config`` has ``env_prefix="HIVEMIND_"``.
        assert s.qdrant.url == "http://custom:6333"
        assert s.qdrant.collection_name == "env_collection"


class TestSettingsEdgeCases:
    def test_nested_delimiter(self, monkeypatch):
        """Double underscore should allow setting nested fields via env vars."""
        monkeypatch.setenv("HIVEMIND_CHUNKING__STRATEGY", "by_lines")
        s = Settings()
        assert s.chunking.strategy == "by_lines"

    def test_indexer_workers_from_env(self, monkeypatch):
        monkeypatch.setenv("HIVEMIND_INDEXER_WORKERS", "8")
        s = Settings()
        assert s.indexer_workers == 8
