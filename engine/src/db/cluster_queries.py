"""
Cluster-Diverse Vector Search.

Single-query retrieval of the top N attractions per geographic cluster,
ranked by similarity to the user's preference vector.
"""
from typing import List, Tuple, Optional, Any, Dict
import math

from src.services.utility_service import UTILITY_CATEGORY_MAP


def execute_cluster_similarity_query(
    conn,
    location_id: int,
    embedding_str: str,
    excluded_place_ids: List[str],
    top_per_cluster: int = 3,
    max_clusters: int = 5,
    filters: Optional[Dict[str, Any]] = None,
    user_lat: Optional[float] = None,
    user_lng: Optional[float] = None,
    max_walk_km: Optional[float] = None,
    current_hour: Optional[int] = None
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Returns (rows, column_names) of the best-matching attractions grouped by cluster.

    How it works:
      1. Score all attractions by cosine distance to user's preference vector
      2. Rank within each geographic cluster (ROW_NUMBER partitioned by cluster)
      3. Pick the top N per cluster, from the top M clusters overall
      Result: diverse recommendations spread across different neighborhoods.
    """

    # pgvector's <=> is cosine distance (0 = identical, 2 = opposite)
    # ROW_NUMBER ranks attractions within each cluster by how close they are to preferences
    query = """
    WITH RankedAttractions AS (
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
            popularity,
            description,
            embedding,
            location_id,
            location_cluster_id,
            created_at,
            (1 - (embedding <=> %s::vector) / 2) as similarity,
            (embedding <=> %s::vector) as distance,
            ROW_NUMBER() OVER(
                PARTITION BY location_cluster_id
                ORDER BY embedding <=> %s::vector
            ) as cluster_rank
        FROM attractions
        WHERE location_id = %s
          AND embedding IS NOT NULL
          AND type != 'utility'
    """

    params: List[Any] = [embedding_str, embedding_str, embedding_str, location_id]

    # Bounding box: only consider attractions within walking distance.
    # Rectangular approximation — corners can be up to max_walk_km * sqrt(2).
    if user_lat is not None and user_lng is not None and max_walk_km is not None:
        soft_limit_km = max_walk_km * 1.0

        lat_offset = soft_limit_km / 111.045  # 1 degree lat ≈ 111 km
        min_lat = user_lat - lat_offset
        max_lat = user_lat + lat_offset

        # longitude degrees shrink toward the poles
        lng_offset = soft_limit_km / (111.045 * math.cos(math.radians(user_lat)))
        min_lng = user_lng - lng_offset
        max_lng = user_lng + lng_offset

        query += """
          AND latitude BETWEEN %s AND %s
          AND longitude BETWEEN %s AND %s
        """
        params.extend([min_lat, max_lat, min_lng, max_lng])

    # Only show places that are open now.
    if current_hour is not None:
        query += """
          AND (
            hours IS NULL
            OR hours = ''
            OR hours = '00:00-23:59'
            OR (
                hours ~ '^\d{1,2}:\d{2}-\d{1,2}:\d{2}$'
                AND (
                    (
                        CAST(SPLIT_PART(SPLIT_PART(hours, '-', 1), ':', 1) AS INTEGER) <= CAST(SPLIT_PART(SPLIT_PART(hours, '-', 2), ':', 1) AS INTEGER)
                        AND %s >= CAST(SPLIT_PART(SPLIT_PART(hours, '-', 1), ':', 1) AS INTEGER)
                        AND %s < CAST(SPLIT_PART(SPLIT_PART(hours, '-', 2), ':', 1) AS INTEGER)
                    )
                    OR (
                        -- overnight range like 22:00-02:00
                        CAST(SPLIT_PART(SPLIT_PART(hours, '-', 1), ':', 1) AS INTEGER) > CAST(SPLIT_PART(SPLIT_PART(hours, '-', 2), ':', 1) AS INTEGER)
                        AND (%s >= CAST(SPLIT_PART(SPLIT_PART(hours, '-', 1), ':', 1) AS INTEGER) OR %s < CAST(SPLIT_PART(SPLIT_PART(hours, '-', 2), ':', 1) AS INTEGER))
                    )
                )
            )
            OR hours !~ '^\d{1,2}:\d{2}-\d{1,2}:\d{2}$'
          )
        """
        params.extend([current_hour, current_hour, current_hour, current_hour])

    # Don't resurface places the user already liked/skipped/visited
    if excluded_place_ids:
        placeholders = ', '.join(['%s'] * len(excluded_place_ids))
        query += f" AND place_id NOT IN ({placeholders})"
        params.extend(excluded_place_ids)

    # Food places only appear via the food intercept layer, never in regular recs.
    # Matches an explicit list + anything with "restaurant" in the category name.
    food_categories = UTILITY_CATEGORY_MAP['food']
    if filters is not None and filters.get('category_filter') == 'food':
        query += """
          AND (
            categories && %s::text[]
            OR EXISTS (SELECT 1 FROM unnest(categories) AS cat WHERE LOWER(cat) LIKE '%%restaurant%%')
          )
        """
        params.append(food_categories)
    else:
        query += """
          AND NOT (
            categories && %s::text[]
            OR EXISTS (SELECT 1 FROM unnest(categories) AS cat WHERE LOWER(cat) LIKE '%%restaurant%%')
          )
        """
        params.append(food_categories)

    # Any extra column-level filters passed from the API (e.g. budget, type)
    ALLOWED_FILTER_COLUMNS = {'budget', 'type', 'is_open'}
    if filters:
        for column_name, filter_value in filters.items():
            if filter_value is None or column_name == 'category_filter':
                continue
            if column_name not in ALLOWED_FILTER_COLUMNS:
                continue
            if isinstance(filter_value, bool):
                query += f" AND {column_name} = {'TRUE' if filter_value else 'FALSE'}"
            else:
                query += f" AND {column_name} = %s"
                params.append(filter_value)

    # ClusterMins: finds the single best attraction per cluster ("cluster champion").
    # FinalRanking: ranks clusters by their champion's distance to user preferences.
    # Final SELECT: keeps top_per_cluster from each of the top max_clusters.
    # Example: 5 clusters × 5 per cluster = up to 25 results per batch.
    query += """
    ),
    ClusterMins AS (
        SELECT location_cluster_id, distance as min_dist
        FROM RankedAttractions
        WHERE cluster_rank = 1
    ),
    FinalRanking AS (
        SELECT r.*,
               DENSE_RANK() OVER(ORDER BY c.min_dist) as cluster_score_rank
        FROM RankedAttractions r
        JOIN ClusterMins c ON r.location_cluster_id = c.location_cluster_id
    )
    SELECT *
    FROM FinalRanking
    WHERE cluster_rank <= %s
      AND cluster_score_rank <= %s
    ORDER BY cluster_score_rank, cluster_rank;
    """
    params.extend([top_per_cluster, max_clusters])

    cursor = conn.cursor()
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    column_names = [desc[0] for desc in cursor.description]
    cursor.close()

    return rows, column_names
