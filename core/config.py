from __future__ import annotations

import os
import yaml
from pathlib import Path
from typing import Any, List, Optional, Literal, Tuple
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
    PydanticBaseSettingsSource,
    YamlConfigSettingsSource
)

from core.secrets import decrypt as _decrypt_secret, is_encrypted as _is_encrypted

# Path to the global config file (~/.hivemind/config.yaml).
# Exposed as a module-level variable so tests can override it directly
# without relying on HOME monkeypatching.
_GLOBAL_CONFIG_PATH: Path = Path("~/.hivemind/config.yaml").expanduser()

class ScoutSettings(BaseSettings):
    urls: List[str] = []
    output_directory: str = ".hivemind/scout"
    recursive: bool = False
    max_pages_per_domain: int = 50
    exclude_patterns: List[str] = ["*login*", "*signup*", "*cart*", "*pricing*"]
    content_filter: bool = True
    skip_existing: bool = True
    include_patterns: List[str] = []
    concurrency_limit: int = 5
    headless: bool = True
    use_stealth: bool = True
    base_delay: Tuple[float, float] = (1.0, 3.0)
    # Search backend configuration
    search_backend: Literal["duckduckgo", "brave", "searxng"] = "duckduckgo"
    brave_api_key: Optional[SecretStr] = None
    searxng_url: str = "http://localhost:8888"
    searxng_categories: List[str] = []

    @field_validator("brave_api_key", mode="before")
    @classmethod
    def _decrypt_brave_key(cls, v: Any) -> Any:
        if isinstance(v, str) and _is_encrypted(v):
            return _decrypt_secret(v)
        return v

class QdrantSettings(BaseSettings):
    url: str = "http://localhost:6333"
    api_key: Optional[SecretStr] = None
    collection_name: str = "hivemind_code"

    @field_validator("api_key", mode="before")
    @classmethod
    def _decrypt_api_key(cls, v: Any) -> Any:
        if isinstance(v, str) and _is_encrypted(v):
            return _decrypt_secret(v)
        return v

class EmbeddingSettings(BaseSettings):
    api_url: str = "http://localhost:1234/v1"
    model_name: str = "qwen3-4B-embedding"
    api_key: Optional[SecretStr] = None
    embedding_dim: Optional[int] = None  # None = auto-detect via probe request
    batch_size: int = 100

    @field_validator("api_key", mode="before")
    @classmethod
    def _decrypt_api_key(cls, v: Any) -> Any:
        if isinstance(v, str) and _is_encrypted(v):
            return _decrypt_secret(v)
        return v

class ChatSettings(BaseSettings):
    api_url: str = "http://localhost:1234/v1"
    model_name: str = "gpt-4o"
    api_key: Optional[SecretStr] = None

    @field_validator("api_key", mode="before")
    @classmethod
    def _decrypt_api_key(cls, v: Any) -> Any:
        if isinstance(v, str) and _is_encrypted(v):
            return _decrypt_secret(v)
        return v

class BySizeSettings(BaseSettings):
    chunk_size: int = 500
    overlap: int = 50

class ByLinesSettings(BaseSettings):
    chunk_lines: int = 50
    overlap_lines: int = 5

class ASTSettings(BaseSettings):
    chunk_lines: int = 50
    overlap_lines: int = 5

class SparseSettings(BaseSettings):
    """Configuration for sparse vector generation (hybrid search)."""
    enabled: bool = True  # Set False to skip sparse vector generation during indexing
    vocab_size: int = 50_000  # Hash space for sparse token indices


class ChunkingSettings(BaseSettings):
    strategy: Literal["by_size", "by_lines", "ast", "hybrid"] = "ast"
    language_aware: bool = True
    by_size: BySizeSettings = BySizeSettings()
    by_lines: ByLinesSettings = ByLinesSettings()
    ast: ASTSettings = ASTSettings()
    hybrid: ByLinesSettings = ByLinesSettings()  # reuses line-based settings

class ApiSettings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8001
    cors_origins: List[str] = ["*"]

class LoggingSettings(BaseSettings):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    file_path: Optional[Path] = None

class StateSettings(BaseSettings):
    directory: Path = Field(
        default_factory=lambda: Path(".hivemind/state")
    )

class SecuritySettings(BaseSettings):
    secret_file: Path = Path("~/.hivemind/secrets.yaml").expanduser()
    api_key_header: str = "X-API-Key"

class PreprocessorSettings(BaseSettings):
    enabled: bool = True
    # Allow users to add custom directories for pre-processors if needed
    plugin_directories: List[Path] = []

class _GlobalFallbackYamlSource(YamlConfigSettingsSource):
    """Reads from ``.hivemind/config.yaml`` *and* ``~/.hivemind/config.yaml``.

    The global config is treated as lowest-priority YAML: it only fills in
    keys that are **not** present in the project config.
    """

    def __init__(self, settings_cls: type[BaseSettings]) -> None:
        # Let the parent read project YAML files (from yaml_file in model_config)
        super().__init__(settings_cls)

        # Also read ~/.hivemind/config.yaml as a lower-priority fallback.
        # Uses module-level _GLOBAL_CONFIG_PATH so tests can override it.
        _glob_path = _GLOBAL_CONFIG_PATH
        if _glob_path.exists():
            try:
                with open(_glob_path) as f:
                    global_data = yaml.safe_load(f) or {}
            except Exception:
                return

            # Merge: global values only fill gaps that project config leaves.
            self._merge_fallback(self.yaml_data, global_data)
            # Sync init_kwargs with the now-merged yaml_data so that
            # __call__() returns the full configuration including global
            # fallback values, not just project-level YAML.
            for key, value in self.yaml_data.items():
                if key not in self.init_kwargs:
                    self.init_kwargs[key] = value
                elif isinstance(value, dict) and isinstance(
                    self.init_kwargs.get(key), dict
                ):
                    self._merge_fallback(self.init_kwargs[key], value)

    @staticmethod
    def _merge_fallback(dest: dict, source: dict) -> None:
        """Recursively merge *source* into *dest*, only writing keys that
        are missing from *dest*."""
        for key, value in source.items():
            if key not in dest:
                dest[key] = value
            elif isinstance(value, dict) and isinstance(dest.get(key), dict):
                _GlobalFallbackYamlSource._merge_fallback(dest[key], value)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HIVEMIND_",
        env_nested_delimiter="__",
        yaml_file=".hivemind/config.yaml",  # Project config (highest YAML priority)
    )

    qdrant: QdrantSettings = QdrantSettings()
    model: EmbeddingSettings = EmbeddingSettings()
    chat: ChatSettings = ChatSettings()
    chunking: ChunkingSettings = ChunkingSettings()
    api: ApiSettings = ApiSettings()
    logging: LoggingSettings = LoggingSettings()
    state: StateSettings = StateSettings()
    security: SecuritySettings = SecuritySettings()
    scout: ScoutSettings = ScoutSettings()
    preprocessor: PreprocessorSettings = PreprocessorSettings()
    sparse: SparseSettings = SparseSettings()
    git_enabled: bool = True
    git_only_tracked: bool = False
    indexer_workers: int = 4
    observability_metrics_enabled: bool = True
    workspace_path: Path = Field(default_factory=lambda: Path(os.environ.get("HIVEMIND_WORKSPACE_PATH", os.getcwd())))

    @property
    def project_name(self) -> str:
        return self.workspace_path.name or "hivemind_global"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,              # Constructor kwargs (highest priority)
            env_settings,               # Environment variables
            _GlobalFallbackYamlSource(settings_cls),  # YAML: project overrides global
            file_secret_settings,       # Secrets file (lowest priority)
        )

settings = Settings()


def reset_settings() -> None:
    """Reset the module-level settings singleton.

    Creates a fresh ``Settings()`` instance, reading from current
    environment variables and filesystem state.  Use this in tests
    to ensure a clean configuration slate between test cases.
    """
    global settings
    settings = Settings()
