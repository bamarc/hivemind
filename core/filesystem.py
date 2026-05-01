"""
Filesystem utility functions for the Hivemind pipeline.

This module provides safe filesystem traversal and inspection functions
that are used by both the indexer and server components.  By centralising
disk I/O here we keep the AGENTS.md boundary clean: the server never
reads local files directly.
"""

import os
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# Directories / file patterns that should never be walked or indexed.
# Shared across the filesystem module, indexer scanner, and code handler.
EXCLUDED_DIRS = frozenset({
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    "build", "dist", ".idea", ".vscode", ".kilocode",
})

_EXCLUDED_PREFIXES = (".", "__")


def _is_excluded(name: str) -> bool:
    """Return ``True`` if *name* should be skipped during tree walks."""
    return name in EXCLUDED_DIRS or name.startswith(_EXCLUDED_PREFIXES)


def get_file_tree(root_path: str, depth: int = 2) -> str:
    """Build a tree-like view of the directory structure at *root_path*.

    Parameters
    ----------
    root_path:
        Absolute or relative path to the root directory.
    depth:
        Maximum depth of subdirectories to recurse into (default 2).

    Returns
    -------
    str
        A human-readable tree representation, or an error message prefixed
        with ``"Error: "``.
    """
    root = Path(root_path).absolute()

    if not root.exists():
        return f"Error: Path {root} does not exist."
    if not root.is_dir():
        return f"Error: Path {root} is not a directory."

    tree_lines: List[str] = [f"# File Tree for {root.name}"]

    def walk(current: Path, current_depth: int, prefix: str = "") -> None:
        if current_depth > depth:
            return

        try:
            items = sorted(
                current.iterdir(),
                key=lambda x: (not x.is_dir(), x.name),
            )
        except PermissionError:
            return
        except Exception as exc:
            logger.error("Error walking tree at %s: %s", current, exc)
            return

        for i, item in enumerate(items):
            if _is_excluded(item.name):
                continue

            is_last = i == len(items) - 1
            connector = "└── " if is_last else "├── "
            suffix = "/" if item.is_dir() else ""
            tree_lines.append(f"{prefix}{connector}{item.name}{suffix}")

            if item.is_dir():
                new_prefix = prefix + ("    " if is_last else "│   ")
                walk(item, current_depth + 1, new_prefix)

    walk(root, 1)
    return "\n".join(tree_lines)


def file_contents(filepath: str) -> Optional[str]:
    """Read a text file and return its contents.

    Returns ``None`` if the file cannot be read (permissions, encoding,
    not found, etc.).
    """
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except FileNotFoundError:
        logger.warning("File not found: %s", filepath)
        return None
    except Exception as exc:
        logger.error("Failed to read file %s: %s", filepath, exc)
        return None
