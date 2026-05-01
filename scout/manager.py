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
        self.output_dir = (output_dir or (settings.workspace_path / settings.scout.output_directory)).resolve()
        self.skip_existing = settings.scout.skip_existing

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

    def _expand_urls(self, urls: List[str]) -> List[str]:
        """Expand URLs containing range placeholders like {1..100}."""
        import re
        expanded = []
        for url in urls:
            # Match {start..end}
            match = re.search(r'\{(\d+)\.\.(\d+)\}', url)
            if match:
                start, end = int(match.group(1)), int(match.group(2))
                # Support both increasing and decreasing ranges
                step = 1 if start <= end else -1
                for i in range(start, end + step, step):
                    expanded.append(url.replace(match.group(0), str(i)))
            else:
                expanded.append(url)
        return expanded

    def get_crawled_urls(self) -> List[str]:
        """Scan the output directory and extract source URLs from markdown frontmatter."""
        urls = []
        if not self.output_dir.exists():
            return urls
            
        logger.info(f"Scanning {self.output_dir} for existing URLs...")
        for path in self.output_dir.rglob("*.md"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    # Read first 10 lines to find source_url
                    for _ in range(10):
                        line = f.readline()
                        if not line: break
                        if line.startswith("source_url:"):
                            url = line.split("source_url:")[1].strip()
                            urls.append(url)
                            break
            except Exception:
                continue
        logger.debug(f"Found {len(urls)} existing URLs.")
        return urls

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
            
            # Verify write
            if file_path.exists():
                size = file_path.stat().st_size
                logger.info(f"Saved {page_url} to {file_path} ({size} bytes)")
                if self.console:
                    self.console.print(f"[green]✔[/green] Saved: [dim]{rel_path}[/dim] ({size} bytes)")
            else:
                logger.error(f"Failed to verify write for {file_path}")
        except Exception as e:
            logger.error(f"Failed to save {page_url} to {file_path}: {e}")

    async def run(
        self,
        urls: Optional[List[str]] = None,
        recursive: Optional[bool] = None,
        max_pages: Optional[int] = None,
        stay_in_path: bool = False,
        skip_existing: Optional[bool] = None,
        include_patterns: Optional[List[str]] = None,
        concurrency_limit: Optional[int] = None,
        headless: Optional[bool] = None,
        base_delay: Optional[float] = None
    ):
        """Run the scout on the provided URLs or from config."""
        target_urls = urls or settings.scout.urls
        # Expand any range placeholders like {1..10}
        target_urls = self._expand_urls(target_urls)
        
        is_recursive = recursive if recursive is not None else settings.scout.recursive
        limit = max_pages or settings.scout.max_pages_per_domain
        should_skip = skip_existing if skip_existing is not None else self.skip_existing
        includes = include_patterns if include_patterns else settings.scout.include_patterns
        
        # Re-initialize crawler to pick up overrides.
        # ScoutCrawler normalises base_delay (float → tuple) internally.
        self.crawler = ScoutCrawler(
            content_filter=settings.scout.content_filter,
            concurrency_limit=concurrency_limit,
            headless=headless,
            base_delay=base_delay,
        )
        
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
            
            if is_recursive:
                for url in target_urls:
                    # Basic URL validation
                    if not any(url.startswith(scheme) for scheme in ["http://", "https://", "file://", "raw:"]):
                        logger.warning(f"Skipping invalid URL: '{url}'")
                        progress.update(task, advance=1)
                        continue

                    progress.update(task, description=f"[cyan]Scouting: [dim]{url}[/dim]")
                    
                    # For recursive, we get results incrementally via async generator
                    count = 0
                    exclude_urls = self.get_crawled_urls() if should_skip else None
                    
                    async for page_url, content in self.crawler.crawl_recursive(
                        url, 
                        max_pages=limit,
                        stay_in_path=stay_in_path,
                        include_patterns=includes,
                        exclude_urls=exclude_urls
                    ):
                        logger.info(f"Page discovered: {page_url}")
                        self._save_page(page_url, content, seed_url=url)
                        count += 1
                        progress.update(task, description=f"[cyan]Scouting: [dim]{url}[/dim] (Found {count} pages)")
                    
                    progress.update(task, advance=1)
            else:
                # Batch mode for non-recursive crawls (e.g. ranges)
                if should_skip:
                    existing_urls = set(self.get_crawled_urls())
                    original_count = len(target_urls)
                    target_urls = [u for u in target_urls if u not in existing_urls]
                    skipped = original_count - len(target_urls)
                    if skipped > 0:
                        self.console.print(f"[yellow]Skipping {skipped} already crawled URLs.[/yellow]")
                        progress.update(task, total=len(target_urls))

                if not target_urls:
                    self.console.print("[green]All URLs already crawled. Nothing to do.[/green]")
                    return

                progress.update(task, description=f"[cyan]Batch Scouting [dim]{len(target_urls)} URLs[/dim]")
                
                # Chunking: Process large batches in smaller groups to prevent memory/task overhead
                chunk_size = 100
                for i in range(0, len(target_urls), chunk_size):
                    chunk = target_urls[i:i + chunk_size]
                    logger.info(f"Processing chunk {i // chunk_size + 1} ({len(chunk)} URLs)...")
                    
                    try:
                        async for page_url, content in self.crawler.crawl_batch(chunk):
                            if content:
                                self._save_page(page_url, content)
                            else:
                                logger.warning(f"No content received for {page_url}")
                            progress.update(task, advance=1)
                    except Exception as e:
                        logger.error(f"Fatal error in batch chunk {i // chunk_size + 1}: {e}")
                        # Continue to next chunk
                        continue

        self.console.print(f"\n[bold green]Scout complete![/bold green] Files saved to [cyan]{self.output_dir}[/cyan]")
        self.console.print("[dim]The indexer will pick these up automatically if it's running.[/dim]")

def sync_run(urls: Optional[List[str]] = None, recursive: Optional[bool] = None):
    """Sync wrapper for the async run method."""
    manager = ScoutManager()
    asyncio.run(manager.run(urls, recursive=recursive))
