import typer
from pathlib import Path
from typing import Optional, List


def register(parent_app: typer.Typer):
    """Register scout subcommands on the parent app."""
    from main import console, setup_logging

    scout_app = typer.Typer(help="Manage the web scout (crawler).", no_args_is_help=True)
    parent_app.add_typer(scout_app, name="scout")

    @scout_app.command("crawl")
    def scout_crawl(
        urls: Optional[List[str]] = typer.Argument(None, help="Specific URLs to scout."),
        recursive: bool = typer.Option(False, "--recursive", "-r", help="Perform recursive crawling."),
        max_pages: Optional[int] = typer.Option(None, "--max-pages", "-m", help="Max pages to crawl (overrides config)."),
        output_dir: Optional[Path] = typer.Option(None, "--output-dir", "-o", help="Root directory for saved markdown files."),
        stay_in_path: bool = typer.Option(False, "--stay-in-path", help="Only follow URLs that start with the seed URL path."),
        skip_existing: bool = typer.Option(True, "--skip-existing/--no-skip", help="Skip URLs that have already been crawled."),
        include_patterns: Optional[List[str]] = typer.Option(None, "--include", "-i", help="Only crawl URLs matching these patterns (glob). Can be used multiple times."),
        concurrency_limit: Optional[int] = typer.Option(None, "--concurrency", "-c", help="Max parallel requests."),
        headful: bool = typer.Option(False, "--headful", help="Run browser with window visible."),
        delay: Optional[float] = typer.Option(None, "--delay", help="Base delay between requests in seconds."),
        verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging.")
    ):
        """Crawl web content and save it for indexing."""
        try:
            from scout.manager import ScoutManager
        except ImportError:
            console.print(
                "[red]Scout dependencies are not installed.[/red]\n\n"
                "To use the web scout, install with scout dependencies:\n\n"
                "  [bold]bash install.sh[/bold]\n\n"
                "Or via uv directly:\n\n"
                "  [bold]uv tool install --reinstall --force . --with crawl4ai --with playwright[/bold]\n\n"
                "For a minimal (core-only) install, use:\n\n"
                "  [bold]bash install.sh --minimal[/bold]"
            )
            raise typer.Exit(1)

        from core.config import settings
        import asyncio

        level = "DEBUG" if verbose else settings.logging.level
        setup_logging(level, settings.logging.file_path)

        manager = ScoutManager(console=console, output_dir=output_dir)
        asyncio.run(manager.run(
            urls,
            recursive=recursive,
            max_pages=max_pages,
            stay_in_path=stay_in_path,
            skip_existing=skip_existing,
            include_patterns=include_patterns,
            concurrency_limit=concurrency_limit,
            headless=not headful,
            base_delay=delay
        ))
