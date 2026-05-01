import logging
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from core.clients import get_db, get_embedding, check_qdrant_connection
from core.config import settings

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Hivemind REST API",
    version="0.2.0",
    description="REST interface for Hivemind semantic search and embeddings"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth Dependency
async def verify_api_key(x_api_key: str = Header(None, alias=settings.security.api_key_header)):
    # Simple check for demonstration. In prod, load from secrets.yaml
    # For now, if no key is configured, allow all.
    return True

class SearchRequest(BaseModel):
    query: str
    limit: int = 5

class EmbedRequest(BaseModel):
    text: str

@app.get("/health")
async def health():
    """Detailed health check."""
    qdrant_ok = check_qdrant_connection()
    # The embedder status is inferred from Qdrant health: a working embedder
    # is required for indexing, but the health endpoint avoids making an
    # expensive embedding API call on every probe.
    return {
        "status": "healthy" if qdrant_ok else "degraded",
        "components": {
            "qdrant": {
                "status": "connected" if qdrant_ok else "disconnected",
                "collection": settings.qdrant.collection_name
            },
            "embedder": {
                "status": "assumed_ok" if qdrant_ok else "unknown",
                "model": settings.model.model_name
            },
            "version": "0.2.0"
        }
    }

@app.post("/embed", dependencies=[Depends(verify_api_key)])
async def embed(request: EmbedRequest):
    """Expose embedding model."""
    try:
        vector = get_embedding(request.text)
        return {
            "embedding": vector,
            "model": settings.model.model_name
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search", dependencies=[Depends(verify_api_key)])
async def search(request: SearchRequest):
    """Semantic search endpoint."""
    try:
        query_vector = get_embedding(request.query)
        response = get_db().query_points(
            collection_name=settings.qdrant.collection_name,
            query=query_vector,
            limit=request.limit
        )
        search_results = response.points
        return {
            "results": [
                {
                    "filepath": hit.payload.get("filepath"),
                    "content": hit.payload.get("content"),
                    "score": hit.score,
                    "chunk_index": hit.payload.get("chunk_index")
                } for hit in search_results
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics")
async def metrics():
    """Basic metrics."""
    if not settings.observability_metrics_enabled:
        raise HTTPException(status_code=404, detail="Metrics disabled")

    points_count = 0
    if check_qdrant_connection():
        try:
            collection_info = get_db().get_collection(settings.qdrant.collection_name)
            points_count = collection_info.points_count
        except Exception:
            logger.warning("Failed to retrieve collection metrics", exc_info=True)

    return {
        "total_chunks_in_db": points_count,
        "collection_name": settings.qdrant.collection_name,
        "version": "0.2.0"
    }

def run_api(host: str = None, port: int = None):
    import uvicorn
    uvicorn.run(
        app, 
        host=host or settings.api.host, 
        port=port or settings.api.port
    )

if __name__ == "__main__":
    run_api()
