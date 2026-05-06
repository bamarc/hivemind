"""
Global test configuration and mock infrastructure for Hivemind.

``core.clients`` now uses lazy factory functions (``get_db()``,
``get_embedder()``, ``get_chat_client()``) instead of module-level globals.
This conftest uses :func:`unittest.mock.patch` to inject ``MagicMock``
instances as the return values of those factories *before* any test module
imports that use them.

``tests/conftest.py`` is loaded by pytest before any test collection
happens, so this patching is in place before any test module is
imported.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# 1.  Build the mock objects
# ---------------------------------------------------------------------------

# Fixed embedding dimension used by all mock responses.  This ensures
# deterministic test behaviour even when ``settings.model.embedding_dim``
# is ``None`` (the default after auto-detect was introduced).
MOCK_EMBEDDING_DIM: int = 2500

# ── Qdrant client mock ────────────────────────────────────────────────
MOCK_QDRANT: MagicMock = MagicMock(name="MockQdrantClient")


def _collection_mock(collection_name: str) -> MagicMock:
    """Create a mock Qdrant collection with a real ``.name`` attribute."""
    col = MagicMock()
    col.name = collection_name
    return col


def _resolve_dim() -> int:
    """Return the configured embedding dimension or the mock default."""
    from core.config import settings

    return settings.model.embedding_dim or MOCK_EMBEDDING_DIM


def _reset_qdrant():
    """Reset MOCK_QDRANT to a known good state, clearing any side_effect,
    return_value, and call-history leakage from the previous test."""
    from core.config import settings

    dim = _resolve_dim()

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
    MOCK_QDRANT.get_collection.return_value = MagicMock(
        config=MagicMock(
            params=MagicMock(
                vectors=MagicMock(size=dim),
                sparse_vectors={
                    "code-sparse": MagicMock(),
                },
            ),
        ),
        points_count=42,
    )


_reset_qdrant()

# ── Embedder mock ─────────────────────────────────────────────────────
MOCK_EMBEDDER: MagicMock = MagicMock(name="MockEmbedder")


def _fake_embedding_response(*, input, model, **_kwargs):
    """Return a fake embedding response for a single string or list of strings."""
    dim = _resolve_dim()

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


# Use a MagicMock with side_effect so callers can assert on invocations
# while still getting realistic fake embedding vectors.
MOCK_EMBEDDER.embeddings.create = MagicMock(
    side_effect=_fake_embedding_response,
    name="MockEmbedder.embeddings.create",
)

# ── Chat client mock ──────────────────────────────────────────────────
MOCK_CHAT_CLIENT: MagicMock = MagicMock(name="MockChatClient")


def _fake_chat_completion(*, model, messages, **_kwargs):
    """Return a fake chat completion response."""
    choice_mock = MagicMock(name="ChatChoice")
    choice_mock.message.content = (
        '{"blueprint": [{"file": "test.py", "action": "modify", '
        '"description": "test", "logic": "pass"}]}'
    )
    choice_mock.message.refusal = None

    completion_mock = MagicMock(name="ChatCompletion")
    completion_mock.choices = [choice_mock]
    return completion_mock


MOCK_CHAT_CLIENT.chat.completions.create = _fake_chat_completion


# ---------------------------------------------------------------------------
# 2.  Apply patches so that every ``get_*()`` factory returns the mock
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True, scope="session")
def _patch_clients():
    """Patch the lazy client factories **once** for the entire test session.

    This replaces the production ``get_db()`` / ``get_embedder()`` /
    ``get_chat_client()`` with functions that always return the module-level
    mock singletons defined above.

    Some modules use ``from .clients import get_*`` (creating a local
    reference), so we also patch those local references directly.
    """
    patchers = [
        # Root factory patches
        patch("core.clients.get_db", return_value=MOCK_QDRANT),
        patch("core.clients.get_embedder", return_value=MOCK_EMBEDDER),
        patch("core.clients.get_chat_client", return_value=MOCK_CHAT_CLIENT),
        # Local references in modules that use ``from .clients import ...``
        patch("core.planner.get_chat_client", return_value=MOCK_CHAT_CLIENT),
        patch("server.server.get_db", return_value=MOCK_QDRANT),
        patch("server.server.get_chat_client", return_value=MOCK_CHAT_CLIENT),
        patch("server.api.get_db", return_value=MOCK_QDRANT),
        patch("indexer.watcher.get_db", return_value=MOCK_QDRANT),
        patch("indexer.index_worker.get_db", return_value=MOCK_QDRANT),
    ]
    for p in patchers:
        p.start()
    yield
    for p in patchers:
        p.stop()


# ── Config isolation (MUST run before _reset_module_mocks) ─────────────
@pytest.fixture(autouse=True)
def _isolate_config(monkeypatch) -> Generator[None, None, None]:
    """Isolate every test from global config, project YAML, and env vars.

    This fixture:
    1. Saves and clears all ``HIVEMIND_*`` environment variables
    2. Points ``_GLOBAL_CONFIG_PATH`` to a nonexistent file
    3. Resets ``embedding_dim`` to ``None`` so that mock helpers always use
       the deterministic ``MOCK_EMBEDDING_DIM`` constant
    4. Calls ``reset_settings()`` to recreate the singleton with clean state
    5. After the test, restores env vars and resets settings again

    This runs BEFORE ``_reset_module_mocks`` (defined later in this file)
    so that mock defaults are computed from the isolated settings values.
    """
    import os as _os
    from core.config import reset_settings

    # 1. Save and clear HIVEMIND_* env vars
    _saved_env: dict[str, str] = {}
    for _key in list(_os.environ.keys()):
        if _key.startswith("HIVEMIND_"):
            _saved_env[_key] = _os.environ.pop(_key)

    # 2. Point global config to a nonexistent file
    monkeypatch.setattr(
        "core.config._GLOBAL_CONFIG_PATH",
        Path("/nonexistent/hivemind_global_config.yaml"),
    )

    # 3. Reset the settings singleton with clean state
    reset_settings()
    # Force embedding_dim to None so _resolve_dim() falls back to
    # MOCK_EMBEDDING_DIM, regardless of any project-level config.yaml.
    # Re-import after reset_settings() since it reassigns the module-level
    # ``settings`` variable to a new ``Settings()`` instance.
    from core.config import settings as _new_s
    _new_s.model.embedding_dim = None

    yield

    # 4. Restore env vars and reset settings
    for _key, _value in _saved_env.items():
        _os.environ[_key] = _value
    reset_settings()


# ---------------------------------------------------------------------------
# 3.  Deterministic embedding helper (for assertions in tests)
# ---------------------------------------------------------------------------
def fake_embedding_vector(index: int = 0) -> list[float]:
    """Return a deterministic embedding vector of the correct dimension.

    This mirrors the logic in ``_fake_embedding_response`` so that tests
    can verify the vectors that get passed to Qdrant (or returned from
    the embedder) match expectations.
    """
    dim = _resolve_dim()
    return [float((index + j % 255) / 255.0) for j in range(dim)]


# ---------------------------------------------------------------------------
# 4.  Auto‑reset between tests to prevent state leakage
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _reset_module_mocks() -> Generator[None, None, None]:
    """Reset all module-level mocks to their default state before each test.

    Because ``test_clients.py`` modifies ``MOCK_EMBEDDER.embeddings.create``
    and other tests modify ``MOCK_QDRANT.get_collections.side_effect``,
    we must restore the defaults to prevent state leaking between tests.
    """
    _reset_qdrant()
    MOCK_EMBEDDER.embeddings.create = MagicMock(
        side_effect=_fake_embedding_response,
        name="MockEmbedder.embeddings.create",
    )
    MOCK_CHAT_CLIENT.chat.completions.create = _fake_chat_completion
    yield


# ---------------------------------------------------------------------------
# 5.  Shared fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_qdrant() -> MagicMock:
    """Return the module-level mocked Qdrant client for per-test configuration."""
    return MOCK_QDRANT


@pytest.fixture
def mock_embedder() -> MagicMock:
    """Return the module-level mocked embedder for per-test configuration.

    Also clears the ``detect_embedding_dim`` LRU cache so that tests
    calling ``detect_embedding_dim()`` always get a fresh probe result.
    """
    from core.clients import detect_embedding_dim

    detect_embedding_dim.cache_clear()
    return MOCK_EMBEDDER


@pytest.fixture
def mock_chat_client() -> MagicMock:
    """Return the module-level mocked chat client for per-test configuration."""
    return MOCK_CHAT_CLIENT


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create a temporary project directory with a ``.gitignore`` and a
    ``.hivemind/config.yaml``, and temporarily change the working directory so that
    ``os.getcwd()`` points inside it.

    This is useful for tests that depend on :attr:`core.config.settings`
    (which uses ``os.getcwd()`` in several defaults).
    """
    cwd = Path.cwd()
    try:
        os.chdir(str(tmp_path))
        # Minimal .gitignore
        (tmp_path / ".gitignore").write_text("*.log\n.env\n__pycache__/\n")
        # Minimal project config
        hive_dir = tmp_path / ".hivemind"
        hive_dir.mkdir()
        (hive_dir / "config.yaml").write_text(
            "qdrant:\n  collection_name: test_collection\n"
            "logging:\n  level: DEBUG\n"
        )
        yield tmp_path
    finally:
        os.chdir(str(cwd))
        from core.config import reset_settings
        reset_settings()


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
