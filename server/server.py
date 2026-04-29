import sys
import logging
from mcp.server.fastmcp import FastMCP
from core.clients import db, get_embedding, chat_client
from core.config import settings
from core.complexity import get_complexity
from core.planner import generate_blueprint as core_generate_blueprint

# Configure logging to stderr for MCP
logging.basicConfig(
    level=settings.logging.level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

mcp = FastMCP("HivemindServer")

from qdrant_client import models

@mcp.tool()
def semantic_code_search(
    query: str, 
    limit: int = 5,
    root_path: str = None,
    file_filter: str = None,
    language: str = None,
    is_test: bool = None
) -> str:
    """
    Search the codebase for relevant code snippets using natural language.
    
    Args:
        query: The natural language search query.
        limit: Number of results to return (default 5).
        root_path: Optional path to the project root to determine the collection.
        file_filter: Optional substring to filter file paths (e.g., "server/").
        language: Optional language filter (e.g., "python", "typescript").
        is_test: Optional boolean to filter for test files only or exclude them.
    """
    try:
        from pathlib import Path
        root = Path(root_path) if root_path else settings.workspace_path
        collection_name = root.name if root_path else settings.qdrant.collection_name

        logger.info(f"Executing semantic search in '{collection_name}' for: '{query}'")
        query_vector = get_embedding(query)

        # Build Qdrant filter
        must_filters = []
        if file_filter:
            must_filters.append(models.FieldCondition(
                key="filepath", 
                match=models.MatchText(text=file_filter)
            ))
        if language:
            must_filters.append(models.FieldCondition(
                key="language", 
                match=models.MatchValue(value=language)
            ))
        if is_test is not None:
            must_filters.append(models.FieldCondition(
                key="is_test", 
                match=models.MatchValue(value=is_test)
            ))

        search_filter = models.Filter(must=must_filters) if must_filters else None

        response = db.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=limit,
            query_filter=search_filter
        )
        search_results = response.points

        if not search_results:
            return f"No relevant code found in collection '{collection_name}'."

        formatted_results = [f"# Semantic Search Results (Collection: {collection_name})\n"]
        for hit in search_results:
            filepath = hit.payload.get("filepath", "Unknown File")
            content = hit.payload.get("content", "")
            language_hit = hit.payload.get("language", "text")
            
            result = f"### {filepath} (Score: {hit.score:.2f})\n"
            result += f"```{language_hit}\n"
            result += f"{content}\n"
            result += "```\n"
            formatted_results.append(result)

        return "\n".join(formatted_results)

    except Exception as e:
        logger.error(f"Error executing semantic search: {e}")
        return f"Error executing semantic search: {str(e)}"

@mcp.tool()
def get_file_tree(root_path: str = None, depth: int = 2) -> str:
    """
    Get a tree-like overview of the project structure.
    Helpful for understanding the codebase layout before searching.
    
    Args:
        root_path: Optional path to the project root. Defaults to current workspace.
        depth: How many levels deep to show (default 2).
    """
    import os
    from pathlib import Path
    
    root = Path(root_path) if root_path else settings.workspace_path
    root = root.absolute()
    
    if not root.exists():
        return f"Error: Path {root} does not exist."
        
    tree_lines = [f"# File Tree for {root.name}"]
    
    def walk_tree(current_path: Path, current_depth: int, prefix: str = ""):
        if current_depth > depth:
            return
            
        try:
            items = sorted(list(current_path.iterdir()), key=lambda x: (not x.is_dir(), x.name))
        except PermissionError:
            return
        except Exception as e:
            logger.error(f"Error walking tree at {current_path}: {e}")
            return

        for i, item in enumerate(items):
            if item.name.startswith(('.', '__')) or item.name in ('node_modules', 'venv', '.venv', 'build', 'dist', '__pycache__'):
                continue
                
            is_last = (i == len(items) - 1)
            connector = "└── " if is_last else "├── "
            
            tree_lines.append(f"{prefix}{connector}{item.name}{'/' if item.is_dir() else ''}")
            
            if item.is_dir():
                new_prefix = prefix + ("    " if is_last else "│   ")
                walk_tree(item, current_depth + 1, new_prefix)

    walk_tree(root, 1)
    return "\n".join(tree_lines)

@mcp.tool()
def get_index_status(root_path: str = None) -> str:
    """
    Check the current indexing status of the project.
    
    Args:
        root_path: Optional path to the project root. Defaults to current workspace.
    """
    import uuid
    from pathlib import Path
    from qdrant_client import models
    
    root = Path(root_path) if root_path else settings.workspace_path
    root = root.absolute()
    
    # Collection name logic: defaults to current settings, 
    # but we could try to detect it if root_path is different.
    # For now, we assume the collection name matches the project folder name.
    collection_name = root.name if root_path else settings.qdrant.collection_name
    
    meta_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{root}_indexing_metadata"))
    try:
        points = db.retrieve(
            collection_name=collection_name,
            ids=[meta_id]
        )
        if not points:
            return f"Status: Not Indexed. Workspace: {root}\nCollection: {collection_name}\nUse start_indexing to begin."
        
        payload = points[0].payload
        status = "Complete" if payload.get("indexing_complete") else "In Progress / Stale"
        last_indexed = payload.get("last_indexed_at", "Unknown")
        return (
            f"Status: {status}\n"
            f"Last Indexed: {last_indexed}\n"
            f"Workspace: {root}\n"
            f"Collection: {collection_name}"
        )
    except Exception as e:
        logger.error(f"Error retrieving index status: {e}")
        return f"Error retrieving status for {root}: {str(e)}"

@mcp.tool()
def start_indexing(root_path: str = None) -> str:
    """
    Trigger a background indexing task for the specified project.
    
    Args:
        root_path: Optional path to the project root. Defaults to current workspace.
    """
    import subprocess
    import os
    from pathlib import Path
    
    root = Path(root_path) if root_path else settings.workspace_path
    root = root.absolute()
    
    if not root.exists():
        return f"Error: Path {root} does not exist."
    
    try:
        # Trigger the CLI indexer in detached mode.
        # We use 'hivemind' command which should be in the path.
        cmd = ["hivemind", "indexer", "start", str(root), "--detach"]
        
        # We set the CWD to the root path so that 'hivemind' finds the local config.yaml
        p = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            cwd=str(root)
        )
        
        return f"Indexing started for {root} (PID: {p.pid}). Use get_index_status to check progress."
    except Exception as e:
        logger.error(f"Error starting indexer: {e}")
@mcp.tool()
def analyze_code_complexity(filepath: str) -> str:
    """
    Calculate complexity metrics for a file (AST depth, dependencies, etc.).
    Use this to decide if a task should be handled by a small or flagship model.
    """
    import json
    result = get_complexity(filepath)
    if "error" in result:
        return f"Error: {result['error']}"
    
    # Format for readability
    score = result['complexity_score']
    triage = "Escalate to Flagship" if score > 50 else "Suitable for Small/Local Model"
    
    return (
        f"## Complexity Analysis: {os.path.basename(filepath)}\n"
        f"- **Score**: {score} ({triage})\n"
        f"- **AST Depth**: {result['max_depth']}\n"
        f"- **Definitions**: {result['def_count']}\n"
        f"- **Imports**: {result['import_count']}\n"
        f"- **Lines**: {result['line_count']}\n"
    )

@mcp.tool()
def generate_blueprint(task: str, context: str) -> str:
    """
    Generate a structured JSON blueprint for a coding task using a flagship model.
    """
    import json
    blueprint = core_generate_blueprint(task, context)
    return json.dumps(blueprint, indent=2)

@mcp.tool()
def run_verification(filepath: str = None) -> str:
    """
    Run linters and tests for the project or a specific file.
    """
    import subprocess
    import os
    
    root = settings.workspace_path
    
    # Detect project type
    if (root / "package.json").exists():
        cmd = ["npm", "test"]
    elif (root / "pyproject.toml").exists() or (root / "pytest.ini").exists():
        cmd = ["uv", "run", "pytest"]
        if filepath:
            cmd.append(filepath)
    else:
        return "Error: Could not detect test runner (no package.json or pyproject.toml found)."
        
    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            cwd=str(root),
            timeout=60
        )
        
        status = "PASSED" if result.returncode == 0 else "FAILED"
        output = result.stdout + result.stderr
        
        # Keep output concise
        if len(output) > 2000:
            output = output[:1000] + "\n... [TRUNCATED] ...\n" + output[-1000:]
            
        return f"### Verification {status}\nCommand: `{' '.join(cmd)}`\n\n```\n{output}\n```"
    except subprocess.TimeoutExpired:
        return "Error: Verification timed out after 60 seconds."
    except Exception as e:
        return f"Error running verification: {str(e)}"

def run_mcp():
    """Entry point for MCP server."""
    logger.info("Starting Hivemind Server on stdio")
    mcp.run()

if __name__ == "__main__":
    run_mcp()