import os
from typing import Dict, Any, Optional
from tree_sitter import Language, Parser
import tree_sitter_python as tspython
import tree_sitter_go as tsgo
import tree_sitter_typescript as tstypescript
import tree_sitter_yaml as tsyaml
import tree_sitter_hcl as tshcl

def get_complexity(filepath: str) -> Dict[str, Any]:
    """Calculate complexity metrics for a source file."""
    ext = os.path.splitext(filepath)[1]
    
    # Initialize languages
    languages = {
        ".py": Language(tspython.language()),
        ".go": Language(tsgo.language()),
        ".ts": Language(tstypescript.language_typescript()),
        ".tsx": Language(tstypescript.language_tsx()),
        ".yaml": Language(tsyaml.language()),
        ".yml": Language(tsyaml.language()),
        ".tf": Language(tshcl.language())
    }
    
    lang = languages.get(ext)
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
        lines = content.decode("utf8").splitlines()
    except UnicodeDecodeError:
        return {"error": "Could not decode file as UTF-8"}
        
    line_count = len(lines)
    
    # Definition types per language
    def_types = {
        "python": ("function_definition", "class_definition"),
        "go": ("function_declaration", "method_declaration", "type_declaration"),
        "typescript": (
            "function_declaration", "method_definition", "class_declaration", 
            "interface_declaration", "type_alias_declaration", "enum_declaration",
            "arrow_function"
        ),
        "yaml": ("block_mapping_pair",),
        "hcl": ("block",)
    }
    
    if ext == ".py":
        lang_name = "python"
    elif ext == ".go":
        lang_name = "go"
    elif ext in (".ts", ".tsx"):
        lang_name = "typescript"
    elif ext in (".yaml", ".yml"):
        lang_name = "yaml"
    elif ext == ".tf":
        lang_name = "hcl"
    else:
        lang_name = "unknown"
        
    target_types = def_types.get(lang_name, ())
    
    def count_defs(node):
        count = 1 if node.type in target_types else 0
        return count + sum(count_defs(child) for child in node.children)
        
    def_count = count_defs(root)
    
    # Dependency count (import statements)
    import_types = {
        "python": ("import_statement", "import_from_statement"),
        "go": ("import_declaration",),
        "typescript": ("import_statement",)
    }
    target_imports = import_types.get(lang_name, ())
    
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
