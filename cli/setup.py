import os
import subprocess
import yaml
from pathlib import Path
from typing import Dict, Any
from rich.console import Console
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.panel import Panel

console = Console()

def run_command(command: list, description: str):
    """Run a shell command and show progress."""
    with console.status(f"[bold green]{description}..."):
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            return True, result.stdout
        except subprocess.CalledProcessError as e:
            return False, e.stderr
        except Exception as e:
            return False, str(e)

def setup_wizard():
    console.clear()
    console.print(Panel(
        "[bold cyan]Hivemind System Setup[/bold cyan]\n"
        "This wizard will configure your global environment and dependencies.",
        title="🧙 Wizard",
        border_style="cyan"
    ))

    # 1. Prepare Directory
    config_dir = Path(os.path.expanduser("~/.hivemind"))
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.yaml"

    # Load existing config if available
    current_config = {}
    if config_file.exists():
        try:
            with open(config_file, "r") as f:
                current_config = yaml.safe_load(f) or {}
        except Exception:
            pass

    # 2. Qdrant Setup
    console.print("\n[bold cyan]Step 1: Vector Database (Qdrant)[/bold cyan]")
    run_qdrant_locally = Confirm.ask("Do you want to run Qdrant locally using Docker?", default=True)
    
    qdrant_url = current_config.get("qdrant", {}).get("url", "http://localhost:6333")
    if run_qdrant_locally:
        success, _ = run_command(["docker", "--version"], "Checking for Docker")
        if not success:
            console.print("[red]Error: Docker is not installed or not in PATH.[/red]")
            run_qdrant_locally = False
        else:
            # Check if container is already running
            _, running = run_command(["docker", "ps", "--filter", "name=hivemind-qdrant", "--format", "{{.Names}}"], "Checking for existing Qdrant container")
            if "hivemind-qdrant" not in running:
                console.print("[yellow]Starting Qdrant container...[/yellow]")
                success, err = run_command([
                    "docker", "run", "-d", 
                    "--name", "hivemind-qdrant",
                    "-p", "6333:6333", 
                    "-p", "6334:6334",
                    "-v", f"{config_dir}/qdrant_storage:/qdrant/storage",
                    "--restart", "unless-stopped",
                    "qdrant/qdrant"
                ], "Starting Qdrant")
                if success:
                    console.print("[green]✓ Qdrant is running at http://localhost:6333[/green]")
                else:
                    console.print(f"[red]Failed to start Qdrant: {err}[/red]")
                    run_qdrant_locally = False
            else:
                console.print("[green]✓ Qdrant container 'hivemind-qdrant' is already running.[/green]")
            qdrant_url = "http://localhost:6333"

    if not run_qdrant_locally:
        qdrant_url = Prompt.ask("Enter your Qdrant URL", default=qdrant_url)

    # 3. Embedding Model Setup
    console.print("\n[bold cyan]Step 2: Embedding Model[/bold cyan]")
    console.print("[dim]Used for indexing code. Works best with LM Studio or OpenAI.[/dim]")
    model_url = Prompt.ask("Embedding API URL", default=current_config.get("model", {}).get("api_url", "http://localhost:1234/v1"))
    model_name = Prompt.ask("Model Name", default=current_config.get("model", {}).get("model_name", "qwen3-4B-embedding"))
    model_dim = IntPrompt.ask("Embedding Dimensions", default=current_config.get("model", {}).get("embedding_dim", 2500))
    model_key = Prompt.ask("API Key (optional)", password=True, default=current_config.get("model", {}).get("api_key", ""))

    # 4. LLM Chat Setup
    console.print("\n[bold cyan]Step 3: LLM Chat Setup[/bold cyan]")
    console.print("[dim]Used for reasoning and searching.[/dim]")
    chat_url = Prompt.ask("Chat API URL", default=current_config.get("chat", {}).get("api_url", "http://localhost:1234/v1"))
    chat_name = Prompt.ask("Chat Model Name", default=current_config.get("chat", {}).get("model_name", "gpt-4o"))

    # 5. Scout Setup
    console.print("\n[bold cyan]Step 4: Web Scout Defaults[/bold cyan]")
    scout_recursive = Confirm.ask("Enable recursive scouting by default?", default=current_config.get("scout", {}).get("recursive", False))
    scout_pages = IntPrompt.ask("Default max pages per domain", default=current_config.get("scout", {}).get("max_pages_per_domain", 50))

    # 6. Build Final Config
    config = {
        "qdrant": {
            "url": qdrant_url,
            "collection_name": current_config.get("qdrant", {}).get("collection_name", "hivemind_code")
        },
        "model": {
            "api_url": model_url,
            "model_name": model_name,
            "embedding_dim": model_dim
        },
        "chat": {
            "api_url": chat_url,
            "model_name": chat_name
        },
        "scout": {
            "recursive": scout_recursive,
            "max_pages_per_domain": scout_pages,
            "output_directory": "docs/scout",
            "content_filter": True
        },
        "logging": {
            "level": "INFO"
        }
    }
    
    if model_key:
        config["model"]["api_key"] = model_key

    # Save Config
    with open(config_file, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    console.print(f"\n[bold green]✨ Configuration saved to {config_file}[/bold green]")
    
    if Confirm.ask("\nDo you want to initialize a project in the current directory now?"):
        # Delayed import to avoid circular dependencies if called from main
        import main
        main.init_project()

if __name__ == "__main__":
    setup_wizard()
