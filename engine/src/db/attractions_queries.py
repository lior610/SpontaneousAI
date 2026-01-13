"""
Database Query Layer for Attractions.

This module contains pure SQL query construction and execution.
It does NOT contain business logic - it only applies filters and queries
that are passed in from higher layers.

Responsibilities:
- Build SQL queries with filters
- Execute queries against the database
- Return raw database results

Flow: Vector Search → Attractions Queries → PostgreSQL
"""
from typing import List, Tuple, Optional, Any, Dict


def _apply_filters(query: str, params: List[Any], filters: Dict[str, Any]) -> Tuple[str, List[Any]]:
    """
    Append WHERE clauses for filters passed from the service layer.
    
    This function applies whatever filters it receives - it does NOT decide
    which filters are "hard" or "soft". That decision is made in the service layer.
    
    Filter keys must match database column names exactly (no mapping needed).
    
    Supported filter types:
    - Equality filters: {"country": "France"} -> "country = %s"
    - Boolean filters: {"is_open_now": True} -> "is_open_now = TRUE"
    
    Args:
        query: SQL query string (must already have a WHERE clause)
        params: List of query parameters
        filters: Dictionary of filters to apply (keys = database column names)
        
    Returns:
        Tuple of (modified query string, updated parameters list)
    """
    for column_name, filter_value in filters.items():
        if filter_value is None:
            continue
        
        # Handle boolean filters
        if isinstance(filter_value, bool):
            if filter_value:
                query += f" AND {column_name} = TRUE"
            else:
                query += f" AND {column_name} = FALSE"
        # Handle equality filters
        else:
            query += f" AND {column_name} = %s"
            params.append(filter_value)
    
    return query, params


def _apply_similarity_constraints(
    query: str,
    params: List[Any],
    embedding_str: str,
    min_similarity: Optional[float],
    limit: int,
) -> Tuple[str, List[Any]]:
    """
    Append similarity threshold and ordering clauses.
    
    Uses pgvector cosine distance operator (<=>) for similarity calculation.
    Similarity score = 1 - (distance / 2), where distance is 0-2.
    
    Args:
        query: SQL query string
        params: List of query parameters
        embedding_str: Embedding in pgvector string format
        min_similarity: Optional minimum similarity threshold (0-1)
        limit: Maximum number of results
        
    Returns:
        Tuple of (modified query string, updated parameters list)
    """
    # Apply minimum similarity threshold if specified
    if min_similarity is not None:
        # Convert similarity (0-1) to max distance (0-2)
        # similarity = 1 - (distance / 2)  =>  distance = 2 * (1 - similarity)
        max_distance = 2 * (1 - min_similarity)
        query += " AND (embedding <=> %s::vector) <= %s"
        params.extend([embedding_str, max_distance])

    # Order by similarity (ascending distance = descending similarity)
    query += " ORDER BY embedding <=> %s::vector LIMIT %s"
    params.extend([embedding_str, limit])
    
    return query, params


def execute_similarity_query(
    conn,
    embedding_str: str,
    limit: int = 10,
    min_similarity: Optional[float] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Tuple[Any, ...]], List[str]]:
    """
    Execute database query to fetch attractions ordered by vector similarity.
    
    This is a pure database query function. It:
    1. Builds the SQL query with filters
    2. Executes the query
    3. Returns raw database results
    
    Args:
        conn: psycopg2 database connection
        embedding_str: Embedding in pgvector string format "[0.1,0.2,...]"
        limit: Maximum number of results to return
        min_similarity: Optional minimum similarity threshold (0-1)
        filters: Optional dictionary of hard filters (city, country, is_open_now, etc.)
        
    Returns:
        Tuple of:
        - rows: List of tuples, each tuple is one attraction row
        - column_names: List of column names matching the row order
        
    Note:
        The similarity score is calculated as: 1 - (cosine_distance / 2)
        This gives a score from 0-1 where 1 is identical and 0 is completely different.
    """
    # Base query: select all attraction fields plus similarity score
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

    params: List[Any] = [embedding_str]

    # Apply filters (service layer decides which filters to pass)
    if filters:
        query, params = _apply_filters(query, params, filters)

    # Apply similarity constraints and ordering
    query, params = _apply_similarity_constraints(
        query=query,
        params=params,
        embedding_str=embedding_str,
        min_similarity=min_similarity,
        limit=limit,
    )

    # Execute query
    cursor = conn.cursor()
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    column_names = [desc[0] for desc in cursor.description]
    cursor.close()

    return rows, column_names


