"""
CLI command for asking questions about the codebase using RAG.

Usage::

    hivemind ask "How does authentication work?"
    hivemind ask "How does authentication work?" --context "Adding OAuth" --max-chunks 10
"""

from __future__ import annotations

import typer


def register(app: typer.Typer) -> None:
    """Register the ``ask`` command on the main app."""
    from main import console, setup_logging
    from core.config import settings

    @app.command("ask", no_args_is_help=True)
    def ask(
        question: str = typer.Argument(
            ..., help="Natural language question about the codebase."
        ),
        context: str = typer.Option(
            "",
            "--context",
            "-c",
            help="Optional extra context about what you're trying to accomplish.",
        ),
        max_chunks: int = typer.Option(
            5,
            "--max-chunks",
            "-n",
            help="Maximum number of code chunks to retrieve (default: 5).",
            min=1,
            max=50,
        ),
        project_path: str = typer.Option(
            None,
            "--project-path",
            "-p",
            help="Project root path. Auto-detected from workspace by default.",
        ),
        verbose: bool = typer.Option(
            False,
            "--verbose",
            "-v",
            help="Enable debug logging to see API requests and response details.",
        ),
    ):
        """Ask a natural-language question about your codebase.

        Retrieves relevant code chunks via semantic search and synthesises
        an answer using the configured chat/LLM model.
        """
        log_level = "DEBUG" if verbose else settings.logging.level
        setup_logging(log_level, settings.logging.file_path)

        from core.rag import ask_codebase

        spinner = "[bold green]Searching codebase and synthesising answer..."
        with console.status(spinner):
            try:
                answer, citations = ask_codebase(
                    question,
                    context=context,
                    max_chunks=max_chunks,
                    project_path=project_path,
                )
            except ValueError as e:
                console.print(f"[yellow]{e}[/yellow]")
                raise typer.Exit(1)
            except Exception as e:
                console.print(f"[red]Error answering question: {e}[/red]")
                raise typer.Exit(1)

        from rich.panel import Panel
        from rich.markdown import Markdown

        # Display the answer in a styled panel
        answer_md = Markdown(answer)
        panel = Panel(
            answer_md,
            title="[bold cyan]Answer[/bold cyan]",
            title_align="left",
            border_style="cyan",
            padding=(1, 2),
        )
        console.print()
        console.print(panel)
        console.print()

        # Display citations / sources
        if citations:
            from rich.markdown import Markdown as MdCitations

            citations_md = MdCitations(citations)
            sources_panel = Panel(
                citations_md,
                title="[bold yellow]Sources[/bold yellow]",
                title_align="left",
                border_style="yellow",
                padding=(1, 2),
            )
            console.print(sources_panel)
            console.print()
