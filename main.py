import typer
import logging
from pathlib import Path
from typing import Optional, List
from rich.console import Console
from rich.logging import RichHandler

# Set up logging early
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

# Indexer Subcommand
indexer_app = typer.Typer(help="Manage the code indexer.", no_args_is_help=True)
app.add_typer(indexer_app, name="indexer")

@indexer_app.callback(invoke_without_command=True)
def indexer_callback(ctx: typer.Context):
    """Indexer management"""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()

@indexer_app.command("start", no_args_is_help=True)
def indexer_start(
    path: Path = typer.Argument(..., help="Path to the codebase to index."),
    watch: bool = typer.Option(True, "--watch/--no-watch", help="Watch for file changes."),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging."),
    detach: bool = typer.Option(False, "--detach", "-d", help="Run in background.")
):
    """Start the concurrent file watcher for indexing code."""
    from indexer.watcher import Indexer
    from core.config import settings
    from core.clients import init_collection
    import os
    import sys
    import subprocess
    
    level = "DEBUG" if verbose else settings.logging.level
    
    def detach_indexer():
        """Helper to re-spawn the indexer in the background."""
        import subprocess
        # Build command for background process, removing detach flags
        cmd = [sys.executable] + sys.argv
        if "--detach" in cmd: cmd.remove("--detach")
        if "-d" in cmd: cmd.remove("-d")
        
        # Ensure we have a log file for output
        log_file = settings.logging.file_path or Path(os.path.expanduser(f"~/.hivemind/{os.path.basename(os.getcwd())}/hivemind.log"))
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(log_file, "a") as f:
            p = subprocess.Popen(
                cmd,
                stdout=f,
                stderr=f,
                start_new_session=True,
                cwd=os.getcwd()
            )
        
        console.print(f"\n[bold green]Indexer detached and running in background.[/bold green]")
        console.print(f"PID: [cyan]{p.pid}[/cyan]")
        console.print(f"Logs: [cyan]{log_file}[/cyan]")
        raise typer.Exit()

    if detach:
        detach_indexer()

    setup_logging(level, settings.logging.file_path)

    # Ensure collection exists
    init_collection()
    
    indexer = Indexer(console=console)
    try:
        indexer.start(path, watch=watch, detach_callback=detach_indexer)
    except KeyboardInterrupt:
        indexer.stop()
        console.print("[yellow]Indexer stopped by user.[/yellow]")

@indexer_app.command("stop")
def indexer_stop():
    """Stop the background indexer process."""
    from indexer.watcher import Indexer
    indexer = Indexer(console=console)
    pid = indexer.state_manager.get_pid()
    
    if not pid:
        console.print("[yellow]No running indexer found (or no PID file).[/yellow]")
        return
        
    import os
    import signal
    try:
        os.kill(pid, signal.SIGTERM)
        console.print(f"[green]Sent shutdown signal to indexer (PID: {pid})[/green]")
        # Small wait to see if it cleans up
        import time
        for _ in range(5):
            if not indexer.state_manager.pid_file.exists():
                console.print("[bold green]Indexer stopped successfully.[/bold green]")
                return
            time.sleep(0.5)
    except ProcessLookupError:
        console.print("[red]Process not found. Cleaning up stale PID file.[/red]")
        indexer.state_manager.remove_pid()
    except Exception as e:
        console.print(f"[red]Error stopping indexer: {e}[/red]")

@indexer_app.command("clean")
def indexer_clean(
    force: bool = typer.Option(False, "--force", "-f", help="Force deletion without confirmation.")
):
    """Wipe the local state and Qdrant collection for the current project."""
    from core.config import settings
    from core.clients import db
    import shutil
    import os
    
    project_name = os.path.basename(os.getcwd())
    collection_name = settings.qdrant.collection_name
    state_dir = settings.state.directory
    
    console.print(f"[bold red]WARNING:[/bold red] This will delete the Qdrant collection [cyan]'{collection_name}'[/cyan]")
    console.print(f"and wipe all local indexing state in [cyan]'{state_dir}'[/cyan].")
    
    if not force:
        confirm = typer.confirm("Are you sure you want to proceed?")
        if not confirm:
            console.print("[yellow]Aborted.[/yellow]")
            return

    # 1. Delete Qdrant Collection
    with console.status(f"[bold red]Deleting Qdrant collection '{collection_name}'..."):
        try:
            db.delete_collection(collection_name=collection_name)
            console.print(f"[green]✓ Qdrant collection '{collection_name}' deleted.[/green]")
        except Exception as e:
            if "not found" in str(e).lower() or "404" in str(e):
                console.print(f"[yellow]! Collection '{collection_name}' did not exist.[/yellow]")
            else:
                console.print(f"[red]✗ Failed to delete collection: {e}[/red]")

    # 2. Wipe State Directory
    with console.status(f"[bold red]Wiping state directory '{state_dir}'..."):
        try:
            if state_dir.exists():
                shutil.rmtree(state_dir)
                state_dir.mkdir(parents=True, exist_ok=True)
                console.print(f"[green]✓ State directory wiped.[/green]")
            else:
                console.print(f"[yellow]! State directory '{state_dir}' does not exist.[/yellow]")
        except Exception as e:
            console.print(f"[red]✗ Failed to wipe state directory: {e}[/red]")

    console.print("\n[bold green]Index cleaned successfully![/bold green]")
    console.print(f"You can now reindex everything by running: [cyan]hivemind indexer start .[/cyan]")

# Scout Subcommand
scout_app = typer.Typer(help="Manage the web scout (crawler).", no_args_is_help=True)
app.add_typer(scout_app, name="scout")

@scout_app.command("crawl")
def scout_crawl(
    urls: Optional[List[str]] = typer.Argument(None, help="Specific URLs to scout."),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Perform recursive crawling."),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging.")
):
    """Crawl web content and save it for indexing."""
    from scout.manager import ScoutManager
    from core.config import settings
    import asyncio
    
    level = "DEBUG" if verbose else settings.logging.level
    setup_logging(level, settings.logging.file_path)
    
    manager = ScoutManager(console=console)
    asyncio.run(manager.run(urls, recursive=recursive))

# Search Subcommand
@app.command("search", no_args_is_help=True)
def search(
    query: str = typer.Argument(..., help="Semantic search query."),
    limit: int = typer.Option(5, "--limit", help="Number of results to return."),
    verbose: bool = typer.Option(False, "--verbose", help="Show detailed metadata."),
    output_format: str = typer.Option("text", "--format", "-f", help="Output format (text, json).")
):
    """One-off semantic search for terminal testing."""
    from core.clients import db, get_embedding
    from core.config import settings
    import json
    
    setup_logging(settings.logging.level, settings.logging.file_path)
    
    with console.status("[bold green]Searching..."):
        query_vector = get_embedding(query)
        response = db.query_points(
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

# MCP Subcommand
@app.command("mcp")
def mcp_serve():
    """Start the MCP server over standard input/output."""
    from server.server import run_mcp
    run_mcp()

# API Subcommand
@app.command("api", no_args_is_help=True)
def api_serve(
    host: str = typer.Option(None, "--host", help="Host to bind."),
    port: int = typer.Option(None, "--port", help="Port to bind."),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging.")
):
    """Start the REST API server."""
    from server.api import run_api
    from core.config import settings
    
    level = "DEBUG" if verbose else settings.logging.level
    setup_logging(level, settings.logging.file_path)
    
    console.print(f"[bold green]Starting Hivemind API on {host or settings.api.host}:{port or settings.api.port}[/bold green]")
    run_api(host=host, port=port)

# Init Subcommand
@app.command("init", no_args_is_help=False)
def init_project():
    """Initialize a Hivemind project configuration for the current directory."""
    import os
    from pathlib import Path
    
    current_dir_name = os.path.basename(os.getcwd())
    project_dir = Path(os.path.expanduser(f"~/.hivemind/{current_dir_name}"))
    
    try:
        project_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        console.print(f"[red]Failed to create directory {project_dir}: {e}[/red]")
        raise typer.Exit(1)
        
    config_path = project_dir / "config.yaml"
    log_path = project_dir / "hivemind.log"
    
    import yaml
    
    global_config_path = Path(os.path.expanduser("~/.hivemind/config.yaml"))
    
    config_data = {}
    if global_config_path.exists():
        try:
            with open(global_config_path, "r") as f:
                config_data = yaml.safe_load(f) or {}
            console.print(f"[dim]Loaded base config from {global_config_path}[/dim]")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not read global config: {e}[/yellow]")
    else:
        console.print("[yellow]Warning: No global config found at ~/.hivemind/config.yaml. Using empty base.[/yellow]")

    # Ensure nested dictionaries exist
    config_data.setdefault('qdrant', {})
    config_data.setdefault('logging', {})
    
    # Overwrite specific values for this project
    config_data['qdrant']['collection_name'] = current_dir_name
    config_data['logging']['file_path'] = str(log_path)

    try:
        with open(config_path, "w") as f:
            yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)
        console.print(f"[bold green]Successfully initialized project '{current_dir_name}'[/bold green]")
        console.print(f"Configuration saved to: [cyan]{config_path}[/cyan]")
        console.print(f"Logs will be saved to: [cyan]{log_path}[/cyan]")
    except Exception as e:
        console.print(f"[red]Failed to write configuration: {e}[/red]")
        raise typer.Exit(1)

def cli():
    import sys
    # If only 'hivemind' or 'hivemind indexer' is called, append --help
    if len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] == "indexer"):
        sys.argv.append("--help")
    app()

if __name__ == "__main__":
    cli()

