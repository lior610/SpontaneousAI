"""
Vector Search Data Access Layer.

This module handles the data access for vector similarity search operations.
It sits between the service layer and the database query layer, handling:
- Connection management
- Result formatting
- Error handling

Flow: Service Layer → Vector Search → Database Queries → Database
"""
from typing import List, Dict, Any, Optional
import sys
from pathlib import Path

# Ensure shared python path is available
shared_path = str(Path(__file__).resolve().parents[3] / "shared" / "python")
if shared_path not in sys.path:
    sys.path.insert(0, shared_path)

from db.attractionsConnection import get_db_connection
from src.db.attractions_queries import execute_similarity_query
from src.utils.formatting import format_embedding_for_pgvector, normalize_attraction_row


def execute_vector_search( 
    query_embedding: List[float],
    limit: int = 10,
    min_similarity: Optional[float] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Execute vector similarity search and return formatted results.
    
    This is the data access layer for vector search. It:
    1. Formats the embedding for database queries
    2. Executes the database query via attractions_queries
    3. Formats and normalizes the results
    4. Handles errors
    
    Args:
        query_embedding: Embedding vector (list of floats)
        limit: Maximum number of results to return (default: 10)
        min_similarity: Optional minimum similarity threshold (0-1, where 1 = identical)
        filters: Optional dictionary of hard filters (city, country, is_open_now, etc.)
    
    Returns:
        List of attraction dictionaries, each with a 'similarity' score (0-1, higher = more similar)
        
    Raises:
        RuntimeError: If database query fails
        ValueError: If embedding format is invalid
    """
    if not query_embedding:
        return []

    embedding_str = format_embedding_for_pgvector(query_embedding)
    results: List[Dict[str, Any]] = []

    try:
        with get_db_connection() as conn:
            rows, column_names = execute_similarity_query(
                conn=conn,
                embedding_str=embedding_str,
                limit=limit,
                min_similarity=min_similarity,
                filters=filters or {},
            )

            # Convert database rows to dictionaries and normalize types
            for row in rows:
                attraction = dict(zip(column_names, row))
                results.append(normalize_attraction_row(attraction))

    except Exception as e:
        raise RuntimeError(f"Error performing vector search: {str(e)}") from e

    return results
