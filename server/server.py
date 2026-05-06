import os
import sys
import logging
from mcp.server.fastmcp import FastMCP
from core.clients import get_db, get_embedding, get_chat_client, text_to_sparse_vector
from core.config import settings
from core.complexity import get_complexity
from core.filesystem import get_file_tree as core_get_file_tree, file_contents
from core.planner import generate_blueprint as core_generate_blueprint, BlueprintError
from core.search import search_web as core_search_web

# Configure logging to stderr for MCP
logging.basicConfig(
    level=settings.logging.level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

mcp = FastMCP("HivemindServer")

from qdrant_client import models

@mcp.tool()
def semantic_code_search(
    query: str,
    limit: int = 5,
    root_path: str = None,
    file_filter: str = None,
    language: str = None,
    is_test: bool = None,
    mode: str = "auto",
) -> str:
    """
    PRIMARY tool for code discovery. Find code by meaning, not by filename.
    
    Use this when you know what the code DOES but not where it lives.
    This is ALWAYS preferred over manually reading files to locate logic.
    It searches the vector index using natural language understanding,
    so you can ask questions like "where is password hashing handled?"
    or "find the database connection pooling logic."
    
    Args:
        query: Natural language description of the functionality, concept, or logic you are looking for. Phrase it as a question or a description (e.g., "user authentication flow", "how are embeddings generated?").
        limit: Maximum number of results to return (default 5, max 20).
        root_path: Project root path. Only needed if searching a different project than the current workspace. Auto-detected from workspace by default.
        file_filter: Filter results to files whose path contains this substring (e.g., "server/" for server code, "test_" for test files).
        language: Programming language to filter by (e.g., "python", "typescript", "rust"). Leave empty for all languages.
        is_test: Set True to return only test files, False to exclude test files, None (default) for no filter.
        mode: Search mode — "auto" or "dense" (pure vector, default), "sparse" (keyword-based), "hybrid" (dense + sparse fused via RRF).
    """
    try:
        from pathlib import Path
        root = Path(root_path) if root_path else settings.workspace_path
        collection_name = root.name if root_path else settings.qdrant.collection_name

        logger.info(f"Executing semantic search in '{collection_name}' for: '{query}' (mode={mode})")
        query_vector = get_embedding(query)

        # Build Qdrant filter
        must_filters = []
        if file_filter:
            must_filters.append(models.FieldCondition(
                key="filepath",
                match=models.MatchText(text=file_filter)
            ))
        if language:
            must_filters.append(models.FieldCondition(
                key="language",
                match=models.MatchValue(value=language)
            ))
        if is_test is not None:
            must_filters.append(models.FieldCondition(
                key="is_test",
                match=models.MatchValue(value=is_test)
            ))

        search_filter = models.Filter(must=must_filters) if must_filters else None

        if mode == "hybrid":
            # Hybrid: dense + sparse with RRF fusion
            sparse_vector = text_to_sparse_vector(query)

            response = get_db().query_points(
                collection_name=collection_name,
                prefetch=[
                    models.Prefetch(
                        query=query_vector,
                        limit=limit * 2,
                        filter=search_filter,
                    ),
                    models.Prefetch(
                        query=models.SparseVector(
                            indices=sparse_vector.indices,
                            values=sparse_vector.values,
                        ),
                        using="code-sparse",
                        limit=limit * 2,
                        filter=search_filter,
                    ),
                ],
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=limit,
            )
        elif mode == "sparse":
            # Pure sparse (keyword) search using TF-hashing
            sparse_vector = text_to_sparse_vector(query)

            response = get_db().query_points(
                collection_name=collection_name,
                query=models.SparseVector(
                    indices=sparse_vector.indices,
                    values=sparse_vector.values,
                ),
                using="code-sparse",
                limit=limit,
                query_filter=search_filter,
            )
        else:
            # "auto" or "dense" — pure vector search (backward compatible)
            response = get_db().query_points(
                collection_name=collection_name,
                query=query_vector,
                limit=limit,
                query_filter=search_filter,
            )
        search_results = response.points

        if not search_results:
            return f"No relevant code found in collection '{collection_name}'."

        formatted_results = [f"# Semantic Search Results (Collection: {collection_name})\n"]
        for hit in search_results:
            filepath = hit.payload.get("filepath", "Unknown File")
            content = hit.payload.get("content", "")
            language_hit = hit.payload.get("language", "text")
            
            result = f"### {filepath} (Score: {hit.score:.2f})\n"
            result += f"```{language_hit}\n"
            result += f"{content}\n"
            result += "```\n"
            formatted_results.append(result)

        return "\n".join(formatted_results)

    except Exception as e:
        logger.error(f"Error executing semantic search: {e}")
        return f"Error executing semantic search: {str(e)}"

# ---------------------------------------------------------------------------
# RAG-Style Code Q&A — delegates to core/rag.py
# ---------------------------------------------------------------------------
from core.rag import ask_codebase as _ask_codebase


@mcp.tool()
def answer_code_question(
    question: str,
    context: str = "",
    max_chunks: int = 5,
    project_path: str = None,
) -> str:
    """
    Answer a natural-language question about the codebase using
    retrieval-augmented generation (RAG).

    Retrieves relevant code chunks via semantic search and synthesizes
    an answer using the configured chat model. Returns the answer with
    filepath citations.

    Args:
        question: The natural language question about the codebase
            (e.g., "How does user authentication work?").
        context: Optional extra context about what you're trying to
            accomplish (e.g., "I'm adding OAuth support").
        max_chunks: Maximum number of code chunks to retrieve (default 5).
        project_path: Project root path for the search scope.
            Auto-detected from workspace by default.
    """
    try:
        answer, citations = _ask_codebase(
            question,
            context=context,
            max_chunks=max_chunks,
            project_path=project_path,
        )
        return f"## Answer\n\n{answer}\n\n## Sources\n\n{citations}"
    except ValueError as e:
        return str(e)
    except Exception as e:
        logger.error(f"Error in answer_code_question: {e}")
        return f"Error answering question: {str(e)}"


@mcp.tool()
def get_file_tree(root_path: str = None, depth: int = 2) -> str:
    """
    Get a structural overview of the project directory tree.
    
    Use this ONLY for understanding project layout (directory names, file organization).
    For finding specific logic, features, or implementations, ALWAYS use semantic_code_search instead.
    Reading individual files to search for logic is inefficient — semantic_code_search is faster and more accurate.
    
    Args:
        root_path: Project root path. Auto-detected from workspace by default.
        depth: Directory tree depth (default 2). Increase to see deeper nesting.
    """
    from pathlib import Path

    root = Path(root_path) if root_path else settings.workspace_path
    root = root.absolute()

    if not root.exists():
        return f"Error: Path {root} does not exist."

    return core_get_file_tree(str(root), depth)

@mcp.tool()
def get_index_status(root_path: str = None) -> str:
    """
    Check if the semantic search index is ready for a project.
    
    Call this if semantic_code_search returns a "not indexed" message.
    The index is built asynchronously — if it's not ready, use start_indexing.
    
    Args:
        root_path: Project root path. Auto-detected from workspace by default.
    """
    import uuid
    from pathlib import Path
    from qdrant_client import models
    
    root = Path(root_path) if root_path else settings.workspace_path
    root = root.absolute()
    
    # Collection name logic: defaults to current settings,
    # but we could try to detect it if root_path is different.
    # For now, we assume the collection name matches the project folder name.
    collection_name = root.name if root_path else settings.qdrant.collection_name
    
    meta_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{root}_indexing_metadata"))
    try:
        points = get_db().retrieve(
            collection_name=collection_name,
            ids=[meta_id]
        )
        if not points:
            return f"Status: Not Indexed. Workspace: {root}\nCollection: {collection_name}\nUse start_indexing to begin."
        
        payload = points[0].payload
        status = "Complete" if payload.get("indexing_complete") else "In Progress / Stale"
        last_indexed = payload.get("last_indexed_at", "Unknown")
        return (
            f"Status: {status}\n"
            f"Last Indexed: {last_indexed}\n"
            f"Workspace: {root}\n"
            f"Collection: {collection_name}"
        )
    except Exception as e:
        logger.error(f"Error retrieving index status: {e}")
        return f"Error retrieving status for {root}: {str(e)}"

@mcp.tool()
def start_indexing(root_path: str = None) -> str:
    """
    Start building the semantic search index for a project.
    
    Required before semantic_code_search can return results.
    Runs in the background — use get_index_status to monitor progress.
    You only need to call this once per project (or after code changes).
    
    Args:
        root_path: Project root path. Auto-detected from workspace by default.
    """
    import subprocess
    import os
    from pathlib import Path
    
    root = Path(root_path) if root_path else settings.workspace_path
    root = root.absolute()
    
    if not root.exists():
        return f"Error: Path {root} does not exist."
    
    try:
        # Trigger the CLI indexer in detached mode.
        cmd = ["hivemind", "indexer", "start", str(root), "--detach"]
        
        p = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            cwd=str(root)
        )

        # Persist the PID so it can be tracked externally (e.g. for
        # graceful shutdown or monitoring).
        pid_dir = settings.state.directory
        pid_dir.mkdir(parents=True, exist_ok=True)
        pid_file = pid_dir / "server_spawned_indexer.pid"
        pid_file.write_text(f"{p.pid}\n{root}\n")
        
        return (
            f"Indexing started for {root} (PID: {p.pid}). "
            f"Use get_index_status to check progress."
        )
    except FileNotFoundError:
        return (
            "Error: 'hivemind' CLI not found. Ensure the project is "
            "installed (uv sync) and the hivemind script is on PATH."
        )
    except Exception as e:
        logger.error(f"Error starting indexer: {e}")
        return f"Error starting indexer: {str(e)}"
@mcp.tool()
def analyze_code_complexity(filepath: str) -> str:
    """
    Calculate complexity metrics for a file (AST depth, dependencies, etc.).
    Use this to decide if a task should be handled by a small or flagship model.
    """
    import json
    result = get_complexity(filepath)
    if "error" in result:
        return f"Error: {result['error']}"
    
    # Format for readability
    score = result['complexity_score']
    triage = "Escalate to Flagship" if score > 50 else "Suitable for Small/Local Model"
    
    return (
        f"## Complexity Analysis: {os.path.basename(filepath)}\n"
        f"- **Score**: {score} ({triage})\n"
        f"- **AST Depth**: {result['max_depth']}\n"
        f"- **Definitions**: {result['def_count']}\n"
        f"- **Imports**: {result['import_count']}\n"
        f"- **Lines**: {result['line_count']}\n"
    )

@mcp.tool()
def generate_blueprint(task: str, context: str) -> str:
    """
    Generate a structured JSON blueprint for a coding task using a flagship model.
    """
    import json
    try:
        blueprint = core_generate_blueprint(task, context)
        return json.dumps(blueprint, indent=2)
    except BlueprintError as e:
        return json.dumps({"error": str(e)}, indent=2)

@mcp.tool()
def run_verification(filepath: str = None) -> str:
    """
    Run linters and tests for the project or a specific file.
    """
    import subprocess
    import os
    
    root = settings.workspace_path
    
    # Detect project type
    if (root / "package.json").exists():
        cmd = ["npm", "test"]
    elif (root / "pyproject.toml").exists() or (root / "pytest.ini").exists():
        cmd = ["uv", "run", "pytest"]
        if filepath:
            cmd.append(filepath)
    else:
        return "Error: Could not detect test runner (no package.json or pyproject.toml found)."
        
    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            cwd=str(root),
            timeout=60
        )
        
        status = "PASSED" if result.returncode == 0 else "FAILED"
        output = result.stdout + result.stderr
        
        # Keep output concise
        if len(output) > 2000:
            output = output[:1000] + "\n... [TRUNCATED] ...\n" + output[-1000:]
            
        return f"### Verification {status}\nCommand: `{' '.join(cmd)}`\n\n```\n{output}\n```"
    except subprocess.TimeoutExpired:
        return "Error: Verification timed out after 60 seconds."
    except Exception as e:
        return f"Error running verification: {str(e)}"

@mcp.tool()
def search_web(
    query: str,
    max_results: int = 10,
    categories: list[str] | None = None,
) -> str:
    """
    Search the web using DuckDuckGo and return structured results.

    Use this to find documentation, API references, or solutions for
    programming questions. Returns title, URL, and snippet for each result.

    To get full page content from a result URL, use the scout_urls tool.

    Args:
        query: The search query string (e.g., "python asyncio gather documentation").
        max_results: Maximum number of results to return (default 10, max 20).
        categories: Optional list of search categories (SearXNG backend only).
            Common categories: general, science, it, news, files, images, videos,
            music, social media, map. Ignored by DuckDuckGo backend.
    """
    try:
        results = core_search_web(query, max_results=max_results, categories=categories)

        if not results:
            return f"No web results found for: {query}"

        lines = [f"# Web Search Results for: {query}\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"## {i}. {r.title}")
            lines.append(f"- **URL**: {r.url}")
            lines.append(f"- **Snippet**: {r.snippet}")
            lines.append("")

        return "\n".join(lines)

    except ImportError as e:
        return (
            f"Error: {e}\n\n"
            "The search_web tool requires the 'ddgs' package.\n"
            "Install it with: `uv sync --extra scout`"
        )
    except Exception as e:
        logger.error(f"Error in search_web: {e}")
        return f"Error searching the web: {str(e)}"


@mcp.tool()
async def scout_urls(
    urls: list[str],
    max_results: int = 3,
    mode: str = "full",
    sections: dict[str, list[str]] | None = None,
) -> str:
    """
    Crawl one or more URLs and return their content as markdown.

    Use this after search_web to get full page content from result URLs.
    Multiple URLs are crawled in parallel and returned in a single response
    to reduce token overhead.

    When used with ``mode="toc"``, returns a Table of Contents showing all
    sections of the page with estimated token counts — the agent can then
    request only the relevant sections with ``mode="sections"``.

    Args:
        urls: List of URLs to crawl (e.g., ["https://docs.python.org/3/library/asyncio.html"]).
        max_results: Maximum number of URLs to crawl (default 3, max 10, safety limit).
        mode: One of ``"full"`` (default, raw markdown with truncation),
            ``"toc"`` (Table of Contents only), or ``"sections"`` (chunks
            matching the ``sections`` parameter).
        sections: Dictionary mapping URLs to lists of section names or indices
            to retrieve when ``mode="sections"``. Keys must match URLs passed
            in the ``urls`` parameter. Section names match against header text
            (case-insensitive substring) and numeric index from the TOC.
            Example: ``{"https://docs.python.org/3/": ["Installation", "Usage"]}``
    """
    try:
        from scout.crawler import ScoutCrawler
    except ImportError:
        return (
            "Error: Scout dependencies are not installed.\n\n"
            "The scout_urls tool requires 'crawl4ai' and 'playwright'.\n"
            "Install with: `uv sync --extra scout`\n"
            "Then run: `playwright install chromium`"
        )

    if not urls:
        return "Error: No URLs provided."

    # Safety limit
    max_results = max(1, min(max_results, 10))
    urls = urls[:max_results]

    # ------------------------------------------------------------------
    # Sections mode — read from cache first, fall back to re-crawling
    # ------------------------------------------------------------------
    if mode == "sections":
        from scout.chunk_cache import get_chunk_cache

        cache = get_chunk_cache()
        section_results: list[str] = []

        # Normalise sections dict: allow None or empty dict as "no sections for any URL"
        url_sections: dict[str, list[str]] = sections or {}

        for url in urls:
            # Look up sections for this specific URL
            url_section_list = url_sections.get(url, [])

            cached = cache.get_sections(url, url_section_list)
            if cached is not None:
                section_results.append(cached)
            else:
                # Cache miss — crawl, chunk, cache, then serve
                logger.info("Cache miss for %s — re-crawling for sections mode", url)
                try:
                    crawler = ScoutCrawler()
                    content = None
                    async for u, c in crawler.crawl_batch([url]):
                        content = c
                    if content:
                        from indexer.chunkers.markdown import MarkdownChunker
                        chunker = MarkdownChunker()
                        chunks = chunker.chunk(content, url)
                        cache.store(url, chunks)
                        cached = cache.get_sections(url, url_section_list)
                        if cached:
                            section_results.append(cached)
                except Exception as e:
                    logger.error("Error re-crawling %s: %s", url, e)
                    section_results.append(f"Error reading {url}: {e}")

        if not section_results:
            return "No content retrieved from any of the provided URLs."

        return "\n".join(section_results)

    # ------------------------------------------------------------------
    # Full / TOC mode — crawl, chunk, cache, then format
    # ------------------------------------------------------------------
    try:
        crawler = ScoutCrawler()
        results: list[tuple[str, str]] = []

        async for url, content in crawler.crawl_batch(urls):
            results.append((url, content))

        if not results:
            return "No content retrieved from any of the provided URLs."

        # Chunk + cache all results (used by both "full" and "toc" modes)
        from indexer.chunkers.markdown import MarkdownChunker
        from scout.chunk_cache import get_chunk_cache

        chunker = MarkdownChunker()
        cache = get_chunk_cache()

        for url, content in results:
            chunks = chunker.chunk(content, url)
            cache.store(url, chunks)

        # TOC mode — return Table of Contents only
        if mode == "toc":
            toc_lines = ["# Scouted Pages (Table of Contents)\n"]
            for url, _ in results:
                toc = cache.get_toc(url)
                toc_lines.append(toc or f"Could not generate TOC for {url}")
                toc_lines.append("")
            return "\n".join(toc_lines)

        # Full mode — return raw markdown (backward compatible)
        lines = ["# Scouted Pages\n"]
        for url, content in results:
            lines.append(f"---")
            lines.append(f"## Source: {url}\n")
            # Use chunk-aware truncation instead of blind 8k truncation:
            # if content is large, show first two chunks + note about sections mode
            if len(content) > 8000:
                chunks = cache.get(url)
                if chunks and len(chunks) > 2:
                    excerpt_lines = []
                    excerpt_lines.append(chunks[0].content)
                    excerpt_lines.append("")
                    excerpt_lines.append(
                        "... [TRUNCATED - page too large. "
                        f"This page has {len(chunks)} sections. "
                        "Re-call with mode='toc' to browse sections, "
                        "then use mode='sections' to read specific sections.] ..."
                    )
                    excerpt_lines.append("")
                    excerpt_lines.append(chunks[1].content)
                    content = "\n".join(excerpt_lines)
                else:
                    content = content[:8000] + "\n\n... [TRUNCATED - page too large] ..."
            lines.append(content)
            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Error in scout_urls: {e}")
        return f"Error crawling URLs: {str(e)}"


@mcp.tool()
async def deep_research(
    query: str,
    max_results: int = 3,
    max_urls: int = 3,
    categories: list[str] | None = None,
) -> str:
    """
    Search the web, crawl the top results, and return chunk-truncated markdown.

    Combines search_web and scout_urls into a single action. Searches
    DuckDuckGo for the query, grabs the top URLs, crawls them concurrently,
    and returns the content as markdown.

    Use this for research tasks where you need up-to-date information
    from the web in a single call.

    Args:
        query: Natural language research query (e.g., "Python asyncio gather docs").
        max_results: Maximum number of search results to consider (default 3, max 10).
        max_urls: Maximum number of URLs to crawl from results (default 3, max 5).
        categories: Optional list of search categories (SearXNG backend only).
            Ignored by DuckDuckGo backend.
    """
    try:
        # Step 1: Search the web
        search_results = core_search_web(query, max_results=max_results, categories=categories)

        if not search_results:
            return f"No web results found for: {query}"

        # Step 2: Extract top URLs
        urls = [r.url for r in search_results[:max_urls] if r.url]

        if not urls:
            return f"No valid URLs found in search results for: {query}"

        # Step 3: Try importing scout dependencies
        try:
            from scout.crawler import ScoutCrawler
        except ImportError:
            return (
                "Error: Scout dependencies are not installed.\n\n"
                "The deep_research tool requires 'crawl4ai' and 'playwright'.\n"
                "Install with: `uv sync --extra scout`\n"
                "Then run: `playwright install chromium`"
            )

        # Step 4: Crawl all URLs concurrently
        crawler = ScoutCrawler()
        crawl_results: list[tuple[str, str]] = []

        async for url, content in crawler.crawl_batch(urls):
            crawl_results.append((url, content))

        if not crawl_results:
            return f"Failed to crawl any of the URLs for query: {query}"

        # Step 5: Chunk + cache
        from indexer.chunkers.markdown import MarkdownChunker
        from scout.chunk_cache import get_chunk_cache

        chunker = MarkdownChunker()
        cache = get_chunk_cache()

        for url, content in crawl_results:
            chunks = chunker.chunk(content, url)
            cache.store(url, chunks)

        # Step 6: Format results (search results header + chunk-truncated content)
        lines = [
            f"# Deep Research: {query}\n",
            "## Search Results\n",
        ]
        for i, r in enumerate(search_results[:max_urls], 1):
            lines.append(f"{i}. **{r.title}** — {r.url}")
            lines.append(f"   > {r.snippet}")
            lines.append("")

        lines.append("---\n")
        lines.append("## Crawled Content\n")

        for url, content in crawl_results:
            lines.append(f"---")
            lines.append(f"### Source: {url}\n")
            # Chunk-aware truncation (same as scout_urls full mode)
            if len(content) > 8000:
                chunks = cache.get(url)
                if chunks and len(chunks) > 2:
                    excerpt_lines = []
                    excerpt_lines.append(chunks[0].content)
                    excerpt_lines.append("")
                    excerpt_lines.append(
                        "... [TRUNCATED - page too large. "
                        f"This page has {len(chunks)} sections. "
                        "Use scout_urls with mode='toc' to browse sections, "
                        "then mode='sections' to read specific sections.] ..."
                    )
                    excerpt_lines.append("")
                    excerpt_lines.append(chunks[1].content)
                    content = "\n".join(excerpt_lines)
                else:
                    content = content[:8000] + "\n\n... [TRUNCATED - page too large] ..."
            lines.append(content)
            lines.append("")

        return "\n".join(lines)

    except ImportError as e:
        return (
            f"Error: {e}\n\n"
            "The search_web tool requires the 'ddgs' package.\n"
            "Install it with: `uv sync --extra scout`"
        )
    except Exception as e:
        logger.error(f"Error in deep_research: {e}")
        return f"Error performing deep research: {str(e)}"


@mcp.tool()
def read_file(filepath: str, start_line: int = 1, max_lines: int = 500) -> str:
    """
    Read the contents of a file with optional line range.

    Use this to inspect file contents when semantic_code_search is
    insufficient. Supports slicing with start_line and max_lines.

    Args:
        filepath: Path to the file to read (relative or absolute).
        start_line: First line to read (1-based, default 1).
        max_lines: Maximum number of lines to return (default 500, max 1000).
    """
    from pathlib import Path

    path = Path(filepath)
    if not path.is_absolute():
        path = settings.workspace_path / path

    # Safety: respect excluded directories
    from core.filesystem import _is_excluded
    for part in path.parts:
        if _is_excluded(part):
            return (
                f"Error: Cannot read from excluded directory pattern: {part}\n"
                f"Path: {path}"
            )

    content = file_contents(str(path))
    if content is None:
        return f"Error: Could not read file: {filepath}\n(File not found, not readable, or binary.)"

    lines = content.split("\n")
    total_lines = len(lines)

    # Clamp parameters
    start_line = max(1, start_line)
    max_lines = max(1, min(max_lines, 1000))

    end_line = min(start_line + max_lines - 1, total_lines)
    selected = lines[start_line - 1 : end_line]

    header = f"# {path.name} (lines {start_line}-{end_line} of {total_lines})\n"
    numbered = []
    for i, line in enumerate(selected, start=start_line):
        numbered.append(f"{i:6d} | {line}")

    return header + "```\n" + "\n".join(numbered) + "\n```"


@mcp.tool()
def get_git_history(filepath: str) -> str:
    """
    Get git commit history metadata for a file.

    Returns the last commit's hash, author, email, date, and subject.
    Use this to understand who last modified a file and why.

    Args:
        filepath: Path to the file (relative to workspace root).
    """
    from pathlib import Path
    from indexer.git_utils import GitManager

    root = settings.workspace_path
    path = Path(filepath)
    if not path.is_absolute():
        path = root / path

    if not path.exists():
        return f"Error: File not found: {filepath}"

    manager = GitManager(root)

    if not manager.is_git_repo:
        return f"Not a git repository: {root}"

    metadata = manager.get_commit_metadata(path)
    if not metadata:
        return f"No git history found for: {filepath}\n(File may be untracked or has no commits.)"

    return (
        f"# Git History: {path.name}\n"
        f"- **Commit**: `{metadata.get('commit_hash', 'N/A')}`\n"
        f"- **Author**: {metadata.get('commit_author', 'N/A')} <{metadata.get('commit_email', 'N/A')}>\n"
        f"- **Date**: {metadata.get('commit_date', 'N/A')}\n"
        f"- **Subject**: {metadata.get('commit_subject', 'N/A')}\n"
    )


def run_mcp():
    """Entry point for MCP server."""
    logger.info("Starting Hivemind Server on stdio")
    mcp.run()