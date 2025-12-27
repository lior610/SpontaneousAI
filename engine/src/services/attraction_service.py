"""
Attraction Service - Business logic entrypoint for attractions.
Calling this service from API/handlers 
"""

import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

# Ensure shared python path is available (for db/embedding if needed)
shared_path = str(Path(__file__).resolve().parents[3] / "shared" / "python")
if shared_path not in sys.path:
    sys.path.insert(0, shared_path)

from src.services.embedding_service import generate_embedding
from src.search.vector_search import search_similar_attractions


async def get_attraction_by_id(attraction_id: str) -> Optional[Dict[str, Any]]:
    """Get attraction by ID (stub)."""
    # TODO: Implement database query
    return None


async def create_attraction(attraction_data: dict) -> dict:
    """
    Create a new attraction (from scraping).
    Generates embedding and stores in database (stub).
    """
    attraction_text = f"{attraction_data.get('name', '')} {attraction_data.get('description', '')}"
    embedding = await generate_embedding(attraction_text)
    # TODO: Store attraction + embedding in database
    return {**attraction_data, "embedding": embedding}


async def search_attractions(
    query_text: str,
    limit: int = 10,
    min_similarity: Optional[float] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Service-level search entrypoint.
    - Generates embedding from query text
    - Applies hard filters (passed through) in vector_search
    """
    query_embedding = await generate_embedding(query_text)
    return search_similar_attractions(
        query_embedding=query_embedding,
        limit=limit,
        min_similarity=min_similarity,
        filters=filters or {},
    )