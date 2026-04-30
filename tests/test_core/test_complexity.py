"""
Tests for :mod:`core.complexity`.

The :func:`get_complexity` function uses tree-sitter to parse source files
and compute structural metrics (nesting depth, node count, definition count,
import count, etc.).  These tests create small temporary source files in each
supported language and verify the returned metrics.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from core.complexity import get_complexity


# ======================================================================
#  Fixtures – small sample files for each supported language
# ======================================================================

@pytest.fixture
def py_sample(tmp_path: Path) -> Path:
    """A small Python file with imports, a function, and a class."""
    p = tmp_path / "sample.py"
    p.write_text(
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
    )
    return p


@pytest.fixture
def go_sample(tmp_path: Path) -> Path:
    """A small Go file with a package, import, and function."""
    p = tmp_path / "main.go"
    p.write_text(
        "package main\n"
        "\n"
        "import \"fmt\"\n"
        "\n"
        "func greet(name string) string {\n"
        '    return "Hello, " + name\n'
        "}\n"
        "\n"
        "type Person struct {\n"
        "    Name string\n"
        "}\n"
    )
    return p


@pytest.fixture
def ts_sample(tmp_path: Path) -> Path:
    """A small TypeScript file with import, interface, function, and class."""
    p = tmp_path / "sample.ts"
    p.write_text(
        "import { Component } from './component';\n"
        "\n"
        "interface Props {\n"
        "    title: string;\n"
        "}\n"
        "\n"
        "function greet(name: string): string {\n"
        '    return `Hello, ${name}`;\n'
        "}\n"
        "\n"
        "class MyComponent implements Props {\n"
        "    title: string;\n"
        "    constructor(title: string) {\n"
        "        this.title = title;\n"
        "    }\n"
        "}\n"
    )
    return p


@pytest.fixture
def yaml_sample(tmp_path: Path) -> Path:
    """A small YAML file with mappings."""
    p = tmp_path / "config.yaml"
    p.write_text(
        "server:\n"
        "  host: localhost\n"
        "  port: 8080\n"
        "database:\n"
        "  url: postgres://localhost:5432/db\n"
        "  pool:\n"
        "    min: 1\n"
        "    max: 10\n"
    )
    return p


@pytest.fixture
def tf_sample(tmp_path: Path) -> Path:
    """A small Terraform file with a resource block."""
    p = tmp_path / "main.tf"
    p.write_text(
        "resource \"aws_instance\" \"web\" {\n"
        "  ami           = \"ami-12345\"\n"
        "  instance_type = \"t2.micro\"\n"
        "\n"
        "  tags = {\n"
        "    Name = \"web-instance\"\n"
        "  }\n"
        "}\n"
        "\n"
        "variable \"region\" {\n"
        "  default = \"us-east-1\"\n"
        "}\n"
    )
    return p


@pytest.fixture
def empty_py(tmp_path: Path) -> Path:
    """An empty Python file."""
    p = tmp_path / "empty.py"
    p.write_text("")
    return p


# ======================================================================
#  Edge cases
# ======================================================================

class TestEdgeCases:
    def test_unsupported_extension(self, tmp_path: Path):
        """An unsupported file extension should return an error dict."""
        f = tmp_path / "data.xyz"
        f.write_text("anything")
        result = get_complexity(str(f))
        assert "error" in result
        assert "Unsupported" in result["error"]

    def test_file_not_found(self):
        """A non-existent file should return a 'File not found' error."""
        result = get_complexity("/nonexistent/path/foo.py")
        assert "error" in result
        assert "not found" in result["error"]

    def test_non_utf8_file_returns_error(self, tmp_path: Path):
        """A binary file that cannot be decoded as UTF-8 should return an error."""
        f = tmp_path / "binary.py"
        f.write_bytes(b"\x80\x81\x82\x83")  # invalid UTF-8
        result = get_complexity(str(f))
        assert "error" in result
        assert "Could not decode" in result["error"]

    def test_empty_file_returns_zero_counts(self, empty_py: Path):
        """An empty file should parse successfully with zero counts."""
        result = get_complexity(str(empty_py))
        assert "error" not in result
        assert result["line_count"] == 0
        assert result["node_count"] >= 1  # root node always exists
        assert result["def_count"] == 0
        assert result["import_count"] == 0
        assert result["max_depth"] == 0  # root has no children


# ======================================================================
#  Language-specific parsing
# ======================================================================

class TestPython:
    def test_python_metrics(self, py_sample: Path):
        """A small Python file should produce reasonable complexity metrics."""
        result = get_complexity(str(py_sample))
        assert "error" not in result, result.get("error")
        assert result["filepath"] == str(py_sample)
        assert result["language"] == "python"
        assert result["line_count"] >= 10
        assert result["import_count"] >= 2  # import os, import sys
        assert result["def_count"] >= 2     # greet function + Calculator class
        assert result["max_depth"] > 1
        assert isinstance(result["complexity_score"], float)
        assert result["complexity_score"] > 0


class TestGo:
    def test_go_metrics(self, go_sample: Path):
        """A small Go file should produce correct metrics."""
        result = get_complexity(str(go_sample))
        assert "error" not in result, result.get("error")
        assert result["language"] == "go"
        assert result["import_count"] >= 1
        assert result["def_count"] >= 2   # func + type declaration


class TestTypeScript:
    def test_typescript_metrics(self, ts_sample: Path):
        """A small TypeScript file should produce correct metrics."""
        result = get_complexity(str(ts_sample))
        assert "error" not in result, result.get("error")
        assert result["language"] == "typescript"
        assert result["import_count"] >= 1
        assert result["def_count"] >= 4   # interface + function + class + constructor


class TestYaml:
    def test_yaml_metrics(self, yaml_sample: Path):
        """A small YAML file should produce correct metrics."""
        result = get_complexity(str(yaml_sample))
        assert "error" not in result, result.get("error")
        assert result["language"] == "yaml"
        # YAML definitions = block_mapping_pair count
        assert result["def_count"] >= 5   # server, host, port, database, url, etc.
        assert result["node_count"] > 0


class TestTerraform:
    def test_tf_metrics(self, tf_sample: Path):
        """A small Terraform file should produce correct metrics."""
        result = get_complexity(str(tf_sample))
        assert "error" not in result, result.get("error")
        assert result["language"] == "hcl"
        assert result["def_count"] >= 2   # resource + variable blocks


# ======================================================================
#  Result structure
# ======================================================================

class TestResultStructure:
    def test_result_contains_all_keys(self, py_sample: Path):
        """The returned dict should contain all expected keys."""
        result = get_complexity(str(py_sample))
        expected_keys = {
            "filepath", "max_depth", "node_count", "line_count",
            "def_count", "import_count", "complexity_score", "language"
        }
        assert expected_keys.issubset(result.keys())
