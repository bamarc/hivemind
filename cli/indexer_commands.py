import typer
from pathlib import Path


def register(parent_app: typer.Typer):
    """Register indexer subcommands on the parent app."""
    from main import console, setup_logging

    indexer_app = typer.Typer(help="Manage the code indexer.", no_args_is_help=True)
    parent_app.add_typer(indexer_app, name="indexer")

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
        from core.clients import get_db
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
                get_db().delete_collection(collection_name=collection_name)
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
