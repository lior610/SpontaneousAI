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
    Place_ids the user liked during this trip, oldest first.

    Feeds PreferenceComposer's real-time EMA vector (liked attraction
    embeddings averaged into the preference vector).
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
    Place_ids to exclude from retrieval for this trip.

    Covers all three actions (liked, skipped, visited) — once the user has
    interacted with an attraction it should not be re-recommended.
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
    Fetch embeddings for a list of place_ids, same order as input.

    None for any place_id whose embedding is missing (used to convert
    liked place_ids into vectors for the EMA update).
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
    Upsert a feedback row for (trip_id, place_id) — if the user changes their
    mind (e.g. first skips then later visits), the action is updated in place
    rather than duplicated.
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

def get_attraction_categories(
    attractions_conn, place_ids: List[str]
) -> Set[str]:
    """Unique categories/types across a list of place_ids, seeds 'real_seen_categories' for the diversity score."""
    if not place_ids:
        return set()

    cursor = attractions_conn.cursor()
    cursor.execute(
        """
        SELECT categories, type
        FROM attractions
        WHERE place_id = ANY(%s)
        """,
        (place_ids,)
    )
    rows = cursor.fetchall()
    cursor.close()

    seen_cats = set()
    for row in rows:
        cats = row[0] or []
        typ = row[1]
        for c in cats:
            if c:
                seen_cats.add(c)
        if typ:
            seen_cats.add(typ)
    return seen_cats


def _parse_embedding(emb) -> np.ndarray:
    """Convert a DB embedding value (list, string, or array) to float32 ndarray."""
    if isinstance(emb, np.ndarray):
        return emb.astype(np.float32)
    if isinstance(emb, list):
        return np.array(emb, dtype=np.float32)
    if isinstance(emb, str):
        return np.array(json.loads(emb), dtype=np.float32)
    return np.array(list(emb), dtype=np.float32)
