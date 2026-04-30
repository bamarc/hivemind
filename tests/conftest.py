"""
Global test configuration and mock infrastructure for Hivemind.

Because ``core.clients`` creates ``db``, ``embedder``, and ``chat_client``
at **import time** (module-level globals), this conftest imports
``core.clients`` and then immediately replaces those globals with
:class:`unittest.mock.MagicMock` instances.  Any test module that
accesses ``core.clients.db`` or uses functions from ``core.clients``
will therefore use the mocked objects.

``tests/conftest.py`` is loaded by pytest before any test collection
happens, so this patching is in place before any test module is
imported.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# 1.  Mock the module-level clients in ``core.clients``
# ---------------------------------------------------------------------------
# The import below triggers instantiation of QdrantClient, OpenAI (embedder)
# and OpenAI (chat).  None of these constructors actually connect to anything
# at __init__ time -- they just store configuration -- so it is safe even
# with the LM server offline.
import core.clients  # noqa: E402  (pytest re-ordering is intentional)

# ── Qdrant client mock ────────────────────────────────────────────────
MOCK_QDRANT: MagicMock = MagicMock(name="MockQdrantClient")


def _collection_mock(collection_name: str) -> MagicMock:
    """Create a mock Qdrant collection with a real ``.name`` attribute."""
    col = MagicMock()
    col.name = collection_name
    return col


def _reset_qdrant():
    """Reset MOCK_QDRANT to a known good state, clearing any side_effect,
    return_value, and call-history leakage from the previous test."""
    from core.config import settings

    # reset_mock() clears call counts, call args, side_effect, return_value,
    # and child mock cache -- then we explicitly re-bind the defaults so
    # the next test starts with a clean slate.
    MOCK_QDRANT.reset_mock()
    MOCK_QDRANT.get_collections.side_effect = None
    MOCK_QDRANT.get_collections.return_value = MagicMock(
        collections=[_collection_mock(settings.qdrant.collection_name)]
    )
    MOCK_QDRANT.query_points.side_effect = None
    MOCK_QDRANT.query_points.return_value = MagicMock(points=[])
    MOCK_QDRANT.retrieve.side_effect = None
    MOCK_QDRANT.retrieve.return_value = []
    MOCK_QDRANT.upsert.side_effect = None
    MOCK_QDRANT.upsert.return_value = None
    MOCK_QDRANT.create_collection.side_effect = None
    MOCK_QDRANT.create_collection.return_value = None
    MOCK_QDRANT.create_payload_index.side_effect = None
    MOCK_QDRANT.create_payload_index.return_value = None
    MOCK_QDRANT.delete_collection.side_effect = None
    MOCK_QDRANT.delete_collection.return_value = None
    MOCK_QDRANT.get_collection.side_effect = None
    MOCK_QDRANT.get_collection.return_value = MagicMock(points_count=42)

_reset_qdrant()
core.clients.db = MOCK_QDRANT

# ── Embedder mock ─────────────────────────────────────────────────────
MOCK_EMBEDDER: MagicMock = MagicMock(name="MockEmbedder")


def _fake_embedding_response(*, input, model, **_kwargs):
    """Return a fake embedding response for a single string or list of strings."""
    from core.config import settings

    dim = settings.model.embedding_dim

    if isinstance(input, str):
        inputs = [input]
    else:
        inputs = list(input)

    mock_data = []
    for i, _text in enumerate(inputs):
        vec = [float((i + j % 255) / 255.0) for j in range(dim)]
        item_mock = MagicMock(name=f"EmbeddingItem[{i}]")
        item_mock.embedding = vec
        mock_data.append(item_mock)

    response_mock = MagicMock(name="EmbeddingResponse")
    response_mock.data = mock_data
    return response_mock


MOCK_EMBEDDER.embeddings.create = _fake_embedding_response

core.clients.embedder = MOCK_EMBEDDER

# ── Chat client mock ──────────────────────────────────────────────────
MOCK_CHAT_CLIENT: MagicMock = MagicMock(name="MockChatClient")


def _fake_chat_completion(*, model, messages, **_kwargs):
    """Return a fake chat completion response."""
    choice_mock = MagicMock(name="ChatChoice")
    choice_mock.message.content = '{"blueprint": [{"file": "test.py", "action": "modify", "description": "test", "logic": "pass"}]}'
    choice_mock.message.refusal = None

    completion_mock = MagicMock(name="ChatCompletion")
    completion_mock.choices = [choice_mock]
    return completion_mock


MOCK_CHAT_CLIENT.chat.completions.create = _fake_chat_completion

core.clients.chat_client = MOCK_CHAT_CLIENT


# ---------------------------------------------------------------------------
# 2.  Deterministic embedding helper (for assertions in tests)
# ---------------------------------------------------------------------------
def fake_embedding_vector(index: int = 0) -> list[float]:
    """Return a deterministic embedding vector of the correct dimension.

    This mirrors the logic in ``_fake_embedding_response`` so that tests
    can verify the vectors that get passed to Qdrant (or returned from
    the embedder) match expectations.
    """
    from core.config import settings

    dim = settings.model.embedding_dim
    return [float((index + j % 255) / 255.0) for j in range(dim)]


# ---------------------------------------------------------------------------
# 3.  Auto‑reset between tests to prevent state leakage
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _reset_module_mocks() -> Generator[None, None, None]:
    """Reset all module-level mocks to their default state before each test.

    Because ``test_clients.py`` modifies ``mock_embedder.embeddings.create``
    and other tests modify ``mock_qdrant.get_collections.side_effect``,
    we must restore the defaults to prevent state leaking between tests.
    """
    # ── Reset Qdrant mock ──
    _reset_qdrant()

    # ── Reset Embedder mock ──
    MOCK_EMBEDDER.embeddings.create = _fake_embedding_response

    # ── Reset Chat client mock ──
    MOCK_CHAT_CLIENT.chat.completions.create = _fake_chat_completion

    yield


# ---------------------------------------------------------------------------
# 4.  Shared fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_qdrant() -> MagicMock:
    """Return the module-level mocked Qdrant client for per-test configuration."""
    return MOCK_QDRANT


@pytest.fixture
def mock_embedder() -> MagicMock:
    """Return the module-level mocked embedder for per-test configuration."""
    return MOCK_EMBEDDER


@pytest.fixture
def mock_chat_client() -> MagicMock:
    """Return the module-level mocked chat client for per-test configuration."""
    return MOCK_CHAT_CLIENT


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create a temporary project directory with a ``.gitignore`` and a
    ``config.yaml``, and temporarily change the working directory so that
    ``os.getcwd()`` points inside it.

    This is useful for tests that depend on :attr:`core.config.settings`
    (which uses ``os.getcwd()`` in several defaults).
    """
    cwd = Path.cwd()
    try:
        os.chdir(str(tmp_path))
        # Minimal .gitignore
        (tmp_path / ".gitignore").write_text("*.log\n.env\n__pycache__/\n")
        # Minimal config.yaml
        (tmp_path / "config.yaml").write_text(
            "qdrant:\n  collection_name: test_collection\n"
            "logging:\n  level: DEBUG\n"
        )
        yield tmp_path
    finally:
        os.chdir(str(cwd))


@pytest.fixture
def sample_python_file(tmp_path: Path) -> Path:
    """Create a small Python source file for chunking / indexing tests."""
    filepath = tmp_path / "sample.py"
    filepath.write_text(
        "import os\n"
        "import sys\n"
        "\n"
        "def greet(name: str) -> str:\n"
        '    """Say hello."""\n'
        '    return f"Hello, {name}"\n'
        "\n"
        "class Calculator:\n"
        "    def add(self, a: int, b: int) -> int:\n"
        "        return a + b\n"
        "\n"
        "    def multiply(self, a: int, b: int) -> int:\n"
        "        return a * b\n"
    )
    return filepath


@pytest.fixture
def sample_markdown_file(tmp_path: Path) -> Path:
    """Create a markdown file for chunking tests."""
    filepath = tmp_path / "readme.md"
    filepath.write_text(
        "# Project Title\n\n"
        "Intro paragraph.\n\n"
        "## Installation\n\n"
        "Run `pip install foo`.\n\n"
        "## Usage\n\n"
        "Run `foo --help`.\n\n"
        "### Advanced\n\n"
        "Details here.\n"
    )
    return filepath
