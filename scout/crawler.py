import asyncio
import logging
from pathlib import Path
from typing import List, Optional, AsyncGenerator, Any
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig, RateLimiter
from crawl4ai.async_dispatcher import MemoryAdaptiveDispatcher
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
from crawl4ai.deep_crawling.filters import FilterChain, URLPatternFilter

logger = logging.getLogger(__name__)


def _extract_best_markdown(result: Any) -> str:
    """Extract the best available Markdown from a crawl result.

    Prefers ``markdown_v2.fit_markdown`` when available, falling back
    to ``result.markdown``.
    """
    content: str = result.markdown or ""
    if hasattr(result, "markdown_v2") and result.markdown_v2:
        mv2 = result.markdown_v2
        if hasattr(mv2, "fit_markdown") and mv2.fit_markdown:
            content = mv2.fit_markdown
    return content


class ScoutCrawler:
    def __init__(
        self,
        content_filter: bool = True,
        concurrency_limit: int | None = None,
        headless: bool | None = None,
        base_delay: float | tuple[float, float] | None = None,
    ):
        from core.config import settings
        self.browser_config = BrowserConfig(
            enable_stealth=settings.scout.use_stealth,
            headless=headless if headless is not None else settings.scout.headless,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        self.run_config = CrawlerRunConfig(
            markdown_generator=DefaultMarkdownGenerator(
                content_filter=PruningContentFilter() if content_filter else None
            ),
            magic=True
        )
        self._concurrency_limit = concurrency_limit if concurrency_limit is not None else settings.scout.concurrency_limit

        # Normalise base_delay: a plain float becomes (delay, delay*2).
        if base_delay is None:
            self._base_delay = settings.scout.base_delay
        elif isinstance(base_delay, (int, float)):
            self._base_delay = (float(base_delay), float(base_delay) * 2)
        else:
            self._base_delay = base_delay

    async def crawl_url(self, url: str) -> Optional[str]:
        """Crawl a single URL and return markdown content."""
        results = []
        async for u, content in self.crawl_batch([url]):
            results.append(content)
        return results[0] if results else None

    async def crawl_batch(self, urls: List[str]) -> AsyncGenerator[tuple[str, str], None]:
        """Crawl multiple URLs in parallel and yield results incrementally."""
        # Use a fresh config with streaming enabled
        batch_config = CrawlerRunConfig(
            markdown_generator=self.run_config.markdown_generator,
            stream=True,
            magic=True
        )
        
        # Setup rate limiter and dispatcher for "polite" crawling
        rate_limiter = RateLimiter(
            base_delay=self._base_delay,
            max_delay=60.0,
            max_retries=3
        )
        dispatcher = MemoryAdaptiveDispatcher(
            max_session_permit=self._concurrency_limit,
            rate_limiter=rate_limiter
        )
        
        logger.info(f"Starting batch crawl of {len(urls)} URLs (Concurrency: {self._concurrency_limit}, Delay: {self._base_delay})")
        async with AsyncWebCrawler(config=self.browser_config) as crawler:
            # arun_many returns an async iterator when stream=True
            async for result in await crawler.arun_many(urls, config=batch_config, dispatcher=dispatcher):
                if result.success:
                    logger.info(f"Successfully crawled: {result.url}")
                    content = _extract_best_markdown(result)
                    yield result.url, content
                else:
                    logger.warning(f"Failed to crawl {result.url}: {result.error_message}")

    async def crawl_urls(self, urls: List[str]) -> List[tuple[str, str]]:
        """Crawl multiple URLs and return list of (url, markdown) pairs."""
        results = []
        async with AsyncWebCrawler(config=self.browser_config) as crawler:
            for url in urls:
                logger.info(f"Scouting URL: {url}")
                try:
                    result = await crawler.arun(url, config=self.run_config)
                    if result.success:
                        content = _extract_best_markdown(result)
                        results.append((url, content))
                    else:
                        logger.warning(f"Skipping {url} due to error: {result.error_message}")
                except Exception as e:
                    logger.error(f"Error crawling {url}: {e}")
        return results

    async def crawl_recursive(
        self, 
        url: str, 
        max_pages: int = 50, 
        max_depth: int = 3, 
        stay_in_path: bool = False,
        include_patterns: Optional[List[str]] = None,
        exclude_urls: Optional[List[str]] = None
    ) -> AsyncGenerator[tuple[str, str], None]:
        """Perform recursive crawling starting from a seed URL and yield results incrementally."""
        logger.info(f"Scouting recursively starting from: {url} (max pages: {max_pages}, max depth: {max_depth}, stay_in_path: {stay_in_path})")
        
        try:
            # Setup filter chain
            filters = []
            
            # 1. Inclusion patterns (OR logic)
            inclusion_patterns = []
            if stay_in_path:
                inclusion_patterns.append(f"*{url.rstrip('/')}*")
            if include_patterns:
                inclusion_patterns.extend(include_patterns)
                
            if inclusion_patterns:
                filters.append(URLPatternFilter(patterns=inclusion_patterns))
                
            # 3. Exclude already crawled URLs if provided
            if exclude_urls and len(exclude_urls) < 1000: # Limit to avoid performance issues
                # Using reverse=True for exclusion
                filters.append(URLPatternFilter(patterns=exclude_urls, reverse=True))

            filter_chain = FilterChain(filters) if filters else None

            # Strategy parameters
            strategy_kwargs = {
                "max_depth": max_depth,
                "max_pages": max_pages,
                "include_external": False
            }
            if filter_chain:
                strategy_kwargs["filter_chain"] = filter_chain

            strategy = BFSDeepCrawlStrategy(**strategy_kwargs)
            
            # Create a specific config for this recursive run that includes the strategy and streaming
            recursive_config = CrawlerRunConfig(
                markdown_generator=self.run_config.markdown_generator,
                deep_crawl_strategy=strategy,
                stream=True,
                magic=True,
                semaphore_count=self._concurrency_limit
            )

            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                # arun returns an async iterator when stream=True is provided in config
                logger.info(f"Starting streamed crawl for {url}... (Concurrency limit: {self._concurrency_limit})")
                iterator = await crawler.arun(
                    url, 
                    config=recursive_config
                )
                
                async for result in iterator:
                    logger.debug(f"Crawl result received for {result.url} (success: {result.success})")
                    if result.success:
                        content = _extract_best_markdown(result)
                        yield result.url, content
                        
        except Exception as e:
            logger.error(f"Error during recursive crawl of {url}: {e}")
