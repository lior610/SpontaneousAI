"""
Companion Suggestion Service.

Implements the "because you liked X, you might also like Y" flow. When a user
likes an attraction, this service checks whether that attraction belongs to a
popular trip whose persona matches the user's current preference vector, and if
so returns another (unseen, reachable) stop from that same popular trip.

Match rule (persona similarity):
    liked attraction is in a popular trip
      AND cosine(user preference vector, trip.persona embedding) >= threshold

Reachability is MANDATORY: the suggested stop must be within the trip's
max_walking_distance of the user's live position (falling back to the liked
attraction's coordinates). If no stop qualifies, no suggestion is returned.
"""
import os
import sys
import logging
from typing import Dict, Any, Optional, Tuple
from pathlib import Path

import numpy as np

shared_path = str(Path(__file__).resolve().parents[3] / "shared" / "python")
if shared_path not in sys.path:
    sys.path.insert(0, shared_path)

from db.usersConnection import get_db_connection as get_users_conn
from db.attractionsConnection import get_db_connection as get_attr_conn
from models.recommendation import CompanionSuggestion

from src.services.geo_utils import haversine
from src.db.preference_queries import get_current_embedding
from src.db.feedback_queries import get_excluded_place_ids
from src.db.user_queries import get_trip
from src.db.popular_trip_queries import (
    get_popular_trips_for_place,
    get_trip_candidate_stops,
    get_attraction_summary,
)

logger = logging.getLogger(__name__)

SIM_THRESHOLD = float(os.getenv("COMPANION_SIM_THRESHOLD", "0.45"))
MAX_PER_TRIP = int(os.getenv("COMPANION_MAX_PER_TRIP", "3"))
COOLDOWN_LIKES = int(os.getenv("COMPANION_COOLDOWN_LIKES", "1"))
# Fallback walking radius (km) when the trip has no max_walking_distance set.
DEFAULT_MAX_WALK_KM = float(os.getenv("COMPANION_DEFAULT_MAX_WALK_KM", "2.0"))


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


class CompanionSuggestionService:
    """Produces companion suggestions from the popular-trips pool."""

    def __init__(self):
        # In-memory anti-nag state (per process). Resets on restart, which is
        # acceptable for a soft "don't over-suggest" guard.
        self._shown_count: Dict[int, int] = {}
        self._likes_since_shown: Dict[int, int] = {}

    def suggest(self, user_id: int, trip_id: int, liked_place_id: str) -> Optional[Dict[str, Any]]:
        """
        Return a companion suggestion dict (CompanionSuggestion shape) or None.

        Called only for 'liked' actions, after the EMA update so the preference
        vector already reflects the just-liked attraction.
        """
        try:
            suggestion = self._suggest(user_id, trip_id, liked_place_id)
        except Exception as e:
            # Never let a suggestion failure break the feedback flow.
            logger.warning(f"Companion suggestion failed (non-fatal): {e}")
            return None

        if suggestion is not None:
            self._shown_count[trip_id] = self._shown_count.get(trip_id, 0) + 1
            self._likes_since_shown[trip_id] = 0
        else:
            self._likes_since_shown[trip_id] = self._likes_since_shown.get(trip_id, 0) + 1
        return suggestion

    def _is_rate_limited(self, trip_id: int) -> bool:
        """Cap suggestions per trip and enforce a cooldown between them."""
        if self._shown_count.get(trip_id, 0) >= MAX_PER_TRIP:
            return True
        if (self._shown_count.get(trip_id, 0) > 0
                and self._likes_since_shown.get(trip_id, 10 ** 9) < COOLDOWN_LIKES):
            return True
        return False

    def _suggest(self, user_id: int, trip_id: int, liked_place_id: str) -> Optional[Dict[str, Any]]:
        if self._is_rate_limited(trip_id):
            return None

        # 1. Load user preference vector, trip context, and seen places (users DB).
        with get_users_conn() as users_conn:
            pref_vec = get_current_embedding(users_conn, trip_id)
            trip = get_trip(users_conn, trip_id)
            excluded = get_excluded_place_ids(users_conn, trip_id)

        if pref_vec is None or trip is None:
            return None

        # 2. Popular trips containing the liked attraction + best persona match (attractions DB).
        with get_attr_conn() as attr_conn:
            candidate_trips = get_popular_trips_for_place(attr_conn, liked_place_id)
            if not candidate_trips:
                return None

            best, best_sim = self._best_persona_match(candidate_trips, pref_vec)
            if best is None:
                return None

            # 3. Candidate stops from the matched trip, excluding seen + liked.
            exclude_ids = set(excluded)
            exclude_ids.add(liked_place_id)
            stops = get_trip_candidate_stops(attr_conn, best["popular_trip_id"], list(exclude_ids))
            if not stops:
                return None

            # 4. MANDATORY reachability, relative to live position or the liked place.
            liked_summary = get_attraction_summary(attr_conn, liked_place_id)
            ref_lat, ref_lng = self._reference_position(trip, liked_summary)
            max_walk_km = self._max_walk_km(trip)

            chosen = self._pick_reachable_stop(stops, ref_lat, ref_lng, max_walk_km)
            if chosen is None:
                return None

            liked_name = (liked_summary or {}).get("name") or "that spot"
            return self._build_suggestion(chosen, best, best_sim, liked_name)

    def _best_persona_match(self, candidate_trips, pref_vec) -> Tuple[Optional[Dict[str, Any]], float]:
        best = None
        best_sim = -1.0
        for ct in candidate_trips:
            sim = _cosine(pref_vec, ct["persona_embedding"])
            if sim >= SIM_THRESHOLD and sim > best_sim:
                best_sim = sim
                best = ct
        return best, best_sim

    def _reference_position(self, trip: Dict[str, Any], liked_summary: Optional[Dict[str, Any]]):
        """User's live position; fall back to the liked attraction's coordinates."""
        lat = trip.get("current_lat")
        lng = trip.get("current_lng")
        if lat is not None and lng is not None:
            return float(lat), float(lng)
        if liked_summary and liked_summary.get("latitude") is not None and liked_summary.get("longitude") is not None:
            return float(liked_summary["latitude"]), float(liked_summary["longitude"])
        return None, None

    def _max_walk_km(self, trip: Dict[str, Any]) -> float:
        raw = trip.get("max_walking_distance")
        try:
            return float(raw) if raw is not None else DEFAULT_MAX_WALK_KM
        except (TypeError, ValueError):
            return DEFAULT_MAX_WALK_KM

    def _pick_reachable_stop(self, stops, ref_lat, ref_lng, max_walk_km):
        """
        Pick the first reachable stop in route order.

        Reachability is mandatory when a reference position is available: stops
        beyond max_walk_km are rejected. If no reference position exists at all
        (rare), fall back to the first stop.
        """
        if ref_lat is None or ref_lng is None:
            stop = dict(stops[0])
            stop["_distance_km"] = None
            return stop

        for stop in stops:
            lat = stop.get("latitude")
            lng = stop.get("longitude")
            if lat is None or lng is None:
                continue
            dist = haversine(ref_lat, ref_lng, float(lat), float(lng))
            if dist <= max_walk_km:
                stop = dict(stop)
                stop["_distance_km"] = round(dist, 2)
                return stop
        return None

    def _build_suggestion(self, stop, best_trip, similarity, liked_name) -> Dict[str, Any]:
        persona_name = best_trip.get("persona_name") or "popular"
        reason = (
            f"Because you liked {liked_name}, you might also like this stop on a "
            f"popular {persona_name} route."
        )
        categories = stop.get("categories")
        if categories is not None and not isinstance(categories, list):
            categories = list(categories)

        suggestion = CompanionSuggestion(
            place_id=stop["place_id"],
            name=stop["name"],
            description=stop.get("description"),
            latitude=float(stop["latitude"]) if stop.get("latitude") is not None else None,
            longitude=float(stop["longitude"]) if stop.get("longitude") is not None else None,
            address=stop.get("address"),
            categories=categories,
            budget=stop.get("budget"),
            hours=stop.get("hours"),
            image_url=stop.get("image_url"),
            reason=reason,
            popular_trip_id=best_trip["popular_trip_id"],
            persona_slug=best_trip.get("persona_slug"),
            similarity=round(float(similarity), 4),
            distance_km=stop.get("_distance_km"),
        )
        return suggestion.model_dump()
