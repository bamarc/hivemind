import typer


def register(app: typer.Typer):
    """Register the search command on the main app."""
    from main import console, setup_logging

    @app.command("search", no_args_is_help=True)
    def search(
        query: str = typer.Argument(..., help="Semantic search query."),
        limit: int = typer.Option(5, "--limit", help="Number of results to return."),
        verbose: bool = typer.Option(False, "--verbose", help="Show detailed metadata."),
        output_format: str = typer.Option("text", "--format", "-f", help="Output format (text, json).")
    ):
        """One-off semantic search for terminal testing."""
        from core.clients import get_db, get_embedding
        from core.config import settings
        import json

        setup_logging(settings.logging.level, settings.logging.file_path)

        with console.status("[bold green]Searching..."):
            query_vector = get_embedding(query)
            response = get_db().query_points(
                collection_name=settings.qdrant.collection_name,
                query=query_vector,
                limit=limit,
                with_payload=True
            )
            results = response.points

        if not results:
            console.print("[yellow]No relevant code found.[/yellow]")
            return

        if output_format == "json":
            output_data = []
            for hit in results:
                data = {
                    "id": hit.id,
                    "score": hit.score,
                    "payload": hit.payload
                }
                output_data.append(data)
            console.print_json(data=output_data)
            return

        from rich.panel import Panel
        from rich.syntax import Syntax
        from rich.table import Table

        for hit in results:
            payload = hit.payload
            filepath = payload.get("filepath", "Unknown")
            content = payload.get("content", "")
            score = hit.score

            language = payload.get("language", "unknown")
            line_start = int(payload.get("line_start", 1))
            symbols = payload.get("symbols", [])

            title = f"[bold cyan]󰈙 {filepath}[/bold cyan]"
            if verbose:
                title += f" [dim](Score: {score:.4f})[/dim]"

            # Build metadata table for verbose mode
            meta_table = None
            if verbose:
                meta_table = Table(box=None, padding=(0, 1, 0, 0), show_header=False)
                meta_table.add_column("Key", style="bold white", justify="right")
                meta_table.add_column("Value", style="white")

                meta_table.add_row("Lines:", f"{line_start}-{payload.get('line_end', '?')}")
                if symbols:
                    meta_table.add_row("Symbols:", ", ".join(symbols[:10]))

                # Git Info
                if "commit_hash" in payload:
                    meta_table.add_row("Commit:", f"[magenta]{payload['commit_hash'][:8]}[/magenta]")
                    meta_table.add_row("Author:", payload.get("commit_author", "Unknown"))
                    meta_table.add_row("Date:", payload.get("commit_date", "Unknown"))

                # Path Segments
                if "path_segments" in payload:
                    segments = payload["path_segments"]
                    seg_str = " / ".join([segments[str(i)] for i in range(len(segments))])
                    meta_table.add_row("Breadcrumb:", f"[dim]{seg_str}[/dim]")

            # Standard subtitle for non-verbose
            subtitle = f"[dim]Lines: {line_start} | Score: {score:.2f}[/dim]"
            if symbols and not verbose:
                subtitle = f"[dim]Lines: {line_start} | Symbols: {', '.join(symbols[:3])} | Score: {score:.2f}[/dim]"

            # Use syntax highlighting
            try:
                display_content = Syntax(
                    content,
                    language,
                    theme="ansi_dark",
                    line_numbers=True,
                    start_line=line_start,
                    word_wrap=True
                )
            except Exception:
                display_content = content

            renderable = display_content
            if verbose and meta_table:
                from rich.console import Group
                renderable = Group(meta_table, "", display_content)

            panel = Panel(
                renderable,
                title=title,
                subtitle=subtitle if not verbose else None,
                title_align="left",
                subtitle_align="right",
                border_style="blue",
                padding=(1, 2)
            )

            console.print(panel)
