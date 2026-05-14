"""
Utility Queries — finds the nearest place matching a category (pharmacy, grocery, food, etc.)
sorted by approximate Euclidean distance (good enough for short-range within a city).
"""
from typing import List, Tuple, Optional, Any, Dict


def execute_closest_utility_query(
    conn,
    categories: List[str],
    lat: float,
    lng: float,
    location_id: int,
    current_hour: Optional[int] = None,
    limit: int = 5,
    type_filter: str = 'utility'
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Finds nearest places by category, ordered by distance.
    type_filter controls whether we search utility-type or attraction-type rows
    (food uses 'attraction' since restaurants aren't utilities in the DB).
    """
    import math
    cos_lat = math.cos(math.radians(lat))

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
            location_id,
            location_cluster_id,
            created_at,
            ((latitude - %s) * (latitude - %s) + ((longitude - %s) * %s) * ((longitude - %s) * %s)) as distance_sq
        FROM attractions
        WHERE type = %s
        AND location_id = %s
    """
    params: List[Any] = [lat, lat, lng, cos_lat, lng, cos_lat, type_filter, location_id]

    # Category Array Intersection
    if categories:
        query += " AND categories && %s::text[]"
        params.append(categories)

    # Hours filtering (allow unpredictably formatted hour strings to pass to python)
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
                        CAST(SPLIT_PART(SPLIT_PART(hours, '-', 1), ':', 1) AS INTEGER) > CAST(SPLIT_PART(SPLIT_PART(hours, '-', 2), ':', 1) AS INTEGER)
                        AND (%s >= CAST(SPLIT_PART(SPLIT_PART(hours, '-', 1), ':', 1) AS INTEGER) OR %s < CAST(SPLIT_PART(SPLIT_PART(hours, '-', 2), ':', 1) AS INTEGER))
                    )
                )
            )
            OR hours !~ '^\d{1,2}:\d{2}-\d{1,2}:\d{2}$'
          )
        """
        params.extend([current_hour, current_hour, current_hour, current_hour])
        
    query += " ORDER BY distance_sq ASC LIMIT %s"
    params.append(limit)
    
    cursor = conn.cursor()
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    column_names = [desc[0] for desc in cursor.description]
    cursor.close()
    
    return rows, column_names
