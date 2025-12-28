"""
Attraction Service - Business Logic Layer.

This is the main entry point for attraction-related business logic.
It orchestrates operations across multiple layers:
- Embedding generation
- Filter building
- Search execution

Flow: API Routes → Attraction Service → (Embedding Service, Vector Search) → Database

Responsibilities:
- Transform API requests into business operations
- Build filters from user context
- Orchestrate embedding generation and search
- Handle business-level validation and logic
"""

import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

shared_path = str(Path(__file__).resolve().parents[3] / "shared" / "python")
if shared_path not in sys.path:
    sys.path.insert(0, shared_path)

from src.services.embedding_service import generate_embedding
from src.search.vector_search import search_similar_attractions
from src.search.hard_filters import build_hard_filters
from src.search.soft_filters import apply_soft_filters


async def get_attraction_by_id(attraction_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a single attraction by its ID.
    
    Args:
        attraction_id: Unique identifier for the attraction
        
    Returns:
        Attraction dictionary if found, None otherwise
        
    Note:
        This is a stub - implementation needed
    """
    # TODO: Implement database query to fetch by ID
    return None


async def create_attraction(attraction_data: dict) -> dict:
    """
    Create a new attraction with generated embedding.
    
    This is typically called from the data pipeline when scraping new attractions.
    It generates an embedding from the attraction's text content and prepares
    the data for storage.
    
    Args:
        attraction_data: Dictionary containing attraction information
        
    Returns:
        Dictionary with attraction data including generated embedding
        
    Note:
        Database storage is not yet implemented - this is a stub
    """
    # Build text for embedding from relevant fields
    attraction_text = f"{attraction_data.get('name', '')} {attraction_data.get('description', '')}"
    
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
    """
    Search for attractions using semantic similarity.
    
    This is the main search entrypoint. It:
    1. Generates an embedding from the query text  - When he have embedding service, use it here
    2. Builds hard filters from user context
    3. Executes vector similarity search
    4. Returns ranked results
    
    Args:
        query_text: Natural language search query (e.g., "romantic dinner spots")
        limit: Maximum number of results to return (default: 10)
        min_similarity: Optional minimum similarity threshold (0-1)
        context: Optional user context for filtering (city, country, is_open_now, etc.)
        
    Returns:
        List of attraction dictionaries, sorted by similarity score (highest first)
        
    """
    # Step 1: Generate embedding from query text
    query_embedding = await generate_embedding(query_text)
    
    # Step 2: Build hard filters (applied at SQL level)
    hard_filters = build_hard_filters(context or {})
    
    # Step 3: Execute vector similarity search
    results = search_similar_attractions(
        query_embedding=query_embedding,
        limit=limit,
        min_similarity=min_similarity,
        filters=hard_filters,
    )
    
    # Step 4: Apply soft filters (post-query scoring and ranking)
    results = apply_soft_filters(results, context)
    
    return results