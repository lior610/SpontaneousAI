"""Data access layer for vector similarity search: connection, query, and result formatting."""
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
    Run the similarity query and return normalized attraction dicts (each with a 0-1 'similarity' score).

    Raises:
        RuntimeError: If the database query fails.
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
