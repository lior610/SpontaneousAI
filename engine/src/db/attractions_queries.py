"""Pure SQL query construction/execution for attractions - no business logic, filters come from the caller."""
from typing import List, Tuple, Optional, Any, Dict


def _apply_filters(query: str, params: List[Any], filters: Dict[str, Any]) -> Tuple[str, List[Any]]:
    """
    Append WHERE clauses for whatever filters it's given — doesn't decide
    hard vs. soft, that's the service layer's call. Keys must match DB
    column names exactly.
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
    """Append similarity threshold + ordering, via pgvector's <=> cosine distance op (similarity = 1 - distance/2)."""
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
    Fetch attractions ordered by vector similarity; returns (rows, column_names).

    Similarity = 1 - (cosine_distance / 2), giving 0-1 where 1 is identical.
    """
    # Base query: select all attraction fields plus similarity score (matches AttractionBase model)
    query = """
        SELECT 
            place_id as activity_id,
            source,
            place_id,
            name,
            categories,
            category_id,
            latitude,
            longitude,
            address,
            city,
            region,
            country,
            telephone,
            url,
            type,
            budget,
            hours,
            description,
            embedding,
            location_id,
            location_cluster_id,
            created_at,
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


