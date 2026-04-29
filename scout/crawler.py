import asyncio
import logging
from pathlib import Path
from typing import List, Optional
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
from crawl4ai.deep_crawling.filters import FilterChain, URLPatternFilter

logger = logging.getLogger(__name__)

class ScoutCrawler:
    def __init__(self, content_filter: bool = True):
        self.run_config = CrawlerRunConfig(
            markdown_generator=DefaultMarkdownGenerator(
                content_filter=PruningContentFilter() if content_filter else None
            )
        )

    async def crawl_url(self, url: str) -> Optional[str]:
        """Crawl a single URL and return markdown content."""
        logger.info(f"Scouting URL: {url}")
        try:
            async with AsyncWebCrawler() as crawler:
                result = await crawler.arun(url, config=self.run_config)
                if result.success:
                    # Use fit_markdown if available, otherwise raw markdown
                    if hasattr(result, 'markdown_v2') and result.markdown_v2:
                        if hasattr(result.markdown_v2, 'fit_markdown') and result.markdown_v2.fit_markdown:
                            return result.markdown_v2.fit_markdown
                    return result.markdown
                else:
                    logger.error(f"Failed to crawl {url}: {result.error_message}")
                    return None
        except Exception as e:
            logger.error(f"Error crawling {url}: {e}")
            return None

    async def crawl_urls(self, urls: List[str]) -> List[tuple[str, str]]:
        """Crawl multiple URLs and return list of (url, markdown) pairs."""
        results = []
        async with AsyncWebCrawler() as crawler:
            for url in urls:
                logger.info(f"Scouting URL: {url}")
                try:
                    result = await crawler.arun(url, config=self.run_config)
                    if result.success:
                        content = result.markdown
                        if hasattr(result, 'markdown_v2') and result.markdown_v2:
                            if hasattr(result.markdown_v2, 'fit_markdown') and result.markdown_v2.fit_markdown:
                                content = result.markdown_v2.fit_markdown
                        results.append((url, content))
                    else:
                        logger.warning(f"Skipping {url} due to error: {result.error_message}")
                except Exception as e:
                    logger.error(f"Error crawling {url}: {e}")
        return results

    async def crawl_recursive(self, url: str, max_pages: int = 50, max_depth: int = 3, stay_in_path: bool = False) -> List[tuple[str, str]]:
        """Perform recursive crawling starting from a seed URL."""
        logger.info(f"Scouting recursively starting from: {url} (max pages: {max_pages}, max depth: {max_depth}, stay_in_path: {stay_in_path})")
        results = []
        
        try:
            # Setup path filter if requested
            filter_chain = None
            if stay_in_path:
                # Use a wildcard to match any URL starting with the seed URL
                # We handle both with and without trailing slash for the base
                pattern = f"*{url.rstrip('/')}*"
                filter_chain = FilterChain([URLPatternFilter(patterns=[pattern])])

            strategy = BFSDeepCrawlStrategy(
                max_depth=max_depth, 
                max_pages=max_pages,
                include_external=False,
                filter_chain=filter_chain
            )
            
            # Create a specific config for this recursive run that includes the strategy
            recursive_config = CrawlerRunConfig(
                markdown_generator=self.run_config.markdown_generator,
                deep_crawl_strategy=strategy
            )

            async with AsyncWebCrawler() as crawler:
                # arun returns a single list of CrawlResult when strategy is provided in config
                crawl_results = await crawler.arun(
                    url, 
                    config=recursive_config
                )
                
                if isinstance(crawl_results, list):
                    for result in crawl_results:
                        if result.success:
                            content = result.markdown
                            if hasattr(result, 'markdown_v2') and result.markdown_v2:
                                if hasattr(result.markdown_v2, 'fit_markdown') and result.markdown_v2.fit_markdown:
                                    content = result.markdown_v2.fit_markdown
                            results.append((result.url, content))
                else:
                    # Fallback for single result
                    if crawl_results.success:
                        content = crawl_results.markdown
                        if hasattr(crawl_results, 'markdown_v2') and crawl_results.markdown_v2:
                            if hasattr(crawl_results.markdown_v2, 'fit_markdown') and crawl_results.markdown_v2.fit_markdown:
                                content = crawl_results.markdown_v2.fit_markdown
                        results.append((crawl_results.url, content))
                        
        except Exception as e:
            logger.error(f"Error during recursive crawl of {url}: {e}")
            
        return results
