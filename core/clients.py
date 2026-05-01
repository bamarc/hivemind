import logging
import threading
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential
from qdrant_client import QdrantClient, models
from openai import OpenAI

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy client initialisation – clients are created on first access so that
# callers can import the factory functions without triggering connection
# setup, and so that tests can easily inject mocks via patch().
#
# A lock protects against concurrent initialisation from multiple threads
# (e.g. several IndexWorkers calling get_db() simultaneously).
# ---------------------------------------------------------------------------
_db: Optional[QdrantClient] = None
_embedder: Optional[OpenAI] = None
_chat_client: Optional[OpenAI] = None
_clients_lock = threading.Lock()


def get_db() -> QdrantClient:
    """Return a lazily-initialised QdrantClient singleton (thread-safe)."""
    global _db
    if _db is None:
        with _clients_lock:
            if _db is None:
                from .config import settings

                _db = QdrantClient(
                    url=settings.qdrant.url,
                    api_key=settings.qdrant.api_key.get_secret_value()
                    if settings.qdrant.api_key
                    else None,
                )
    return _db


def get_embedder() -> OpenAI:
    """Return a lazily-initialised OpenAI client for embeddings (thread-safe)."""
    global _embedder
    if _embedder is None:
        with _clients_lock:
            if _embedder is None:
                from .config import settings

                _embedder = OpenAI(
                    base_url=settings.model.api_url,
                    api_key=settings.model.api_key.get_secret_value()
                    if settings.model.api_key
                    else "empty",
                )
    return _embedder


def get_chat_client() -> OpenAI:
    """Return a lazily-initialised OpenAI client for chat (thread-safe)."""
    global _chat_client
    if _chat_client is None:
        with _clients_lock:
            if _chat_client is None:
                from .config import settings

                _chat_client = OpenAI(
                    base_url=settings.chat.api_url,
                    api_key=settings.chat.api_key.get_secret_value()
                    if settings.chat.api_key
                    else "empty",
                )
    return _chat_client

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True
)
def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Fetch embeddings for a list of texts from the model API with retry logic."""
    if not texts:
        return []

    client = get_embedder()
    from .config import settings

    all_embeddings = []
    batch_size = settings.model.batch_size

    # Process in sub-batches to avoid API limits
    for i in range(0, len(texts), batch_size):
        sub_batch = texts[i : i + batch_size]
        try:
            response = client.embeddings.create(
                input=sub_batch,
                model=settings.model.model_name
            )
            all_embeddings.extend([item.embedding for item in response.data])
        except Exception as e:
            logger.error(f"Failed to fetch batch embeddings: {e}")
            raise

    return all_embeddings

def get_embedding(text: str) -> list[float]:
    """Fetch embedding from the model API with retry logic.

    Raises:
        ValueError: If the embedding service returns no result for the given text.
    """
    results = get_embeddings_batch([text])
    if not results:
        raise ValueError(f"Embedding returned empty result for text of length {len(text)}")
    return results[0]

def check_qdrant_connection() -> bool:
    """Verify connection to Qdrant."""
    try:
        get_db().get_collections()
        return True
    except Exception:
        return False


def init_collection():
    """Ensure the target collection exists in Qdrant before indexing.

    Also validates that the embedding dimension matches any existing
    collection to detect model changes early.
    """
    from .config import settings

    client = get_db()
    try:
        collections_response = client.get_collections()
        existing_collections = [col.name for col in collections_response.collections]

        if settings.qdrant.collection_name not in existing_collections:
            logger.info(
                f"Creating new Qdrant collection: {settings.qdrant.collection_name}"
            )
            client.create_collection(
                collection_name=settings.qdrant.collection_name,
                vectors_config=models.VectorParams(
                    size=settings.model.embedding_dim,
                    distance=models.Distance.COSINE,
                ),
            )
            # Create payload indexes for metadata-aware filtering
            client.create_payload_index(
                collection_name=settings.qdrant.collection_name,
                field_name="type",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
            _create_path_segment_indexes(client)
        else:
            # Validate embedding dimension matches existing collection
            collection_info = client.get_collection(
                collection_name=settings.qdrant.collection_name
            )
            existing_dim = collection_info.config.params.vectors.size
            configured_dim = settings.model.embedding_dim
            if existing_dim != configured_dim:
                raise ValueError(
                    f"Embedding dimension mismatch: existing collection has "
                    f"dimension {existing_dim}, but configuration specifies "
                    f"{configured_dim}. Please update 'embedding_dim' in your "
                    f"config or delete the collection to recreate it."
                )
            logger.debug(
                f"Collection '{settings.qdrant.collection_name}' already exists "
                f"(dim={existing_dim})."
            )
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Failed to initialize Qdrant collection: {e}")
        raise


def _create_path_segment_indexes(client: QdrantClient) -> None:
    """Create payload indexes for path segments 0 through 4.

    The number of indexed segments is deliberately limited since most
    project structures don't exceed 5 meaningful depth levels.
    """
    from .config import settings

    num_segments = 5
    for i in range(num_segments):
        client.create_payload_index(
            collection_name=settings.qdrant.collection_name,
            field_name=f"path_segments.{i}",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
        logger.debug(f"Created payload index for path_segments.{i}")
