import sys
import time
from watchdog.observers import Observer
from indexer.watcher import CodeHandler
from core.clients import db, COLLECTION_NAME, EMBED_DIM
from qdrant_client.http.models import Distance, VectorParams

def init_db():
    """Ensure the collection exists in Qdrant before starting."""
    if not db.collection_exists(collection_name=COLLECTION_NAME):
        print(f"[CLI] Initializing collection: {COLLECTION_NAME}")
        db.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
        )

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run python -m cli.run_indexer <path_to_watch>")
        sys.exit(1)
        
    init_db()
    
    target_path = sys.argv[1]
    event_handler = CodeHandler()
    observer = Observer()
    observer.schedule(event_handler, target_path, recursive=True)
    
    print(f"[CLI] Deploying Indexer to monitor: {target_path}")
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
