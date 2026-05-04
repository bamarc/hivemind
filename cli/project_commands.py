import typer


def register(app: typer.Typer):
    """Register project management commands on the main app."""
    from main import console

    @app.command("setup")
    def setup():
        """Run the interactive setup wizard to configure Hivemind."""
        from cli.setup import setup_wizard
        setup_wizard()

    @app.command("init", no_args_is_help=False)
    def init_project():
        """Initialize a Hivemind project configuration for the current directory.

        Creates a minimal ``.hivemind/config.yaml`` with only project-specific
        settings (collection name, log path, scout output directory). Model
        configuration, API keys, and other global settings are inherited from
        ``~/.hivemind/config.yaml`` at runtime (see :mod:`core.config`).
        """
        import os
        from pathlib import Path

        current_dir_name = os.path.basename(os.getcwd())
        project_dir = Path(".hivemind")

        try:
            project_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            console.print(f"[red]Failed to create directory {project_dir}: {e}[/red]")
            raise typer.Exit(1)

        config_path = project_dir / "config.yaml"
        log_path = project_dir / "hivemind.log"

        import yaml

        # Only write project-specific overrides.
        # Model/chat/qdrant URL/API keys are inherited from
        # ~/.hivemind/config.yaml at config-load time.
        config_data = {
            "qdrant": {
                "collection_name": current_dir_name,
            },
            "logging": {
                "file_path": str(log_path),
            },
            "scout": {
                "output_directory": ".hivemind/scout",
            },
        }

        try:
            with open(config_path, "w") as f:
                yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)
            console.print(f"[bold green]Successfully initialized project '{current_dir_name}'[/bold green]")
            console.print(f"Configuration saved to: [cyan]{config_path}[/cyan]")
            console.print(f"Logs will be saved to: [cyan]{log_path}[/cyan]")
        except Exception as e:
            console.print(f"[red]Failed to write configuration: {e}[/red]")
            raise typer.Exit(1)

        # Ensure .hivemind is in .gitignore
        gitignore_path = Path(".gitignore")
        if gitignore_path.exists():
            try:
                gitignore_content = gitignore_path.read_text()
                if ".hivemind" not in gitignore_content:
                    with open(gitignore_path, "a") as f:
                        if not gitignore_content.endswith("\n"):
                            f.write("\n")
                        f.write("# Hivemind local state\n.hivemind/\n")
                    console.print("[green]Added .hivemind/ to .gitignore[/green]")
                else:
                    console.print("[dim].hivemind/ already in .gitignore[/dim]")
            except Exception as e:
                console.print(f"[yellow]Warning: Could not update .gitignore: {e}[/yellow]")
