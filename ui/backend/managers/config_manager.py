"""ConfigManager — reads/writes Hivemind's config.yaml for repo management.

Phase 7: Wired to ``core.config.HivemindConfig``.
"""

from __future__ import annotations

import logging
from typing import Any

from core.config import settings

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages repository configuration and Hivemind settings.

    Reads/writes directly to the Hivemind ``Settings`` singleton.
    Repo definitions live in ``settings.workspace_path / .hivemind / config.yaml``
    as part of Hivemind's project-level config.
    """

    def __init__(self) -> None:
        self._repos: list[dict[str, Any]] = []

    # ── Repository CRUD ──────────────────────────────────────────────────

    def get_repos(self) -> list[dict[str, Any]]:
        """Return all configured repositories (from workspace_path or stub)."""
        # For now, return a stub list.  In future this will read from
        # Hivemind's project config.
        if not self._repos:
            self._repos = [
                {
                    "name": "hivemind",
                    "path": str(settings.workspace_path),
                    "indexed": True,
                    "chunks": 128,
                },
            ]
        return list(self._repos)

    def add_repo(self, path: str, chunker: str = "ast") -> dict[str, Any]:
        """Add a repository to the configuration."""
        name = path.rstrip("/").split("/")[-1]
        repo = {"name": name, "path": path, "indexed": False, "chunks": 0}
        self._repos.append(repo)
        logger.info("Added repo: %s (chunker=%s)", path, chunker)
        return repo

    def remove_repo(self, path: str) -> bool:
        """Remove a repository from the configuration."""
        before = len(self._repos)
        self._repos = [r for r in self._repos if r["path"] != path]
        return len(self._repos) < before

    def reindex_repo(self, path: str) -> bool:
        """Mark a repository for re-indexing."""
        for repo in self._repos:
            if repo["path"] == path:
                repo["indexed"] = False
                repo["chunks"] = 0
                return True
        return False

    # ── Settings ─────────────────────────────────────────────────────────

    def get_settings(self) -> dict[str, Any]:
        """Return current settings from Hivemind's core Settings singleton."""
        s = settings
        # Safely extract secret value if present
        api_key = ""
        if s.model.api_key:
            try:
                api_key = s.model.api_key.get_secret_value()
            except Exception:
                api_key = str(s.model.api_key) if s.model.api_key else ""
        return {
            "qdrantHost": s.qdrant.url.replace("http://", "").rsplit(":", 1)[0],
            "qdrantPort": int(s.qdrant.url.rsplit(":", 1)[-1].rstrip("/") or "6333"),
            "collectionName": s.qdrant.collection_name,
            "embeddingProvider": "LM Studio",
            "embeddingModel": s.model.model_name,
            "embeddingEndpoint": s.model.api_url,
            "embeddingApiKey": api_key,
            "watcherEnabled": True,
            "watcherDebounce": 2.0,
        }

    def save_settings(self, data: dict[str, Any]) -> None:
        """Persist settings to Hivemind's project config.yaml."""
        import os
        from pathlib import Path
        import yaml

        # Determine config path
        project_config = settings.workspace_path / ".hivemind" / "config.yaml"

        # Load existing config or start fresh
        existing = {}
        if project_config.exists():
            with open(project_config) as f:
                existing = yaml.safe_load(f) or {}

        # Ensure nested structure
        existing.setdefault("model", {})
        existing["model"]["api_key"] = data.get("embeddingApiKey", "")
        existing["model"]["api_url"] = data.get("embeddingEndpoint", settings.model.api_url)
        existing["model"]["model_name"] = data.get("embeddingModel", settings.model.model_name)

        existing.setdefault("qdrant", {})
        existing["qdrant"]["url"] = "http://{}:{}".format(
            data.get("qdrantHost", "localhost"),
            data.get("qdrantPort", 6333),
        )
        existing["qdrant"]["collection_name"] = data.get("collectionName", settings.qdrant.collection_name)

        # Write back
        project_config.parent.mkdir(parents=True, exist_ok=True)
        with open(project_config, "w") as f:
            yaml.dump(existing, f, default_flow_style=False)

        # Reload settings singleton
        from core.config import reset_settings
        reset_settings()

        logger.info("Settings saved to %s", project_config)
