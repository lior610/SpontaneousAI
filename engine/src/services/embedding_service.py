"""
Embedding Service - Text to Vector Conversion.

This service handles the conversion of text into embedding vectors for semantic search.
Embeddings are numerical representations of text that capture semantic meaning,
allowing similarity comparisons between different texts.

Flow: Text → Embedding Service → Vector → Vector Search → Database

Note:
    This is a placeholder service. Implementation should use:
    - OpenAI embeddings API
    - Sentence transformers (Hugging Face)
    - Or other embedding models
"""
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
    """
    Generate a single embedding vector from text.
    
    This converts natural language text into a numerical vector representation
    that can be used for semantic similarity search.
    
    Args:
        text: Input text to embed (e.g., "romantic dinner spots in Paris")
        
    Returns:
        List of floats representing the embedding vector
        
    Note:
        When implementing, only embed fields with semantic meaning:
        - Name, description, tags, categories
        - Skip purely numerical or structural fields
    """
    model = _get_model()
    # Run encoding in thread pool to avoid blocking
    embedding = await asyncio.to_thread(model.encode, text)
    return embedding.tolist()


async def generate_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for multiple texts in a single batch operation.
    
    Batch processing is more efficient than calling generate_embedding
    multiple times, especially when using API-based embedding services.
    
    Args:
        texts: List of texts to embed
        
    Returns:
        List of embedding vectors, one per input text
        
    Note:
        Maintains order: results[i] corresponds to texts[i]
    """
    model = _get_model()
    # Run batch encoding in thread pool to avoid blocking
    embeddings = await asyncio.to_thread(model.encode, texts)
    return [emb.tolist() for emb in embeddings]


def get_embedding_dimension() -> int:
    """
    Get the dimension of embeddings produced by the model.
    
    This is useful for database schema creation and validation.
    
    Returns:
        Integer representing the embedding vector dimension
    """
    model = _get_model()
    return model.get_sentence_embedding_dimension()


