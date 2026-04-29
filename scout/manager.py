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
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self.crawler = ScoutCrawler(content_filter=settings.scout.content_filter)
        self.output_dir = settings.workspace_path / settings.scout.output_directory

    def _url_to_filename(self, url: str) -> str:
        """Convert URL to a safe filename."""
        # Use MD5 of URL to keep it short but unique, prefixed with domain
        domain = url.split("//")[-1].split("/")[0].replace(".", "_")
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        return f"{domain}_{url_hash}.md"

    async def run(self, urls: Optional[List[str]] = None, recursive: Optional[bool] = None, max_pages: Optional[int] = None):
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
                        max_pages=limit
                    )
                    
                    for page_url, content in scanned_pages:
                        if content:
                            filename = self._url_to_filename(page_url)
                            file_path = self.output_dir / filename
                            full_content = f"---\nsource_url: {page_url}\nseed_url: {url}\n---\n\n{content}"
                            with open(file_path, "w", encoding="utf-8") as f:
                                f.write(full_content)
                            logger.info(f"Saved {page_url} to {file_path}")
                else:
                    # Single page crawl
                    content = await self.crawler.crawl_url(url)
                    if content:
                        filename = self._url_to_filename(url)
                        file_path = self.output_dir / filename
                        full_content = f"---\nsource_url: {url}\n---\n\n{content}"
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(full_content)
                        logger.info(f"Saved {url} to {file_path}")
                
                progress.update(task, advance=1)

        self.console.print(f"\n[bold green]Scout complete![/bold green] Files saved to [cyan]{self.output_dir}[/cyan]")
        self.console.print("[dim]The indexer will pick these up automatically if it's running.[/dim]")

def sync_run(urls: Optional[List[str]] = None, recursive: Optional[bool] = None):
    """Sync wrapper for the async run method."""
    manager = ScoutManager()
    asyncio.run(manager.run(urls, recursive=recursive))
