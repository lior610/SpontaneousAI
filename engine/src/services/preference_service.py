"""
Preference Service — PreferenceComposer.

Builds a single 384d preference vector for a user+trip by blending three
signal sources:

    1. Historical (0.2) — average of past trip embeddings from user_preference_embeddings
    2. Trip setup  (0.5) — weighted average of category embeddings + qualifier text
    3. Real-time   (0.3) — EMA of liked attraction embeddings from trip_feedback

The final vector is L2-normalised and upserted into user_preference_embeddings
so it survives reconnections and becomes the historical signal for future trips.

Usage:
    from src.services.preference_service import PreferenceComposer

    composer = PreferenceComposer()
    pref_vec = await composer.build(user_id=1, trip_id=42)
    # → np.ndarray shape (384,)
"""
import os
import sys
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "shared" / "python"))

from db.usersConnection import get_db_connection as get_users_conn
from db.attractionsConnection import get_db_connection as get_attractions_conn
from src.services.embedding_service import generate_embedding, generate_embeddings_batch
from src.db.user_queries import get_user, get_trip
from src.db.preference_queries import (
    get_past_embeddings,
    get_current_embedding,
    upsert_preference_embedding,
)
from src.db.feedback_queries import get_liked_place_ids, get_attraction_embeddings

logger = logging.getLogger(__name__)


def _env_float(key: str, default: float) -> float:
    raw = os.getenv(key)
    if raw is None or not raw.strip():
        return default
    return float(raw)


# ---------------------------------------------------------------------------
# Source weights: tune HISTORICAL + TRIP_SETUP; REALTIME fills the remainder (sums to 1.0)
# ---------------------------------------------------------------------------
WEIGHT_HISTORICAL: float = 0.2
WEIGHT_TRIP_SETUP: float = 0.5
WEIGHT_REALTIME: float = 1.0 - (WEIGHT_HISTORICAL + WEIGHT_TRIP_SETUP)

# Within the trip-setup vector: category breakdown vs qualifier text (should sum to 1.0)
WEIGHT_CATEGORIES: float = _env_float("PREF_WEIGHT_TRIP_SETUP_CATEGORIES", 0.80)
WEIGHT_QUALIFIERS: float = _env_float("PREF_WEIGHT_TRIP_SETUP_QUALIFIERS", 0.20)

# EMA alpha for real-time updates: higher = new feedback has more influence
EMA_ALPHA: float = 0.3

# Descriptive phrases embedded for each preference_breakdown category key.
# Chosen to be semantically rich so all-MiniLM-L6-v2 places them near
# relevant attraction descriptions.
CATEGORY_PHRASES: Dict[str, str] = {
    "food":          "food dining restaurants cafes eating",
    "nature":        "nature parks outdoors greenery hiking",
    "art":           "art museums galleries exhibitions culture",
    "history":       "history monuments heritage landmarks sightseeing",
    "nightlife":     "nightlife bars clubs evening entertainment drinks",
    "shopping":      "shopping markets boutiques retail stores",
    "sports":        "sports activities fitness outdoor recreation",
    "entertainment": "entertainment shows theater cinema attractions",
    "wellness":      "wellness spa relaxation yoga meditation",
    "architecture":  "architecture buildings design urban exploration",
}


class PreferenceComposer:
    """
    Builds and persists the user preference embedding for a given trip.

    The composer is stateless — instantiate once at app startup and call
    `build()` per request.
    """

    async def build(
        self,
        user_id: int,
        trip_id: int,
        force_rebuild: bool = False,
    ) -> np.ndarray:
        """
        Return the preference vector for (user_id, trip_id).

        If a stored embedding already exists for the trip and force_rebuild is
        False, returns the stored one (fast path for mid-trip requests where
        the EMA is already up to date).

        Args:
            user_id: ID of the user
            trip_id: ID of the current trip
            force_rebuild: ignore stored embedding and recompute from scratch

        Returns:
            L2-normalised (384,) float32 preference vector
        """
        # Fast path: return the stored embedding if it exists
        if not force_rebuild:
            with get_users_conn() as conn:
                stored = get_current_embedding(conn, trip_id)
            if stored is not None:
                logger.debug(f"Returning stored preference embedding for trip_id={trip_id}")
                return stored

        # Load user and trip data
        with get_users_conn() as conn:
            user = get_user(conn, user_id)
            trip = get_trip(conn, trip_id)

        if user is None:
            raise ValueError(f"User {user_id} not found")
        if trip is None:
            raise ValueError(f"Trip {trip_id} not found")

        # --- Signal 1: Trip setup vector ---
        trip_vector = await self._build_trip_vector(user, trip)

        # --- Signal 2: Historical vector ---
        historical_vector = await self._build_historical_vector(user_id, trip_id)

        # --- Signal 3: Real-time EMA vector ---
        realtime_vector = await self._build_realtime_vector(trip_id, trip_vector)

        # --- Final blend ---
        preference_vector = self._blend(trip_vector, historical_vector, realtime_vector)

        # --- Persist ---
        preference_text = self._build_preference_text(user, trip)
        with get_users_conn() as conn:
            upsert_preference_embedding(conn, user_id, trip_id, preference_vector, preference_text)

        logger.info(f"Built preference vector for user_id={user_id} trip_id={trip_id}")
        return preference_vector

    async def apply_feedback(
        self,
        user_id: int,
        trip_id: int,
        liked_place_id: str,
    ) -> np.ndarray:
        """
        Apply one liked attraction to the stored preference vector via EMA.

        Called by FeedbackService after recording a 'liked' action.
        Updates and persists the preference vector in-place.

        Args:
            user_id: ID of the user
            trip_id: ID of the current trip
            liked_place_id: place_id of the attraction the user liked

        Returns:
            Updated L2-normalised (384,) preference vector
        """
        # Fetch the current stored vector (or build from scratch if missing)
        with get_users_conn() as conn:
            current = get_current_embedding(conn, trip_id)

        if current is None:
            current = await self.build(user_id, trip_id)

        # Fetch the attraction embedding
        with get_attractions_conn() as conn:
            embeddings = get_attraction_embeddings(conn, [liked_place_id])
        attraction_emb = embeddings[0] if embeddings else None

        if attraction_emb is None:
            logger.warning(f"No embedding found for place_id={liked_place_id}, skipping EMA")
            return current

        # EMA update
        updated = EMA_ALPHA * attraction_emb + (1 - EMA_ALPHA) * current
        updated = _l2_normalize(updated)

        # Persist updated vector
        with get_users_conn() as conn:
            user = get_user(conn, user_id)
            trip = get_trip(conn, trip_id)
        preference_text = self._build_preference_text(user, trip)

        with get_users_conn() as conn:
            upsert_preference_embedding(conn, user_id, trip_id, updated, preference_text)

        logger.info(f"EMA update applied for trip_id={trip_id} liked={liked_place_id}")
        return updated

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _build_trip_vector(
        self, user: Dict, trip: Dict
    ) -> np.ndarray:
        """
        Build the trip-setup vector from preference_breakdown + qualifier fields.

        preference_breakdown weights drive a per-category embedding average.
        Other user/trip fields contribute a smaller qualifier vector.
        """
        preference_breakdown: Optional[Dict[str, float]] = trip.get("preference_breakdown")

        if preference_breakdown:
            category_vector = await self._build_category_vector(preference_breakdown)
        else:
            # Fallback: embed a generic travel phrase
            category_vector = np.array(
                await generate_embedding("travel sightseeing exploring city"), dtype=np.float32
            )

        qualifier_text = self._build_qualifier_text(user, trip)
        qualifier_vector = np.array(
            await generate_embedding(qualifier_text), dtype=np.float32
        )

        trip_vector = WEIGHT_CATEGORIES * category_vector + WEIGHT_QUALIFIERS * qualifier_vector
        return _l2_normalize(trip_vector)

    async def _build_category_vector(
        self, preference_breakdown: Dict[str, float]
    ) -> np.ndarray:
        """
        Weighted average of per-category embeddings.

        Each category key is mapped to a descriptive phrase and embedded
        independently so the weights in preference_breakdown are reflected
        geometrically in the resulting vector.
        """
        known = {k: v for k, v in preference_breakdown.items() if k in CATEGORY_PHRASES}
        if not known:
            logger.warning("No known categories in preference_breakdown; using generic fallback")
            return np.array(
                await generate_embedding("travel sightseeing exploring"), dtype=np.float32
            )

        phrases = [CATEGORY_PHRASES[cat] for cat in known]
        raw_embeddings = await generate_embeddings_batch(phrases)
        embeddings = [np.array(e, dtype=np.float32) for e in raw_embeddings]

        total_weight = sum(known.values())
        category_vector = sum(
            (w / total_weight) * emb
            for (cat, w), emb in zip(known.items(), embeddings)
        )
        return _l2_normalize(np.array(category_vector, dtype=np.float32))

    async def _build_historical_vector(
        self, user_id: int, trip_id: int
    ) -> Optional[np.ndarray]:
        """
        Simple average of the user's past trip preference embeddings.

        Returns None if the user has no past trips (new user).
        """
        with get_users_conn() as conn:
            past = get_past_embeddings(conn, user_id, exclude_trip_id=trip_id)

        if not past:
            return None

        historical = np.mean(np.stack(past), axis=0).astype(np.float32)
        return _l2_normalize(historical)

    async def _build_realtime_vector(
        self, trip_id: int, fallback: np.ndarray
    ) -> np.ndarray:
        """
        EMA over liked attraction embeddings for the current trip.

        Starts from `fallback` (the trip-setup vector) so the real-time
        signal is grounded in the user's stated preferences.
        Returns `fallback` unchanged if no likes recorded yet.
        """
        with get_users_conn() as conn:
            liked_ids = get_liked_place_ids(conn, trip_id)

        if not liked_ids:
            return fallback

        with get_attractions_conn() as conn:
            attraction_embeddings = get_attraction_embeddings(conn, liked_ids)

        realtime = fallback.copy()
        for emb in attraction_embeddings:
            if emb is not None:
                realtime = EMA_ALPHA * emb + (1 - EMA_ALPHA) * realtime

        return _l2_normalize(realtime)

    def _blend(
        self,
        trip_vector: np.ndarray,
        historical_vector: Optional[np.ndarray],
        realtime_vector: np.ndarray,
    ) -> np.ndarray:
        """
        Combine the three source vectors with their respective weights.

        If historical is absent (new user), its weight is redistributed
        proportionally to the other two sources.
        """
        if historical_vector is not None:
            combined = (
                WEIGHT_TRIP_SETUP * trip_vector
                + WEIGHT_HISTORICAL * historical_vector
                + WEIGHT_REALTIME * realtime_vector
            )
        else:
            # Redistribute historical weight proportionally
            total = WEIGHT_TRIP_SETUP + WEIGHT_REALTIME
            combined = (
                (WEIGHT_TRIP_SETUP / total) * trip_vector
                + (WEIGHT_REALTIME / total) * realtime_vector
            )
        return _l2_normalize(combined)

    def _build_qualifier_text(self, user: Dict, trip: Dict) -> str:
        """
        Build a short text phrase from user + trip fields for embedding.

        Stored as preference_text for debugging/inspection.
        """
        parts = []

        travel_style = user.get("travel_style")
        if travel_style == "budget":
            parts.append("budget-friendly")
        elif travel_style == "premium":
            parts.append("premium luxury")
        elif travel_style == "balanced":
            parts.append("balanced")

        pace = user.get("pace_preference")
        if pace == "slow":
            parts.append("relaxed pace")
        elif pace == "fast":
            parts.append("fast pace")

        if trip.get("with_kids"):
            parts.append("with kids family-friendly")

        dietary = user.get("dietary_style")
        if dietary and dietary != "none":
            parts.append(dietary)

        transport = trip.get("preferred_transportation")
        if transport == "walking":
            parts.append("walkable")
        elif transport == "public":
            parts.append("public transport")

        return " ".join(parts) if parts else "travel exploration city"

    def _build_preference_text(self, user: Dict, trip: Dict) -> str:
        """Build the full debug string stored in user_preference_embeddings."""
        qualifier = self._build_qualifier_text(user, trip)
        breakdown = trip.get("preference_breakdown") or {}
        categories = " ".join(
            k for k, _ in sorted(breakdown.items(), key=lambda x: -x[1])
        )
        return f"{categories} | {qualifier}".strip(" |")


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _l2_normalize(v: np.ndarray) -> np.ndarray:
    """Return L2-normalised copy of v. If norm is zero, return v unchanged."""
    norm = np.linalg.norm(v)
    if norm == 0:
        return v
    return (v / norm).astype(np.float32)
