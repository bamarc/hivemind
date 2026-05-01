import typer


def register(app: typer.Typer):
    """Register server commands on the main app."""
    from main import console, setup_logging

    @app.command("mcp")
    def mcp_serve():
        """Start the MCP server over standard input/output."""
        from server.server import run_mcp
        run_mcp()

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
