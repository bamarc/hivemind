"""
RAG (Retrieval-Augmented Generation) pipeline for Hivemind.

Provides shared helpers for semantic search retrieval, prompt building,
and LLM-based Q&A synthesis. Used by both the MCP server
(:mod:`server.server`) and the CLI (:mod:`cli.ask_command`).

All external API clients are imported lazily from :mod:`core.clients`
so that callers can import this module without triggering connection
setup, and so that test patches applied to ``core.clients`` take effect
at call time.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def semantic_search_raw(
    query: str,
    limit: int = 5,
    root_path: str | None = None,
    *,
    min_score: float = 0.0,
    min_content_length: int = 0,
) -> list[dict[str, Any]]:
    """Run semantic search and return raw payload dicts (no markdown formatting).

    Uses dense-only vector search.  For richer results that combine dense
    and sparse matching, use :func:`semantic_search_hybrid`.

    Parameters
    ----------
    query:
        Natural language search query.
    limit:
        Maximum number of results to return.
    root_path:
        Project root path.  ``None`` = use the configured workspace.
    min_score:
        Minimum similarity score to include a result (0.0 = no filter).
    min_content_length:
        Minimum number of non-empty characters in the chunk content
        (0 = no filter).

    Returns
    -------
    list[dict]
        Each dict has keys ``filepath``, ``content``, ``language``,
        ``score``, ``line_start``, ``line_end``.
    """
    from pathlib import Path

    from core.clients import get_db, get_embedding
    from core.config import settings

    root = Path(root_path) if root_path else settings.workspace_path
    collection_name = root.name if root_path else settings.qdrant.collection_name
    query_vector = get_embedding(query)

    response = get_db().query_points(
        collection_name=collection_name,
        query=query_vector,
        limit=limit * 2,  # over-fetch to allow for post-filtering
    )
    results: list[dict[str, Any]] = []
    for hit in response.points:
        content = hit.payload.get("content", "")
        score = hit.score if hasattr(hit, "score") else 0.0

        if min_score > 0 and score < min_score:
            continue
        if min_content_length > 0 and len(content.strip()) < min_content_length:
            continue

        results.append(
            {
                "filepath": hit.payload.get("filepath", "unknown"),
                "content": content,
                "language": hit.payload.get("language", "text"),
                "score": score,
                "line_start": hit.payload.get("line_start", 1),
                "line_end": hit.payload.get("line_end", "?"),
            }
        )
        if len(results) >= limit:
            break

    return results


def semantic_search_hybrid(
    query: str,
    limit: int = 5,
    root_path: str | None = None,
    *,
    min_score: float = 0.0,
    min_content_length: int = 0,
) -> list[dict[str, Any]]:
    """Run semantic search using hybrid mode (dense + sparse RRF fusion).

    Combines dense vector similarity with sparse keyword matching via
    reciprocal rank fusion (RRF).  Requires the Qdrant collection to
    have ``code-sparse`` sparse vector support enabled.

    Parameters
    ----------
    query:
        Natural language search query.
    limit:
        Maximum number of results to return.
    root_path:
        Project root path.  ``None`` = use the configured workspace.
    min_score:
        Minimum similarity score to include a result (0.0 = no filter).
    min_content_length:
        Minimum number of non-empty characters in the chunk content
        (0 = no filter).

    Returns
    -------
    list[dict]
        See :func:`semantic_search_raw` for the dict structure.
    """
    from pathlib import Path

    from core.clients import get_db, get_embedding, text_to_sparse_vector
    from core.config import settings

    root = Path(root_path) if root_path else settings.workspace_path
    collection_name = root.name if root_path else settings.qdrant.collection_name
    query_vector = get_embedding(query)
    sparse_vector = text_to_sparse_vector(query)

    from qdrant_client import models as qdrant_models

    response = get_db().query_points(
        collection_name=collection_name,
        prefetch=[
            qdrant_models.Prefetch(
                query=query_vector,
                limit=limit * 2,
            ),
            qdrant_models.Prefetch(
                query=qdrant_models.SparseVector(
                    indices=sparse_vector.indices,
                    values=sparse_vector.values,
                ),
                using="code-sparse",
                limit=limit * 2,
            ),
        ],
        query=qdrant_models.FusionQuery(fusion=qdrant_models.Fusion.RRF),
        limit=limit * 2,
    )
    results: list[dict[str, Any]] = []
    for hit in response.points:
        content = hit.payload.get("content", "")
        score = hit.score if hasattr(hit, "score") else 0.0

        if min_score > 0 and score < min_score:
            continue
        if min_content_length > 0 and len(content.strip()) < min_content_length:
            continue

        results.append(
            {
                "filepath": hit.payload.get("filepath", "unknown"),
                "content": content,
                "language": hit.payload.get("language", "text"),
                "score": score,
                "line_start": hit.payload.get("line_start", 1),
                "line_end": hit.payload.get("line_end", "?"),
            }
        )
        if len(results) >= limit:
            break

    return results


def format_chunks_for_qa(chunks: list[dict[str, Any]]) -> str:
    """Format a list of chunk dicts into a markdown block for the LLM prompt.

    Parameters
    ----------
    chunks:
        List of chunk dicts as returned by :func:`semantic_search_raw`.

    Returns
    -------
    str
        Formatted markdown with filepath, line ranges, and syntax-highlighted
        code blocks.
    """
    parts: list[str] = []
    for i, chunk in enumerate(chunks, 1):
        parts.append(
            f"### [{i}] {chunk['filepath']} "
            f"(lines {chunk['line_start']}-{chunk['line_end']})\n"
            f"```{chunk['language']}\n{chunk['content']}\n```\n"
        )
    return "\n".join(parts)


def build_qa_system_prompt(context: str) -> str:
    """Build the system prompt for the RAG chat completion.

    Parameters
    ----------
    context:
        Optional extra context provided by the user (e.g. "I'm adding
        OAuth support").

    Returns
    -------
    str
        System prompt instructing the LLM to answer based *only* on the
        provided code snippets.
    """
    base = (
        "You are a senior software engineer analyzing a codebase. "
        "Answer the user's question based ONLY on the provided code snippets. "
        "If the snippets don't contain enough information to answer, say so. "
        "Always reference specific file paths and function/class names. "
        "Be concise but thorough."
    )
    if context:
        base += f"\n\nAdditional context from the user: {context}"
    return base


def build_qa_user_prompt(question: str, chunks_text: str) -> str:
    """Build the user prompt containing the question and relevant code chunks.

    Parameters
    ----------
    question:
        The user's natural language question.
    chunks_text:
        Formatted code chunks (output of :func:`format_chunks_for_qa`).

    Returns
    -------
    str
        User prompt to send to the chat model.
    """
    return (
        f"## Question\n{question}\n\n"
        f"## Relevant Code Snippets\n{chunks_text}\n\n"
        f"## Instructions\n"
        f"Based on the code snippets above, answer the question. "
        f"Cite the relevant file paths in your answer."
    )


def format_citations(chunks: list[dict[str, Any]]) -> str:
    """Format code chunk metadata as a markdown citation list.

    Parameters
    ----------
    chunks:
        List of chunk dicts as returned by :func:`semantic_search_raw`.

    Returns
    -------
    str
        Markdown list with clickable filepath, score, and line ranges.
    """
    lines: list[str] = []
    for c in chunks:
        lines.append(
            f"- [`{c['filepath']}`]({c['filepath']}:{c['line_start']}) "
            f"(score: {c['score']:.2f}, lines {c['line_start']}-{c['line_end']})"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def ask_codebase(
    question: str,
    context: str = "",
    max_chunks: int = 5,
    project_path: str | None = None,
) -> tuple[str, str]:
    """Run the full RAG pipeline: hybrid search -> prompt -> LLM -> answer + citations.

    Uses :func:`semantic_search_hybrid` to combine dense and sparse
    matching with a minimum content length filter (50 chars) to reject
    near-empty chunks.

    Parameters
    ----------
    question:
        Natural language question about the codebase.
    context:
        Optional extra context (e.g. "I'm adding OAuth support").
    max_chunks:
        Maximum number of code chunks to retrieve.
    project_path:
        Project root path for the search scope.
        ``None`` = use the configured workspace.

    Returns
    -------
    tuple[str, str]
        ``(answer, citations_markdown)``.

    Raises
    ------
    ValueError
        If no relevant code chunks are found.
    """
    from core.clients import get_chat_client
    from core.config import settings

    search_results = semantic_search_hybrid(
        question,
        limit=max_chunks,
        root_path=project_path,
        min_content_length=20,
    )
    if not search_results:
        raise ValueError(
            "I couldn't find any relevant code to answer that question. "
            "Make sure the project has been indexed (use `start_indexing`)."
        )

    chunks_text = format_chunks_for_qa(search_results)
    system_prompt = build_qa_system_prompt(context)
    user_prompt = build_qa_user_prompt(question, chunks_text)

    client = get_chat_client()
    response = client.chat.completions.create(
        model=settings.chat.model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
    )
    answer = response.choices[0].message.content
    citations = format_citations(search_results)
    return answer, citations
