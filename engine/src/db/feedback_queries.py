"""
Database Query Layer for Trip Feedback.

Reads and writes the trip_feedback table in the users DB.
Also fetches attraction embeddings for liked places (from attractions DB)
to support the real-time EMA update in PreferenceService.

Flow: PreferenceService / FeedbackService → feedback_queries → users DB / attractions DB
"""
import json
from typing import List, Set, Optional
import numpy as np


# ---------------------------------------------------------------------------
# Read side (used by Phase 1 — PreferenceService)
# ---------------------------------------------------------------------------

def get_liked_place_ids(conn, trip_id: int) -> List[str]:
    """
    Return place_ids that the user liked during this trip, oldest first.

    Used by PreferenceService to build the real-time EMA vector:
    the embeddings of liked attractions are averaged into the preference vector.

    Args:
        conn: psycopg2 connection to the users DB
        trip_id: ID of the current trip

    Returns:
        List of place_id strings in chronological order
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT place_id
        FROM trip_feedback
        WHERE trip_id = %s AND action = 'liked'
        ORDER BY created_at ASC
        """,
        (trip_id,),
    )
    rows = cursor.fetchall()
    cursor.close()
    return [row[0] for row in rows]


def get_excluded_place_ids(conn, trip_id: int) -> Set[str]:
    """
    Return place_ids that should be excluded from retrieval for this trip.

    Includes all three actions (liked, skipped, visited) — once the user
    has interacted with an attraction it should not be re-recommended.

    Args:
        conn: psycopg2 connection to the users DB
        trip_id: ID of the current trip

    Returns:
        Set of place_id strings
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT place_id
        FROM trip_feedback
        WHERE trip_id = %s
        """,
        (trip_id,),
    )
    rows = cursor.fetchall()
    cursor.close()
    return {row[0] for row in rows}


def get_attraction_embeddings(
    attractions_conn, place_ids: List[str]
) -> List[Optional[np.ndarray]]:
    """
    Fetch embeddings for a list of place_ids from the attractions DB.

    Used to convert liked place_ids into vectors for the EMA update.
    Returns embeddings in the same order as place_ids; None for any
    place_id whose embedding is missing.

    Args:
        attractions_conn: psycopg2 connection to the attractions DB
        place_ids: list of place_id strings

    Returns:
        List of (384,) float32 arrays (or None for missing)
    """
    if not place_ids:
        return []

    cursor = attractions_conn.cursor()
    cursor.execute(
        """
        SELECT place_id, embedding
        FROM attractions
        WHERE place_id = ANY(%s) AND embedding IS NOT NULL
        """,
        (place_ids,),
    )
    rows = cursor.fetchall()
    cursor.close()

    embedding_map = {row[0]: _parse_embedding(row[1]) for row in rows}
    return [embedding_map.get(pid) for pid in place_ids]


# ---------------------------------------------------------------------------
# Write side (used by Phase 2 — FeedbackService)
# ---------------------------------------------------------------------------

def record_feedback(
    conn,
    trip_id: int,
    place_id: str,
    action: str,
) -> None:
    """
    Insert or update a feedback row for (trip_id, place_id).

    Uses an upsert so that if the user changes their mind (e.g. first
    skips then later visits), the action is updated rather than duplicated.

    Args:
        conn: psycopg2 connection to the users DB
        trip_id: ID of the current trip
        place_id: ID of the attraction
        action: one of 'liked', 'skipped', 'visited'
    """
    if action not in ("liked", "skipped", "visited"):
        raise ValueError(f"Invalid action '{action}'. Must be liked, skipped, or visited.")

    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO trip_feedback (trip_id, place_id, action)
        VALUES (%s, %s, %s)
        ON CONFLICT (trip_id, place_id)
        DO UPDATE SET action = EXCLUDED.action, created_at = NOW()
        """,
        (trip_id, place_id, action),
    )
    cursor.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_embedding(emb) -> np.ndarray:
    """Convert a DB embedding value (list, string, or array) to float32 ndarray."""
    if isinstance(emb, np.ndarray):
        return emb.astype(np.float32)
    if isinstance(emb, list):
        return np.array(emb, dtype=np.float32)
    if isinstance(emb, str):
        return np.array(json.loads(emb), dtype=np.float32)
    return np.array(list(emb), dtype=np.float32)
