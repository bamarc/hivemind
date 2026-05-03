import os
from pathlib import Path
from typing import List, Optional, Literal, Tuple
from pydantic import Field, SecretStr
from pydantic_settings import (
    BaseSettings, 
    SettingsConfigDict, 
    PydanticBaseSettingsSource, 
    YamlConfigSettingsSource
)

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

class QdrantSettings(BaseSettings):
    url: str = "http://localhost:6333"
    api_key: Optional[SecretStr] = None
    collection_name: str = "hivemind_code"

class EmbeddingSettings(BaseSettings):
    api_url: str = "http://localhost:1234/v1"
    model_name: str = "qwen3-4B-embedding"
    api_key: Optional[SecretStr] = None
    embedding_dim: int = 2500
    batch_size: int = 100

class ChatSettings(BaseSettings):
    api_url: str = "http://localhost:1234/v1"
    model_name: str = "gpt-4o"
    api_key: Optional[SecretStr] = None

class BySizeSettings(BaseSettings):
    chunk_size: int = 500
    overlap: int = 50

class ByLinesSettings(BaseSettings):
    chunk_lines: int = 50
    overlap_lines: int = 5

class ASTSettings(BaseSettings):
    chunk_lines: int = 50
    overlap_lines: int = 5

class ChunkingSettings(BaseSettings):
    strategy: Literal["by_size", "by_lines", "ast"] = "ast"
    language_aware: bool = True
    by_size: BySizeSettings = BySizeSettings()
    by_lines: ByLinesSettings = ByLinesSettings()
    ast: ASTSettings = ASTSettings()

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

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HIVEMIND_",
        env_nested_delimiter="__",
        yaml_file=(
            ".hivemind/config.yaml",
            "config.yaml"
        )
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
            init_settings,
            env_settings,
            YamlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )

settings = Settings()
