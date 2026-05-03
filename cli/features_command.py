"""
CLI command to inspect Hivemind features: installed dependencies, service
connectivity, MCP tool availability, and configuration summary.
"""

import importlib.util
import sys
import typer
from typing import Any

from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.tree import Tree
from rich import box


def _spec_available(mod: str) -> bool:
    """Return ``True`` if *mod* can be imported (installed)."""
    return importlib.util.find_spec(mod) is not None


def _import_ok(mod: str, name: str = "") -> tuple[bool, str]:
    """Check whether *mod* imports without error.

    Returns ``(ok, detail)`` where *detail* is ``"installed"`` or the
    reason the import failed (e.g. ``"not found"``).
    """
    try:
        __import__(mod)
        return True, "installed"
    except ImportError as exc:
        return False, str(exc)


# ---------------------------------------------------------------------------
# Dependency groups
# ---------------------------------------------------------------------------

SCOUT_DEPS: dict[str, str] = {
    "crawl4ai": "scout_urls / deep_research",
    "playwright": "scout_urls / deep_research",
}

CORE_DEPS: dict[str, str] = {
    "ddgs": "search_web / deep_research",
}

# Map each optional dependency extra to its packages
EXTRA_GROUPS: dict[str, dict[str, str]] = {
    "scout": SCOUT_DEPS,
    "web": CORE_DEPS,
}

# ---------------------------------------------------------------------------
# MCP tool list (sourced from server/server.py)
# ---------------------------------------------------------------------------

MCP_TOOLS: list[dict[str, Any]] = [
    {"name": "semantic_code_search",     "required": "core",      "desc": "Find code by meaning (requires Qdrant + embedding model)"},
    {"name": "get_file_tree",            "required": "core",      "desc": "Structural project directory overview"},
    {"name": "get_index_status",         "required": "core",      "desc": "Check if the semantic-search index is ready"},
    {"name": "start_indexing",           "required": "core",      "desc": "Trigger background indexing for a project"},
    {"name": "analyze_code_complexity",  "required": "core",      "desc": "Calculate AST complexity metrics for a file"},
    {"name": "generate_blueprint",       "required": "chat_api",  "desc": "Generate structured JSON blueprint via LLM"},
    {"name": "run_verification",         "required": "core",      "desc": "Run linters and tests for the project"},
    {"name": "search_web",              "required": "web_deps",  "desc": "Search the web via DuckDuckGo / SearXNG"},
    {"name": "scout_urls",              "required": "scout_deps", "desc": "Crawl URLs and return content as markdown"},
    {"name": "deep_research",           "required": "scout_deps", "desc": "Search web + crawl top results in one step"},
    {"name": "read_file",               "required": "core",      "desc": "Read file contents with optional line range"},
    {"name": "get_git_history",          "required": "core",      "desc": "Get last commit metadata for a file"},
]


def _check_service(
    label: str,
    check_fn: Any,
    config_display: str,
) -> tuple[bool, str]:
    """Run *check_fn*, return ``(ok, detail_msg)``."""
    try:
        ok = check_fn()
        detail = "✓ connected" if ok else "✗ unreachable"
        return ok, f"{config_display} | {detail}"
    except Exception as exc:
        return False, f"{config_display} | ✗ error: {exc}"


# ---------------------------------------------------------------------------
# CLI command
# ---------------------------------------------------------------------------


def register(app: typer.Typer):
    """Register the ``features`` command on the main app."""

    from main import console

    @app.command("features")
    def features():
        """Show installed features, service health, and MCP tool availability."""
        from core.config import settings

        # ---- header ----
        console.print()
        console.print(Panel(
            "[bold yellow]Hivemind Feature Inspector[/bold yellow]\n"
            f"Project: [cyan]{settings.workspace_path.name}[/cyan]",
            box=box.ROUNDED,
        ))
        console.print()

        # =================================================================
        # 1. Configuration summary
        # =================================================================
        cfg = Table(
            title="Configuration",
            box=box.SIMPLE,
            show_header=False,
            padding=(0, 2),
        )
        cfg.add_column("Key", style="bold white", no_wrap=True)
        cfg.add_column("Value", style="cyan")

        cfg.add_row("Qdrant URL",    settings.qdrant.url or "(not set)")
        cfg.add_row("Collection",    settings.qdrant.collection_name)
        cfg.add_row("Embedding API", settings.model.api_url)
        cfg.add_row("Embedding Model", settings.model.model_name)
        cfg.add_row("Embedding Dim", str(settings.model.embedding_dim))
        cfg.add_row("Chat API",      settings.chat.api_url)
        cfg.add_row("Chat Model",    settings.chat.model_name)
        cfg.add_row("Search Backend", settings.scout.search_backend)
        cfg.add_row("Git Enabled",   str(settings.git_enabled))
        cfg.add_row("Workspace",     str(settings.workspace_path))

        console.print(cfg)
        console.print()

        # =================================================================
        # 2. Service health
        # =================================================================
        from core.clients import check_qdrant_connection, get_embedder, get_chat_client

        svc = Table(
            title="Service Health",
            box=box.SIMPLE,
            show_header=False,
            padding=(0, 2),
        )
        svc.add_column("Service", style="bold white", no_wrap=True)
        svc.add_column("Status")

        # Qdrant
        q_ok, q_detail = _check_service(
            "Qdrant", check_qdrant_connection,
            settings.qdrant.url,
        )
        svc.add_row("Qdrant", f"{'✓' if q_ok else '✗'} {q_detail}")

        # Embedding API
        emb_ok = False
        try:
            embedder = get_embedder()
            # Lightweight check: list models (cheaper than an embedding call)
            embedder.models.list()
            emb_ok = True
            emb_detail = "✓ reachable"
        except Exception as exc:
            emb_detail = f"✗ {exc}"
        svc.add_row("Embedding API", f"{'✓' if emb_ok else '✗'} {settings.model.api_url} | {emb_detail}")

        # Chat API
        chat_ok = False
        try:
            chat = get_chat_client()
            chat.models.list()
            chat_ok = True
            chat_detail = "✓ reachable"
        except Exception as exc:
            chat_detail = f"✗ {exc}"
        svc.add_row("Chat / LLM API", f"{'✓' if chat_ok else '✗'} {settings.chat.api_url} | {chat_detail}")

        console.print(svc)
        console.print()

        # =================================================================
        # 3. Optional dependency groups
        # =================================================================
        deps_table = Table(
            title="Optional Dependencies",
            box=box.SIMPLE,
            show_header=True,
            padding=(0, 2),
        )
        deps_table.add_column("Extra", style="bold white")
        deps_table.add_column("Package", style="cyan")
        deps_table.add_column("Status")
        deps_table.add_column("Used By")

        for extra_name, packages in EXTRA_GROUPS.items():
            all_ok = True
            for pkg, used_by in packages.items():
                ok, detail = _import_ok(pkg)
                status = f"✓ {detail}" if ok else f"✗ {detail}"
                deps_table.add_row(
                    extra_name if all_ok else "",
                    pkg,
                    status,
                    used_by,
                )
                all_ok = all_ok and ok

        console.print(deps_table)
        console.print()

        # =================================================================
        # 4. MCP Tools
        # =================================================================
        tools_table = Table(
            title="MCP Tools",
            box=box.SIMPLE,
            show_header=True,
            padding=(0, 2),
        )
        tools_table.add_column("Tool", style="bold white", no_wrap=True)
        tools_table.add_column("Status")
        tools_table.add_column("Description")

        for tool in MCP_TOOLS:
            req = tool["required"]
            if req == "core":
                # Core tools are always available (they don't require external services)
                status = "✓ available"
            elif req == "chat_api":
                status = "✓ available" if chat_ok else "✗ chat API unreachable"
            elif req == "scout_deps":
                scout_ready = all(
                    _spec_available(p) for p in SCOUT_DEPS
                )
                status = "✓ available" if scout_ready else "✗ missing: uv sync --extra scout"
            elif req == "web_deps":
                web_ready = all(
                    _spec_available(p) for p in CORE_DEPS
                )
                status = "✓ available" if web_ready else "✗ missing: uv sync --extra web"
            else:
                status = "~ unknown"

            tools_table.add_row(tool["name"], status, tool["desc"])

        console.print(tools_table)
        console.print()

        # =================================================================
        # 5. Quick summary
        # =================================================================
        summary_parts: list[str] = []
        if q_ok:
            summary_parts.append("[green]✓ Qdrant[/green]")
        else:
            summary_parts.append("[red]✗ Qdrant[/red]")

        if emb_ok:
            summary_parts.append("[green]✓ Embedding[/green]")
        else:
            summary_parts.append("[red]✗ Embedding[/red]")

        if chat_ok:
            summary_parts.append("[green]✓ Chat LLM[/green]")
        else:
            summary_parts.append("[red]✗ Chat LLM[/red]")

        scout_ready = all(_spec_available(p) for p in SCOUT_DEPS)
        if scout_ready:
            summary_parts.append("[green]✓ Scout[/green]")
        else:
            summary_parts.append("[dim]✗ Scout (optional)[/dim]")

        web_ready = all(_spec_available(p) for p in CORE_DEPS)
        if web_ready:
            summary_parts.append("[green]✓ Web Search[/green]")
        else:
            summary_parts.append("[red]✗ Web Search[/red]")

        console.print(Panel(
            "  ".join(summary_parts),
            title="Summary",
            box=box.ROUNDED,
        ))
        console.print()
