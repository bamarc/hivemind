import os
from typing import Dict, Any
from tree_sitter import Parser

from .language_support import EXTENSION_TO_LANGUAGE, EXTENSION_TO_LANG_NAME, DEFINITION_TYPES, IMPORT_TYPES


def get_complexity(filepath: str) -> Dict[str, Any]:
    """Calculate complexity metrics for a source file."""
    ext = os.path.splitext(filepath)[1]

    lang = EXTENSION_TO_LANGUAGE.get(ext)
    if not lang:
        return {"error": f"Unsupported extension {ext}"}

    parser = Parser()
    parser.language = lang

    try:
        with open(filepath, "rb") as f:
            content = f.read()
    except FileNotFoundError:
        return {"error": f"File not found: {filepath}"}

    tree = parser.parse(content)
    root = tree.root_node

    def get_max_depth(node, depth=0):
        if not node.children:
            return depth
        return max(get_max_depth(child, depth + 1) for child in node.children)

    def count_nodes(node):
        return 1 + sum(count_nodes(child) for child in node.children)

    max_depth = get_max_depth(root)
    node_count = count_nodes(root)

    # Simple metrics
    try:
        lines = content.decode("utf8", errors="replace").splitlines()
    except UnicodeDecodeError:
        return {"error": "Could not decode file as UTF-8"}

    line_count = len(lines)

    lang_name = EXTENSION_TO_LANG_NAME.get(ext, "unknown")
    target_types = DEFINITION_TYPES.get(lang_name, ())

    def count_defs(node):
        count = 1 if node.type in target_types else 0
        return count + sum(count_defs(child) for child in node.children)

    def_count = count_defs(root)

    # Dependency count (import statements)
    target_imports = IMPORT_TYPES.get(lang_name, ())

    def count_imports(node):
        count = 1 if node.type in target_imports else 0
        return count + sum(count_imports(child) for child in node.children)

    import_count = count_imports(root)

    # Heuristic complexity score
    # Higher score = more complex
    complexity_score = (max_depth * 0.4) + (node_count * 0.01) + (def_count * 0.5) + (import_count * 0.2)

    return {
        "filepath": filepath,
        "max_depth": max_depth,
        "node_count": node_count,
        "line_count": line_count,
        "def_count": def_count,
        "import_count": import_count,
        "complexity_score": round(complexity_score, 2),
        "language": lang_name
    }
