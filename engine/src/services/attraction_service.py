"""Business logic layer for attractions - orchestrates embedding generation, filter building, and search."""

import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

shared_path = str(Path(__file__).resolve().parents[3] / "shared" / "python")
if shared_path not in sys.path:
    sys.path.insert(0, shared_path)

from src.services.embedding_service import generate_embedding
from src.search.vector_search import execute_vector_search
from src.search.hard_filters import build_hard_filters
from src.search.soft_filters import apply_soft_filters


async def get_attraction_by_id(attraction_id: str) -> Optional[Dict[str, Any]]:
    """Stub - not yet implemented."""
    # TODO: Implement database query to fetch by ID
    return None


async def create_attraction(attraction_data: dict) -> dict:
    """
    Typically called from the data pipeline when scraping new attractions.
    Database storage is not yet implemented - returns the dict with embedding attached.
    """
    # Build text for embedding from relevant fields (description; get-vibe outputs embedding_desc, mapped on load)
    attraction_text = attraction_data.get('description') or attraction_data.get('name', '')
    
    # Generate embedding for semantic search
    embedding = await generate_embedding(attraction_text)
    
    # TODO: Store attraction + embedding in database
    return {**attraction_data, "embedding": embedding}


async def search_attractions(
    query_text: str,
    limit: int = 10,
    min_similarity: Optional[float] = None,
    context: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Main search entrypoint: embed query, build hard filters, run vector search, apply soft filters."""
    # Step 1: Generate embedding from query text
    query_embedding = await generate_embedding(query_text)
    
    # Step 2: Build hard filters (applied at SQL level)
    hard_filters = build_hard_filters(context or {})
    
    # Step 3: Execute vector similarity search
    results = execute_vector_search(
        query_embedding=query_embedding,
        limit=limit,
        min_similarity=min_similarity,
        filters=hard_filters,
    )
    
    # Step 4: Apply soft filters (post-query scoring and ranking)
    results = apply_soft_filters(results, context)
    
    return results