"""In-memory TTL cache for chunked scout results.

Enables the Map-Reduce pattern for ``scout_urls``: an agent first requests a
Table of Contents (mode="toc"), decides which sections are relevant, then
requests only those sections (mode="sections") without re-crawling the URL.
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from typing import Dict, List, Optional

from indexer.chunkers.base import Chunk

logger = logging.getLogger(__name__)

# Default time-to-live for cached chunks (seconds).
DEFAULT_TTL = 600  # 10 minutes


class ChunkCache:
    """Thread-safe in-memory store for chunked web page content.

    Each crawled URL is chunked via :class:`~indexer.chunkers.markdown.MarkdownChunker`
    and stored keyed by a SHA-256 hash of the URL.  Entries expire after *ttl*
    seconds to avoid unbounded memory growth.

    Typical usage::

        cache = get_chunk_cache()
        cache.store("https://example.com", chunks)
        toc = cache.get_toc("https://example.com")
        filtered = cache.get_sections("https://example.com", ["Conversation"])
    """

    def __init__(self, ttl: int = DEFAULT_TTL) -> None:
        self._ttl = ttl
        self._store: Dict[str, tuple[List[Chunk], float]] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def store(self, url: str, chunks: List[Chunk]) -> None:
        """Store chunked content for a URL, overwriting any existing entry."""
        key = _url_key(url)
        with self._lock:
            self._store[key] = (chunks, time.monotonic())
            logger.debug("Cached %d chunks for %s (key=%s)", len(chunks), url, key)

    def get(self, url: str) -> Optional[List[Chunk]]:
        """Return cached chunks for *url*, or ``None`` if missing or expired."""
        self.evict_expired()
        key = _url_key(url)
        with self._lock:
            entry = self._store.get(key)
        if entry is None:
            logger.debug("Cache miss for %s (key=%s)", url, key)
            return None
        logger.debug("Cache hit for %s (key=%s)", url, key)
        return entry[0]

    def evict_expired(self) -> None:
        """Remove entries whose TTL has elapsed."""
        now = time.monotonic()
        with self._lock:
            expired = [
                k for k, (_, ts) in self._store.items()
                if now - ts > self._ttl
            ]
            for k in expired:
                del self._store[k]
        if expired:
            logger.debug("Evicted %d expired cache entries", len(expired))

    def clear(self) -> None:
        """Remove all cached entries (useful for testing)."""
        with self._lock:
            self._store.clear()
            logger.debug("Cache cleared")

    # ------------------------------------------------------------------
    # Formatting helpers (delegate to chunk_formatter when available)
    # ------------------------------------------------------------------

    def get_toc(self, url: str) -> Optional[str]:
        """Return a formatted Table of Contents for the cached URL.

        Returns ``None`` when the URL is not cached or has expired.
        """
        chunks = self.get(url)
        if chunks is None:
            return None
        from scout.chunk_formatter import format_toc
        return format_toc(chunks, url)

    def get_sections(self, url: str, section_names: List[str]) -> Optional[str]:
        """Return formatted content for the named sections of a cached URL.

        Returns ``None`` when the URL is not cached or has expired, or
        a message indicating no sections matched.
        """
        chunks = self.get(url)
        if chunks is None:
            return None
        from scout.chunk_formatter import format_sections
        return format_sections(chunks, url, section_names)

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)


# ------------------------------------------------------------------
# Singleton access
# ------------------------------------------------------------------

_cache: Optional[ChunkCache] = None
_cache_lock = threading.Lock()


def get_chunk_cache() -> ChunkCache:
    """Return the process-wide :class:`ChunkCache` singleton."""
    global _cache
    if _cache is None:
        with _cache_lock:
            if _cache is None:
                _cache = ChunkCache()
    return _cache


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _url_key(url: str) -> str:
    """Derive a short, filesystem-safe cache key from a URL."""
    return hashlib.sha256(url.encode()).hexdigest()[:16]
