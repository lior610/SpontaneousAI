"""
Database Query Layer for Cluster-Diverse Vector Search.

Provides optimized single-query retrieval of the top N attractions per geographic
cluster based on vector similarity.
"""
from typing import List, Tuple, Optional, Any, Dict
import json
import math


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
    Query vector space and group mathematically by location_cluster_id.
    
    Uses PostgreSQL Window Functions to find the most semantically similar
    attractions per geographic cluster in a single roundtrip.
    
    Args:
        conn: psycopg2 connection
        location_id: The ID of the current location/city
        embedding_str: User's preference vector as a pgvector string
        excluded_place_ids: List of place_ids the user has already interacted with
        top_per_cluster: Max number of attractions to return per cluster
        max_clusters: Max number of distinct clusters to return
        filters: Hard filters to apply at the SQL level (e.g. is_open)
        
    Returns:
        List of database row tuples, List of column names
    """
    
    # Base CTE uses pgvector <=> operator to calculate distance
    # and ROW_NUMBER to rank attractions within each cluster by distance
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
    
    # 1. Geographic Pre-Filtering (Bounding Box with 1.5x Soft Boundary)
    # 1 degree latitude = ~111.045 km
    if user_lat is not None and user_lng is not None and max_walk_km is not None:
        soft_limit_km = max_walk_km * 1.0
        
        lat_offset = soft_limit_km / 111.045
        min_lat = user_lat - lat_offset
        max_lat = user_lat + lat_offset
        
        # Longitude distance varies by latitude
        # 1 degree longitude = ~111.045 * cos(latitude)
        lng_offset = soft_limit_km / (111.045 * math.cos(math.radians(user_lat)))
        min_lng = user_lng - lng_offset
        max_lng = user_lng + lng_offset
        
        query += """
          AND latitude BETWEEN %s AND %s
          AND longitude BETWEEN %s AND %s
        """
        params.extend([min_lat, max_lat, min_lng, max_lng])
        
    # 2. Hours Pre-Filtering (Only retrieve items open right now)
    if current_hour is not None:
        query += """
          AND (
            hours IS NULL 
            OR hours = '' 
            OR hours = '00:00-23:59' 
            OR (
                -- Only attempt to mathematically parse if it perfectly matches HH:MM-HH:MM
                hours ~ '^\d{1,2}:\d{2}-\d{1,2}:\d{2}$'
                AND (
                    (
                        -- Standard daytime hours (e.g. 09:00-18:00)
                        CAST(SPLIT_PART(SPLIT_PART(hours, '-', 1), ':', 1) AS INTEGER) <= CAST(SPLIT_PART(SPLIT_PART(hours, '-', 2), ':', 1) AS INTEGER)
                        AND %s >= CAST(SPLIT_PART(SPLIT_PART(hours, '-', 1), ':', 1) AS INTEGER)
                        AND %s < CAST(SPLIT_PART(SPLIT_PART(hours, '-', 2), ':', 1) AS INTEGER)
                    )
                    OR (
                        -- Handling Overnight hours (e.g. 22:00-02:00)
                        CAST(SPLIT_PART(SPLIT_PART(hours, '-', 1), ':', 1) AS INTEGER) > CAST(SPLIT_PART(SPLIT_PART(hours, '-', 2), ':', 1) AS INTEGER)
                        AND (%s >= CAST(SPLIT_PART(SPLIT_PART(hours, '-', 1), ':', 1) AS INTEGER) OR %s < CAST(SPLIT_PART(SPLIT_PART(hours, '-', 2), ':', 1) AS INTEGER))
                    )
                )
            )
            OR hours !~ '^\d{1,2}:\d{2}-\d{1,2}:\d{2}$' -- If the string is unpredictable (e.g. "12 PM"), default to letting it pass and let Python handle it
          )
        """
        params.extend([current_hour, current_hour, current_hour, current_hour])
    
    if excluded_place_ids:
        # Prevent re-surfacing attractions the user has liked/skipped/visited this trip
        placeholders = ', '.join(['%s'] * len(excluded_place_ids))
        query += f" AND place_id NOT IN ({placeholders})"
        params.extend(excluded_place_ids)
        
    # Apply additional hard filters if present
    if filters:
        for column_name, filter_value in filters.items():
            if filter_value is None:
                continue
            if isinstance(filter_value, bool):
                query += f" AND {column_name} = {'TRUE' if filter_value else 'FALSE'}"
            else:
                query += f" AND {column_name} = %s"
                params.append(filter_value)
                
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
