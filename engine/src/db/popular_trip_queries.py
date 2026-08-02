"""
Database Query Layer for the Popular Trips pool.

Pure SQL against the attractions DB (personas, popular_trips,
popular_trip_attractions + attractions). No business logic - the companion
service decides thresholds and selection.

Flow: CompanionSuggestionService -> popular_trip_queries -> attractions DB
"""
import json
from typing import List, Dict, Any, Optional
import numpy as np


def _parse_embedding(emb) -> np.ndarray:
    """Convert a DB embedding value (list, string, or array) to float32 ndarray."""
    if isinstance(emb, np.ndarray):
        return emb.astype(np.float32)
    if isinstance(emb, list):
        return np.array(emb, dtype=np.float32)
    if isinstance(emb, str):
        return np.array(json.loads(emb), dtype=np.float32)
    return np.array(list(emb), dtype=np.float32)


def get_all_personas(conn) -> List[Dict[str, Any]]:
    """
    Return every persona with its embedding.

    Used by the companion-debug endpoint to show how close a trip's preference
    vector is to each persona, regardless of which popular trips exist.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT id, slug, name, description, embedding FROM personas ORDER BY id")
    rows = cursor.fetchall()
    cursor.close()
    return [
        {
            "persona_id": row[0],
            "slug": row[1],
            "name": row[2],
            "description": row[3],
            "embedding": _parse_embedding(row[4]),
        }
        for row in rows
    ]


def get_popular_trips_for_place(conn, place_id: str) -> List[Dict[str, Any]]:
    """
    Return every popular trip that contains `place_id`, with its persona.

    Uses the idx_pta_place index. This answers "which popular trips contain the
    attraction the user just liked?".

    Returns a list of dicts:
        { popular_trip_id, persona_id, persona_slug, persona_name, persona_embedding (ndarray) }
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT pt.id, pt.persona_id, per.slug, per.name, per.embedding
        FROM popular_trip_attractions pta
        JOIN popular_trips pt ON pt.id = pta.popular_trip_id
        JOIN personas per ON per.id = pt.persona_id
        WHERE pta.place_id = %s
        """,
        (place_id,),
    )
    rows = cursor.fetchall()
    cursor.close()
    return [
        {
            "popular_trip_id": row[0],
            "persona_id": row[1],
            "persona_slug": row[2],
            "persona_name": row[3],
            "persona_embedding": _parse_embedding(row[4]),
        }
        for row in rows
    ]


def get_trip_candidate_stops(
    conn,
    popular_trip_id: int,
    exclude_place_ids: List[str],
) -> List[Dict[str, Any]]:
    """
    Return the attractions of a popular trip (joined with attraction data),
    in route order, excluding the given place_ids.

    Returns a list of dicts with attraction fields + `position`.
    """
    exclude = list(exclude_place_ids) if exclude_place_ids else []
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            a.place_id, a.name, a.description, a.categories,
            a.latitude, a.longitude, a.address, a.budget, a.hours,
            a.image_url, a.popularity, pta.position
        FROM popular_trip_attractions pta
        JOIN attractions a ON a.place_id = pta.place_id
        WHERE pta.popular_trip_id = %s
          AND NOT (pta.place_id = ANY(%s))
        ORDER BY pta.position ASC
        """,
        (popular_trip_id, exclude),
    )
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    cursor.close()
    return [dict(zip(columns, row)) for row in rows]


def get_attraction_summary(conn, place_id: str) -> Optional[Dict[str, Any]]:
    """Fetch minimal attraction fields (name + coords) for a single place_id."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT place_id, name, latitude, longitude FROM attractions WHERE place_id = %s",
        (place_id,),
    )
    row = cursor.fetchone()
    cursor.close()
    if row is None:
        return None
    return {"place_id": row[0], "name": row[1], "latitude": row[2], "longitude": row[3]}
