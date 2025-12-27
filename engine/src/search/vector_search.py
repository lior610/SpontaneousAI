"""
Vector Search Module - Performs semantic similarity search using pgvector.
"""
from typing import List, Dict, Any, Optional
import sys
from pathlib import Path

# Ensure shared python path is available
shared_path = str(Path(__file__).resolve().parents[3] / "shared" / "python")
if shared_path not in sys.path:
    sys.path.insert(0, shared_path)

from db.attractionsConnection import get_db_connection
from src.db.attractions_queries import fetch_similar_attractions


def _to_pgvector_str(query_embedding: Any) -> str:
    """Convert embedding to pgvector format string."""
    if isinstance(query_embedding, str):
        return query_embedding
    if hasattr(query_embedding, "__iter__"):
        return "[" + ",".join(map(str, query_embedding)) + "]"
    raise ValueError("query_embedding must be a list of floats or a string")


def _normalize_row(row_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize data types for the response."""
    if row_dict.get("activity_id"):
        row_dict["activity_id"] = str(row_dict["activity_id"])
    if row_dict.get("embedding"):
        row_dict["embedding"] = list(row_dict["embedding"])
    if "similarity" in row_dict:
        row_dict["similarity"] = float(row_dict["similarity"])
    return row_dict


def search_similar_attractions(
    query_embedding: List[float],
    limit: int = 10,
    min_similarity: Optional[float] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Find attractions similar to the query embedding.

    Args:
        query_embedding: Embedding vector (list of floats)
        limit: Return top X results (default: 10)
        min_similarity: Optional minimum similarity score (0-1, where 1 = identical)

    Returns:
        List of attraction dicts with a 'similarity' score (0-1, higher = more similar)
    """
    if not query_embedding:
        return []

    embedding_str = _to_pgvector_str(query_embedding)
    results: List[Dict[str, Any]] = []

    try:
        with get_db_connection() as conn:
            rows, column_names = fetch_similar_attractions(
                conn=conn,
                embedding_str=embedding_str,
                limit=limit,
                min_similarity=min_similarity,
                filters=filters or {},
            )

            for row in rows:
                attraction = dict(zip(column_names, row))
                results.append(_normalize_row(attraction))

    except Exception as e:
        raise RuntimeError(f"Error performing vector search: {str(e)}") from e

    return results
