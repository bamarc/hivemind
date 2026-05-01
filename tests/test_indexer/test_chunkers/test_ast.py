"""
Tests for :class:`indexer.chunkers.ast.ASTChunker`.

These tests validate tree-sitter based AST-aware code splitting across
multiple languages.  The chunker must correctly identify definition
boundaries (functions, classes, methods, etc.) and preserve non-definition
content via a buffer.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from indexer.chunkers.ast import ASTChunker


@pytest.fixture
def chunker() -> ASTChunker:
    return ASTChunker(chunk_lines=50, overlap_lines=5)


# ======================================================================
#  Python
# ======================================================================


class TestPythonChunking:
    PY_CODE = (
        "import os\n"
        "import sys\n"
        "\n"
        "GLOBAL_CONST = 42\n"
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
        "\n"
        "# standalone comment\n"
        "x = 1\n"
    )

    def test_chunk_python_definitions(self, chunker: ASTChunker):
        """Function and class definitions become separate chunks with
        appropriate metadata."""
        chunks = chunker.chunk(self.PY_CODE, "/test.py")
        # We expect at least 3 definition chunks: greet, Calculator (header),
        # plus buffer content for the rest
        assert len(chunks) >= 3

        # Find the greet chunk
        greet_chunks = [c for c in chunks if "greet" in str(c.metadata)]
        assert len(greet_chunks) >= 1

    def test_chunk_symbol_metadata(self, chunker: ASTChunker):
        """Symbols should be extracted into chunk metadata."""
        chunks = chunker.chunk(self.PY_CODE, "/test.py")
        # At least one chunk should have "greet" in its symbols
        all_symbols = []
        for c in chunks:
            if c.metadata:
                all_symbols.extend(c.metadata.get("symbols", []))
        assert "greet" in all_symbols

    def test_top_level_code_in_buffer(self, chunker: ASTChunker):
        """Code outside definition nodes should be captured in buffer chunks."""
        chunks = chunker.chunk(self.PY_CODE, "/test.py")
        # The GLOBAL_CONST and the trailing `x = 1` should appear somewhere
        all_content = "".join(c.content for c in chunks)
        assert "GLOBAL_CONST" in all_content
        assert "x = 1" in all_content

    def test_imports_preserved(self, chunker: ASTChunker):
        """Import statements should appear in buffer chunks."""
        chunks = chunker.chunk(self.PY_CODE, "/test.py")
        all_content = "".join(c.content for c in chunks)
        assert "import os" in all_content
        assert "import sys" in all_content

    def test_chunk_line_numbers(self, chunker: ASTChunker):
        """Line numbers should be 1-indexed and accurate."""
        chunks = chunker.chunk(self.PY_CODE, "/test.py")
        for c in chunks:
            content_lines = c.content.splitlines()
            expected_end = c.line_start + len(content_lines) - 1
            assert c.line_end == expected_end, (
                f"Chunk {c.chunk_index}: expected line_end={expected_end}, "
                f"got {c.line_end} (start={c.line_start}, "
                f"{len(content_lines)} lines)"
            )


# ======================================================================
#  Go
# ======================================================================


class TestGoChunking:
    GO_CODE = (
        "package main\n"
        "\n"
        "import \"fmt\"\n"
        "\n"
        "func greet(name string) string {\n"
        "    return fmt.Sprintf(\"Hello, %s\", name)\n"
        "}\n"
        "\n"
        "type Point struct {\n"
        "    X, Y int\n"
        "}\n"
        "\n"
        "func (p Point) Distance() float64 {\n"
        "    return math.Sqrt(float64(p.X*p.X + p.Y*p.Y))\n"
        "}\n"
    )

    def test_chunk_go_functions(self, chunker: ASTChunker):
        chunks = chunker.chunk(self.GO_CODE, "/main.go")
        all_content = "".join(c.content for c in chunks)
        assert "func greet" in all_content
        assert "greet" in str(chunks)

    def test_chunk_go_types(self, chunker: ASTChunker):
        chunks = chunker.chunk(self.GO_CODE, "/main.go")
        all_content = "".join(c.content for c in chunks)
        assert "type Point struct" in all_content


# ======================================================================
#  TypeScript
# ======================================================================


class TestTypeScriptChunking:
    TS_CODE = (
        "import { Component } from '@angular/core';\n"
        "\n"
        "interface User {\n"
        "    name: string;\n"
        "    age: number;\n"
        "}\n"
        "\n"
        "function greet(user: User): string {\n"
        "    return `Hello, ${user.name}`;\n"
        "}\n"
        "\n"
        "class Greeter {\n"
        "    private prefix: string;\n"
        "    constructor(prefix: string) {\n"
        "        this.prefix = prefix;\n"
        "    }\n"
        "    greet(user: User): string {\n"
        "        return `${this.prefix} ${user.name}`;\n"
        "    }\n"
        "}\n"
        "\n"
        "const greeter = new Greeter('Hi');\n"
    )

    def test_chunk_typescript_definitions(self, chunker: ASTChunker):
        chunks = chunker.chunk(self.TS_CODE, "/app.ts")
        assert len(chunks) >= 1

    def test_chunk_typescript_interface(self, chunker: ASTChunker):
        chunks = chunker.chunk(self.TS_CODE, "/app.ts")
        all_content = "".join(c.content for c in chunks)
        assert "interface User" in all_content

    def test_chunk_typescript_class(self, chunker: ASTChunker):
        chunks = chunker.chunk(self.TS_CODE, "/app.ts")
        all_content = "".join(c.content for c in chunks)
        assert "class Greeter" in all_content


# ======================================================================
#  YAML / HCL
# ======================================================================


class TestYamlChunking:
    YAML_CODE = (
        "apiVersion: v1\n"
        "kind: ConfigMap\n"
        "metadata:\n"
        "  name: my-config\n"
        "data:\n"
        "  key1: value1\n"
        "  key2: value2\n"
    )

    def test_chunk_yaml(self, chunker: ASTChunker):
        chunks = chunker.chunk(self.YAML_CODE, "/cfg.yaml")
        all_content = "".join(c.content for c in chunks)
        assert "apiVersion: v1" in all_content


class TestHclChunking:
    HCL_CODE = (
        'resource "aws_instance" "web" {\n'
        "  ami           = \"ami-123\"\n"
        "  instance_type = \"t2.micro\"\n"
        "}\n"
        "\n"
        'variable "region" {\n'
        "  default = \"us-east-1\"\n"
        "}\n"
    )

    def test_chunk_hcl(self, chunker: ASTChunker):
        chunks = chunker.chunk(self.HCL_CODE, "/main.tf")
        all_content = "".join(c.content for c in chunks)
        assert "resource" in all_content


# ======================================================================
#  Fallback & edge cases
# ======================================================================


class TestFallbackAndEdgeCases:
    def test_unsupported_extension_falls_back(self, chunker: ASTChunker):
        """When no tree-sitter language is registered for the extension,
        the chunker should fall back to line-based splitting."""
        content = "\n".join(f"line {i}" for i in range(60))
        chunks = chunker.chunk(content, "/unknown.xyz")
        assert len(chunks) >= 1
        # Should still produce chunks
        assert chunks[0].line_start == 1

    def test_empty_content(self, chunker: ASTChunker):
        chunks = chunker.chunk("", "/empty.py")
        assert chunks == []

    def test_single_function(self, chunker: ASTChunker):
        code = "def foo():\n    pass\n"
        chunks = chunker.chunk(code, "/single.py")
        assert len(chunks) >= 1
        assert "foo" in chunks[0].content
        # The function should have a symbol entry
        if chunks[0].metadata:
            all_symbols = chunks[0].metadata.get("symbols", [])
            assert "foo" in all_symbols or all_symbols == []

    def test_sanitize_base64(self, chunker: ASTChunker):
        """Long base64 strings should be stripped."""
        b64 = "A" * 200 + "=="
        code = f"x = \"{b64}\"\n"
        sanitized = chunker.sanitize_content(code)
        assert "[BASE64_DATA_STRIPPED]" in sanitized
        assert b64 not in sanitized

    def test_sanitize_long_strings(self, chunker: ASTChunker):
        """Very long string literals should be stripped.

        Note: the sanitizer applies the base64-pattern first, so a long
        string composed only of ``[A-Za-z0-9+/]`` will be stripped as
        ``[BASE64_DATA_STRIPPED]`` instead.  We use non-base64 characters
        here to test the long-string-pattern specifically.
        """
        long_str = "x x x " * 200  # spaces are not valid base64
        code = f's = "{long_str}"\n'
        sanitized = chunker.sanitize_content(code)
        assert "[LONG_STRING_STRIPPED]" in sanitized, f"Got: {sanitized!r}"
        assert long_str not in sanitized

    def test_chunk_index_increments(self, chunker: ASTChunker):
        code = (
            "def a(): pass\n"
            "\n"
            "def b(): pass\n"
            "\n"
            "def c(): pass\n"
            "\n"
            "def d(): pass\n"
        )
        chunks = chunker.chunk(code, "/many.py")
        for i, c in enumerate(chunks):
            assert c.chunk_index == i

    def test_no_crash_on_binary_content(self, chunker: ASTChunker):
        """The chunker should not crash on content with lone surrogate
        characters (a known bug)."""
        content = "def foo():\n    pass\n# \ud800\n"
        chunks = chunker.chunk(content, "/broken.py")
        assert isinstance(chunks, list)
        assert len(chunks) >= 1
        assert "foo" in chunks[0].content
