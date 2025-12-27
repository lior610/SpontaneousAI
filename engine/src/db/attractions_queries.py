"""
Data access layer for attractions-related queries.
Manage attraction SQL queries.
"""
from typing import List, Tuple, Optional, Any, Dict


def fetch_similar_attractions(
    conn,
    embedding_str: str,
    limit: int = 10,
    min_similarity: Optional[float] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Tuple[Any, ...]], List[str]]:
    """
    Fetch attractions ordered by vector similarity.

    Args:
        conn: psycopg2 connection
        embedding_str: embedding formatted as pgvector string "[0.1,0.2,...]"
        limit: number of results
        min_similarity: optional similarity threshold (0-1)

    Returns:
        rows: list of tuples
        column_names: list of column names matching row order
    """
    # Base query
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

    # hard filters (non-semantic)
    if filters:
        if effort_levels := filters.get("effort_levels"):
            query += " AND effort_level = ANY(%s)"
            params.append(effort_levels)

        if indoor_outdoor := filters.get("indoor_outdoor"):
            query += " AND indoor_outdoor = %s"
            params.append(indoor_outdoor)

        if max_duration := filters.get("max_duration_min"):
            query += " AND typical_duration_min <= %s"
            params.append(max_duration)

        if include_categories := filters.get("include_categories"):
            query += " AND categories = ANY(%s)"
            params.append(include_categories)

        if exclude_categories := filters.get("exclude_categories"):
            query += " AND categories <> ALL(%s)"
            params.append(exclude_categories)

        if price_level_max := filters.get("price_level_max"):
            query += " AND price_level <= %s"
            params.append(price_level_max)

        if country := filters.get("country"):
            query += " AND country = %s"
            params.append(country)

        if city := filters.get("city"):
            query += " AND city = %s"
            params.append(city)

        if countries := filters.get("countries"):
            query += " AND country = ANY(%s)"
            params.append(countries)

        if cities := filters.get("cities"):
            query += " AND city = ANY(%s)"
            params.append(cities)

        if require_accessible := filters.get("accessibility_required"):
            query += " AND accessibility_features = TRUE"

        if require_booking_false := filters.get("requires_booking_false"):
            query += " AND requires_booking = FALSE"

        if open_now := filters.get("open_now"):
            query += " AND is_open_now = TRUE"

    if min_similarity is not None:
        max_distance = 2 * (1 - min_similarity)  # Convert similarity to distance
        query += " AND (embedding <=> %s::vector) <= %s"
        params.extend([embedding_str, max_distance])

    query += " ORDER BY embedding <=> %s::vector LIMIT %s"
    params.extend([embedding_str, limit])

    cursor = conn.cursor()
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    column_names = [desc[0] for desc in cursor.description]
    cursor.close()

    return rows, column_names


