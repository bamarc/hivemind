import typer
import logging
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.logging import RichHandler

console = Console()

def setup_logging(level: str, file_path: Optional[Path] = None):
    handlers = [RichHandler(console=console, rich_tracebacks=True)]
    if file_path:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(file_path)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        ))
        handlers.append(file_handler)
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=handlers
    )

app = typer.Typer(
    name="hivemind",
    help="Hivemind: A production-ready semantic code indexer and search tool.",
    add_completion=True,
    no_args_is_help=True
)

@app.callback(invoke_without_command=True)
def callback(ctx: typer.Context):
    """Hivemind CLI"""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()

# Register all subcommand modules
from cli.indexer_commands import register as register_indexer
from cli.scout_commands import register as register_scout
from cli.search_command import register as register_search
from cli.web_search_command import register as register_web_search
from cli.server_commands import register as register_server
from cli.project_commands import register as register_project
from cli.features_command import register as register_features
from cli.ask_command import register as register_ask

register_indexer(app)
register_scout(app)
register_search(app)
register_web_search(app)
register_server(app)
register_project(app)
register_features(app)
register_ask(app)

def cli():
    import sys
    if len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] == "indexer"):
        sys.argv.append("--help")
    app()

if __name__ == "__main__":
    cli()
