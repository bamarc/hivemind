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
        """Initialize a Hivemind project configuration for the current directory."""
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
        config_data.setdefault('scout', {})

        # Overwrite specific values for this project
        config_data['qdrant']['collection_name'] = current_dir_name
        config_data['logging']['file_path'] = str(log_path)

        # Ensure scout output goes into .hivemind
        config_data.setdefault('scout', {})
        config_data['scout']['output_directory'] = '.hivemind/scout'

        try:
            with open(config_path, "w") as f:
                yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)
            console.print(f"[bold green]Successfully initialized project '{current_dir_name}'[/bold green]")
            console.print(f"Configuration saved to: [cyan]{config_path}[/cyan]")
            console.print(f"Logs will be saved to: [cyan]{log_path}[/cyan]")
        except Exception as e:
            console.print(f"[red]Failed to write configuration: {e}[/red]")
            raise typer.Exit(1)

        # Create scout output directory if scout URLs are configured
        scout_urls = config_data.get('scout', {}).get('urls', [])
        if scout_urls:
            scout_dir = project_dir / "scout"
            try:
                scout_dir.mkdir(parents=True, exist_ok=True)
                console.print(f"Scout output directory created: [cyan]{scout_dir}[/cyan]")
            except Exception as e:
                console.print(f"[yellow]Warning: Could not create scout directory: {e}[/yellow]")

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
