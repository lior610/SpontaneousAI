"""
Vector Search Module - Performs semantic similarity search using pgvector
"""
from typing import List, Dict, Any, Optional
from src.db.attractionsConnection import get_db_connection


def search_similar_attractions(
    query_embedding: List[float],
    limit: int = 10,
    min_similarity: Optional[float] = None
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
    
    # Convert embedding to pgvector format string
    if isinstance(query_embedding, str):
        # Already a string (e.g. from database), use as-is
        embedding_str = query_embedding
    elif hasattr(query_embedding, '__iter__'):
        # It's a list/array, convert to pgvector format
        embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
    else:
        raise ValueError("query_embedding must be a list of floats or a string")
    
    # Build SQL query with cosine similarity search
    # <=> is pgvector's cosine distance operator (0 = identical, 2 = opposite)
    query = """
        SELECT 
            activity_id,
            source,
            source_ref,
            created_at,
            updated_at,
            last_seen_at,
            name,
            short_description,
            categories,
            tags,
            good_for,
            indoor_outdoor,
            typical_duration_min,
            effort_level,
            lat,
            lng,
            city,
            country,
            opening_hours,
            is_open_now,
            timezone,
            price_level,
            estimated_cost_bucket,
            rating,
            requires_booking,
            age_min,
            accessibility_features,
            embedding,
            (1 - (embedding <=> %s::vector) / 2) as similarity
        FROM attractions
        WHERE embedding IS NOT NULL
    """
    
    # Add similarity threshold filter if provided
    params = [embedding_str]
    if min_similarity is not None:
        max_distance = 2 * (1 - min_similarity)  # Convert similarity to distance
        query += " AND (embedding <=> %s::vector) <= %s"
        params.extend([embedding_str, max_distance])
    
    # Order by similarity and limit results
    query += " ORDER BY embedding <=> %s::vector LIMIT %s"
    params.extend([embedding_str, limit])
    
    results = []
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Execute query with parameters
            cursor.execute(query, tuple(params))
            
            # Fetch all results
            rows = cursor.fetchall()
            
            # Get column names
            column_names = [desc[0] for desc in cursor.description]
            
            # Convert rows to dicts and format data types
            for row in rows:
                attraction = dict(zip(column_names, row))
                if attraction.get('activity_id'):
                    attraction['activity_id'] = str(attraction['activity_id'])
                if attraction.get('embedding'):
                    attraction['embedding'] = list(attraction['embedding'])
                if 'similarity' in attraction:
                    attraction['similarity'] = float(attraction['similarity'])
                results.append(attraction)
            
            cursor.close()
    
    except Exception as e:
        raise RuntimeError(f"Error performing vector search: {str(e)}") from e
    
    return results

