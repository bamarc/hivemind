import sys
import time
from watchdog.observers import Observer
from indexer.watcher import CodeHandler
from core.clients import get_db, init_collection
from core.config import settings
from qdrant_client import models

def init_db():
    """Ensure the collection exists in Qdrant before starting, with
    dimension validation (delegates to the canonical ``init_collection``)."""
    init_collection()

if __name__ == "__main__":
    # This is a simple CLI wrapper for backward compatibility.
    # The main entry point is `hivemind indexer start <path>` via main.py.
    import sys
    from pathlib import Path
    from indexer.watcher import Indexer
    from core.clients import init_collection
    
    if len(sys.argv) < 2:
        print("Usage: uv run python -m cli.run_indexer <path_to_watch>")
        sys.exit(1)
    
    init_collection()
    target_path = Path(sys.argv[1])
    indexer = Indexer()
    try:
        indexer.start(target_path, watch=True)
    except KeyboardInterrupt:
        indexer.stop()
