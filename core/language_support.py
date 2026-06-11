"""Shared language definitions for tree-sitter parsing across the codebase."""

from typing import Dict, Tuple
from tree_sitter import Language

# ── Import-time imports of the binding modules are cheap (they don't
#    construct Language objects), so these stay at the top level.
import tree_sitter_python as tspython
import tree_sitter_go as tsgo
import tree_sitter_typescript as tstypescript
import tree_sitter_yaml as tsyaml
import tree_sitter_hcl as tshcl
import tree_sitter_java as tsjava
import tree_sitter_c_sharp as tscsharp
import tree_sitter_rust as tsrust
import tree_sitter_cpp as tscpp
import tree_sitter_c as tsc
import tree_sitter_javascript as tsjavascript

# ---------------------------------------------------------------------------
# Extension → language name
# ---------------------------------------------------------------------------
EXTENSION_TO_LANG_NAME: Dict[str, str] = {
    ".py": "python",
    ".go": "go",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".tf": "hcl",
    ".java": "java",
    ".cs": "c_sharp",
    ".rs": "rust",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".c": "c",
    ".h": "c",
}

# ---------------------------------------------------------------------------
# Extension → tree-sitter Language factory (lazy – Language objects are
# expensive to construct and should only be created when actually needed
# for parsing, not on every import of this module).
# ---------------------------------------------------------------------------

_LANGUAGE_FACTORIES: Dict[str, "callable"] = {
    ".py": lambda: Language(tspython.language()),
    ".go": lambda: Language(tsgo.language()),
    ".js": lambda: Language(tsjavascript.language()),
    ".ts": lambda: Language(tstypescript.language_typescript()),
    ".tsx": lambda: Language(tstypescript.language_tsx()),
    ".yaml": lambda: Language(tsyaml.language()),
    ".yml": lambda: Language(tsyaml.language()),
    ".tf": lambda: Language(tshcl.language()),
    ".java": lambda: Language(tsjava.language()),
    ".cs": lambda: Language(tscsharp.language()),
    ".rs": lambda: Language(tsrust.language()),
    ".cpp": lambda: Language(tscpp.language()),
    ".cc": lambda: Language(tscpp.language()),
    ".cxx": lambda: Language(tscpp.language()),
    ".hpp": lambda: Language(tscpp.language()),
    ".c": lambda: Language(tsc.language()),
    ".h": lambda: Language(tsc.language()),
}

# Lazily-initialised cache of Language objects keyed by extension.
_cache: Dict[str, Language] = {}


def get_language(ext: str) -> Language:
    """Return the tree-sitter :class:`Language` for *ext*, creating it on
    first access (lazy initialisation)."""
    lang = _cache.get(ext)
    if lang is None:
        factory = _LANGUAGE_FACTORIES.get(ext)
        if factory is None:
            raise KeyError(f"No tree-sitter language for extension {ext!r}")
        lang = _cache[ext] = factory()
    return lang


# Backward-compatible dict interface used by ``chunkers/ast.py`` and
# ``complexity.py`` via ``EXTENSION_TO_LANGUAGE.get(ext)``.
# This provides a read-only mapping that delegates to ``get_language()``.
class _LanguageMapping:
    """A dict-like mapping from extension to Language, creating them lazily."""

    def get(self, key, default=None):
        try:
            return get_language(key)
        except KeyError:
            return default

    def __contains__(self, key):
        return key in _LANGUAGE_FACTORIES

    def __getitem__(self, key):
        return get_language(key)

    def __repr__(self):
        return repr(dict(self))

    def keys(self):
        return _LANGUAGE_FACTORIES.keys()

    def __iter__(self):
        return iter(_LANGUAGE_FACTORIES)


EXTENSION_TO_LANGUAGE: _LanguageMapping = _LanguageMapping()

# ---------------------------------------------------------------------------
# Language name → definition node types
# ---------------------------------------------------------------------------
DEFINITION_TYPES: Dict[str, Tuple[str, ...]] = {
    "python": ("function_definition", "class_definition"),
    "go": ("function_declaration", "method_declaration", "type_declaration"),
    "javascript": ("function_declaration", "class_declaration", "arrow_function", "variable_declaration"),
    "typescript": (
        "function_declaration", "method_definition", "class_declaration",
        "interface_declaration", "type_alias_declaration", "enum_declaration",
        "arrow_function", "variable_declaration"
    ),
    "yaml": ("block_mapping_pair",),
    "hcl": ("block",),
    "java": ("class_declaration", "method_declaration", "interface_declaration", "enum_declaration"),
    "c_sharp": ("class_declaration", "method_declaration", "interface_declaration", "enum_declaration", "struct_declaration"),
    "rust": ("function_item", "impl_item", "struct_item", "enum_item", "trait_item"),
    "cpp": ("function_definition", "class_specifier", "struct_specifier"),
    "c": ("function_definition", "struct_specifier"),
}

# ---------------------------------------------------------------------------
# Language name → import node types
# ---------------------------------------------------------------------------
IMPORT_TYPES: Dict[str, Tuple[str, ...]] = {
    "python": ("import_statement", "import_from_statement"),
    "go": ("import_declaration",),
    "javascript": ("import_statement",),
    "typescript": ("import_statement",),
    "java": ("import_declaration",),
    "c_sharp": ("using_directive",),
    "rust": ("use_declaration",),
    "cpp": ("preproc_include",),
    "c": ("preproc_include",),
}
