"""
Database Query Layer for User Preference Embeddings.

Reads and writes the user_preference_embeddings table in the users DB.

Flow: PreferenceService → preference_queries → users DB
"""
import json
from typing import List, Optional
import numpy as np


def get_past_embeddings(
    conn,
    user_id: int,
    exclude_trip_id: Optional[int] = None,
    limit: int = 5,
) -> List[np.ndarray]:
    """
    Return up to `limit` past preference embeddings for a user, most recent first.

    Excludes the current trip so the historical signal doesn't overlap
    with the trip-setup signal.

    Args:
        conn: psycopg2 connection to the users DB
        user_id: ID of the user
        exclude_trip_id: trip_id to exclude (current trip)
        limit: max number of past embeddings to return

    Returns:
        List of (384,) float32 numpy arrays, most recent first
    """
    cursor = conn.cursor()
    if exclude_trip_id is not None:
        cursor.execute(
            """
            SELECT embedding
            FROM user_preference_embeddings
            WHERE user_id = %s AND (trip_id IS NULL OR trip_id != %s)
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (user_id, exclude_trip_id, limit),
        )
    else:
        cursor.execute(
            """
            SELECT embedding
            FROM user_preference_embeddings
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (user_id, limit),
        )
    rows = cursor.fetchall()
    cursor.close()
    return [_parse_embedding(row[0]) for row in rows]


def upsert_preference_embedding(
    conn,
    user_id: int,
    trip_id: int,
    embedding: np.ndarray,
    preference_text: str,
) -> None:
    """
    Insert or update the preference embedding for the current trip.

    If a row already exists for this (user_id, trip_id), update the embedding
    and preference_text. This is called:
      - Once at the start of a trip (from trip-setup signal)
      - On each feedback event that triggers an EMA update

    Args:
        conn: psycopg2 connection to the users DB
        user_id: ID of the user
        trip_id: ID of the current trip
        embedding: (384,) float32 numpy array
        preference_text: human-readable debug string
    """
    embedding_str = _format_embedding(embedding)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO user_preference_embeddings (user_id, trip_id, preference_text, embedding, updated_at)
        VALUES (%s, %s, %s, %s::vector, NOW())
        ON CONFLICT (trip_id)
        DO UPDATE SET
            embedding = EXCLUDED.embedding,
            preference_text = EXCLUDED.preference_text,
            updated_at = NOW()
        """,
        (user_id, trip_id, preference_text, embedding_str),
    )
    cursor.close()


def get_current_embedding(
    conn,
    trip_id: int,
) -> Optional[np.ndarray]:
    """
    Return the stored preference embedding for the current trip, if any.

    Used to resume a session: if the user reconnects mid-trip, the
    already-updated EMA vector is loaded instead of recomputing from scratch.

    Args:
        conn: psycopg2 connection to the users DB
        trip_id: ID of the current trip

    Returns:
        (384,) float32 numpy array, or None if no row exists yet
    """
    cursor = conn.cursor()
    cursor.execute(
        "SELECT embedding FROM user_preference_embeddings WHERE trip_id = %s",
        (trip_id,),
    )
    row = cursor.fetchone()
    cursor.close()
    if row is None:
        return None
    return _parse_embedding(row[0])


def _parse_embedding(emb) -> np.ndarray:
    """Convert a DB embedding value (list, string, or array) to float32 ndarray."""
    if isinstance(emb, np.ndarray):
        return emb.astype(np.float32)
    if isinstance(emb, list):
        return np.array(emb, dtype=np.float32)
    if isinstance(emb, str):
        return np.array(json.loads(emb), dtype=np.float32)
    return np.array(list(emb), dtype=np.float32)


def _format_embedding(embedding: np.ndarray) -> str:
    """Convert ndarray to pgvector string format '[0.1,0.2,...]'."""
    return "[" + ",".join(map(str, embedding.tolist())) + "]"
