"""Text -> embedding vectors for semantic search, via sentence-transformers."""
from typing import List
from sentence_transformers import SentenceTransformer
import asyncio
from functools import lru_cache

# Model name constant - shared across the codebase
MODEL_NAME = 'all-MiniLM-L6-v2'

# Cache the model instance to avoid reloading
@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    """Get or create the SentenceTransformer model instance (cached)."""
    return SentenceTransformer(MODEL_NAME)


async def generate_embedding(text: str) -> List[float]:
    """Only embed fields with semantic meaning (name, description, tags) — skip numeric/structural ones."""
    model = _get_model()
    # Run encoding in thread pool to avoid blocking
    embedding = await asyncio.to_thread(model.encode, text)
    return embedding.tolist()


async def generate_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Batch version of generate_embedding; results[i] corresponds to texts[i]."""
    model = _get_model()
    # Run batch encoding in thread pool to avoid blocking
    embeddings = await asyncio.to_thread(model.encode, texts)
    return [emb.tolist() for emb in embeddings]


def get_embedding_dimension() -> int:
    model = _get_model()
    return model.get_sentence_embedding_dimension()


