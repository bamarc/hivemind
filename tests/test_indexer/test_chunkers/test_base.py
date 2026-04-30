"""
Tests for :mod:`indexer.chunkers.base` — the :class:`Chunk` dataclass and
the :class:`ChunkingStrategy` ABC.
"""

from __future__ import annotations

from indexer.chunkers.base import Chunk, ChunkingStrategy


class TestChunkDataclass:
    def test_minimal_construction(self):
        """A Chunk can be created with only the required fields."""
        c = Chunk(content="hello", filepath="/a/b.py", chunk_index=0, line_start=1, line_end=5)
        assert c.content == "hello"
        assert c.filepath == "/a/b.py"
        assert c.chunk_index == 0
        assert c.line_start == 1
        assert c.line_end == 5
        assert c.metadata is None

    def test_full_construction(self):
        """All fields including metadata are stored correctly."""
        c = Chunk(
            content="def foo(): pass",
            filepath="/project/src/mod.py",
            chunk_index=3,
            line_start=10,
            line_end=12,
            metadata={"type": "function", "symbols": ["foo"]},
        )
        assert c.metadata == {"type": "function", "symbols": ["foo"]}

    def test_repr(self):
        c = Chunk("x", "f.py", 0, 1, 1)
        r = repr(c)
        assert "Chunk" in r
        assert "f.py" in r

    def test_equality_by_value(self):
        c1 = Chunk("a", "f.py", 0, 1, 1)
        c2 = Chunk("a", "f.py", 0, 1, 1)
        assert c1 == c2

    def test_inequality(self):
        c1 = Chunk("a", "f.py", 0, 1, 1)
        c2 = Chunk("b", "f.py", 0, 1, 1)
        assert c1 != c2


class TestChunkingStrategy:
    def test_abc_cannot_be_instantiated(self):
        """ChunkingStrategy is abstract and cannot be instantiated directly."""
        try:
            ChunkingStrategy()  # type: ignore[abstract]
            assert False, "Should have raised TypeError"
        except TypeError:
            pass
