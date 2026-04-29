import asyncio
import logging
import os
import hashlib
from pathlib import Path
from typing import List, Optional
from core.config import settings
from .crawler import ScoutCrawler
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

logger = logging.getLogger(__name__)

class ScoutManager:
    def __init__(self, console: Optional[Console] = None, output_dir: Optional[Path] = None):
        self.console = console or Console()
        self.crawler = ScoutCrawler(content_filter=settings.scout.content_filter)
        self.output_dir = output_dir or (settings.workspace_path / settings.scout.output_directory)

    def _url_to_path(self, url: str) -> Path:
        """Convert URL to a structured path relative to output_dir."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        
        # 1. Domain as root folder
        domain = parsed.netloc.replace(".", "_")
        
        # 2. Path segments
        url_path = parsed.path.strip("/")
        if not url_path:
            url_path = "index"
        elif parsed.path.endswith("/"):
            url_path = f"{url_path}/index"
            
        # 3. Handle query params to avoid collisions for same path
        if parsed.query:
            query_hash = hashlib.md5(parsed.query.encode()).hexdigest()[:6]
            url_path = f"{url_path}_{query_hash}"
            
        return Path(domain) / f"{url_path}.md"

    def _save_page(self, page_url: str, content: str, seed_url: Optional[str] = None):
        """Save crawled content to a structured file path."""
        if not content:
            return

        rel_path = self._url_to_path(page_url)
        file_path = self.output_dir / rel_path
        
        # Handle filename conflicts
        if file_path.exists():
            # Add a small hash of the full URL to distinguish
            url_hash = hashlib.md5(page_url.encode()).hexdigest()[:4]
            file_path = file_path.with_name(f"{file_path.stem}_{url_hash}{file_path.suffix}")

        # Ensure parent directories exist
        file_path.parent.mkdir(parents=True, exist_ok=True)

        full_content = f"---\nsource_url: {page_url}\n"
        if seed_url:
            full_content += f"seed_url: {seed_url}\n"
        full_content += "---\n\n" + content

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(full_content)
            logger.info(f"Saved {page_url} to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save {page_url} to {file_path}: {e}")

    async def run(self, urls: Optional[List[str]] = None, recursive: Optional[bool] = None, max_pages: Optional[int] = None, stay_in_path: bool = False):
        """Run the scout on the provided URLs or from config."""
        target_urls = urls or settings.scout.urls
        is_recursive = recursive if recursive is not None else settings.scout.recursive
        limit = max_pages or settings.scout.max_pages_per_domain
        
        if not target_urls:
            self.console.print("[yellow]No URLs to scout. Add them to config.yaml or provide via CLI.[/yellow]")
            return
 
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.console.print(f"[bold cyan]Scout starting for {len(target_urls)} URLs...[/bold cyan]")
        self.console.print(f"[dim]Output directory: {self.output_dir}[/dim]")
 
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console,
            expand=True
        )
 
        with progress:
            task = progress.add_task("[green]Scouting...", total=len(target_urls))
            
            for url in target_urls:
                progress.update(task, description=f"[cyan]Scouting: [dim]{url}[/dim]")
                
                if is_recursive:
                    # For recursive, we get a list of results
                    scanned_pages = await self.crawler.crawl_recursive(
                        url, 
                        max_pages=limit,
                        stay_in_path=stay_in_path
                    )
                    
                    for page_url, content in scanned_pages:
                        self._save_page(page_url, content, seed_url=url)
                else:
                    # Single page crawl
                    content = await self.crawler.crawl_url(url)
                    self._save_page(url, content)
                
                progress.update(task, advance=1)

        self.console.print(f"\n[bold green]Scout complete![/bold green] Files saved to [cyan]{self.output_dir}[/cyan]")
        self.console.print("[dim]The indexer will pick these up automatically if it's running.[/dim]")

def sync_run(urls: Optional[List[str]] = None, recursive: Optional[bool] = None):
    """Sync wrapper for the async run method."""
    manager = ScoutManager()
    asyncio.run(manager.run(urls, recursive=recursive))
