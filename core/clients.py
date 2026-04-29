import logging
from tenacity import retry, stop_after_attempt, wait_exponential
from qdrant_client import QdrantClient, models
from openai import OpenAI
from .config import settings

logger = logging.getLogger(__name__)

# Initialize clients using settings
# Qdrant Client
db = QdrantClient(
    url=settings.qdrant.url,
    api_key=settings.qdrant.api_key.get_secret_value() if settings.qdrant.api_key else None
)

# OpenAI / LM Studio Clients
embedder = OpenAI(
    base_url=settings.model.api_url,
    api_key=settings.model.api_key.get_secret_value() if settings.model.api_key else "empty"
)

chat_client = OpenAI(
    base_url=settings.chat.api_url,
    api_key=settings.chat.api_key.get_secret_value() if settings.chat.api_key else "empty"
)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True
)
def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Fetch embeddings for a list of texts from the model API with retry logic."""
    if not texts:
        return []
        
    all_embeddings = []
    batch_size = settings.model.batch_size
    
    # Process in sub-batches to avoid API limits
    for i in range(0, len(texts), batch_size):
        sub_batch = texts[i : i + batch_size]
        try:
            response = embedder.embeddings.create(
                input=sub_batch,
                model=settings.model.model_name
            )
            all_embeddings.extend([item.embedding for item in response.data])
        except Exception as e:
            logger.error(f"Failed to fetch batch embeddings: {e}")
            raise
            
    return all_embeddings

def get_embedding(text: str) -> list[float]:
    """Fetch embedding from the model API with retry logic."""
    results = get_embeddings_batch([text])
    return results[0] if results else []

def check_qdrant_connection() -> bool:
    """Verify connection to Qdrant."""
    try:
        db.get_collections()
        return True
    except Exception:
        return False

def init_collection():
    """Ensure the target collection exists in Qdrant before indexing."""
    try:
        collections_response = db.get_collections()
        existing_collections = [col.name for col in collections_response.collections]

        if settings.qdrant.collection_name not in existing_collections:
            logger.info(f"Creating new Qdrant collection: {settings.qdrant.collection_name}")
            db.create_collection(
                collection_name=settings.qdrant.collection_name,
                vectors_config=models.VectorParams(
                    size=settings.model.embedding_dim,
                    distance=models.Distance.COSINE
                )
            )
            # Create payload indexes for metadata-aware filtering
            db.create_payload_index(
                collection_name=settings.qdrant.collection_name,
                field_name="type",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
            for i in range(5):
                db.create_payload_index(
                    collection_name=settings.qdrant.collection_name,
                    field_name=f"path_segments.{i}",
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )
        else:
            logger.debug(f"Collection '{settings.qdrant.collection_name}' already exists.")
    except Exception as e:
        logger.error(f"Failed to initialize Qdrant collection: {e}")
        raise
