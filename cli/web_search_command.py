import typer
from typing import Optional


def register(app: typer.Typer):
    """Register the web-search command on the main app."""
    from main import console, setup_logging

    @app.command("web-search", no_args_is_help=True)
    def web_search(
        query: str = typer.Argument(..., help="Web search query."),
        max_results: int = typer.Option(10, "--max-results", "-n", help="Maximum number of results (1-20)."),
        backend: Optional[str] = typer.Option(None, "--backend", "-b", help="Search backend override (duckduckgo, brave, searxng)."),
        verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed logging."),
    ):
        """Search the web and display results in the terminal."""
        from core.config import settings
        from core.search import search_web

        setup_logging(settings.logging.level, settings.logging.file_path)

        with console.status("[bold green]Searching the web..."):
            try:
                results = search_web(query, max_results=max_results, backend=backend)
            except ImportError as e:
                console.print(
                    "[red]Search dependencies are not installed.[/red]\n\n"
                    "To use web search, install the scout extra:\n\n"
                    "  [bold]uv sync --extra scout[/bold]"
                )
                raise typer.Exit(1)
            except Exception as e:
                console.print(f"[red]Error:[/red] {e}")
                raise typer.Exit(1)

        if not results:
            console.print(f"[yellow]No web results found for:[/yellow] {query}")
            return

        from rich.table import Table

        table = Table(title=f"Web Search Results: {query}", box=None)
        table.add_column("#", style="dim", justify="right")
        table.add_column("Title", style="bold cyan")
        table.add_column("URL", style="blue")
        table.add_column("Snippet", style="white", no_wrap=False)

        for i, r in enumerate(results, 1):
            snippet = r.snippet
            if len(snippet) > 120:
                snippet = snippet[:120] + "..."
            table.add_row(str(i), r.title, r.url, snippet)

        console.print(table)
