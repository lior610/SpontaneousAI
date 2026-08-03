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
from typing import Dict, Any, List, Optional, Tuple
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
    get_all_personas,
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
        Companion suggestion dict (CompanionSuggestion shape) or None.

        Called only for 'liked' actions, after the EMA update so the
        preference vector already reflects the just-liked attraction.
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
            logger.info(
                f"[Companion] trip {trip_id}: rate-limited "
                f"(shown {self._shown_count.get(trip_id, 0)}/{MAX_PER_TRIP}, "
                f"likes since last {self._likes_since_shown.get(trip_id)}, cooldown {COOLDOWN_LIKES})"
            )
            return None

        # 1. Load user preference vector, trip context, and seen places (users DB).
        with get_users_conn() as users_conn:
            pref_vec = get_current_embedding(users_conn, trip_id)
            trip = get_trip(users_conn, trip_id)
            excluded = get_excluded_place_ids(users_conn, trip_id)

        if pref_vec is None or trip is None:
            logger.info(
                f"[Companion] trip {trip_id}: missing "
                f"{'preference vector' if pref_vec is None else 'trip row'} — no suggestion"
            )
            return None

        # 2. Popular trips containing the liked attraction, ranked by persona match (attractions DB).
        with get_attr_conn() as attr_conn:
            candidate_trips = get_popular_trips_for_place(attr_conn, liked_place_id)
            if not candidate_trips:
                logger.info(
                    f"[Companion] trip {trip_id}: liked place {liked_place_id} "
                    f"is not in any popular trip — no suggestion"
                )
                return None

            matching = self._matching_trips(candidate_trips, pref_vec, trip_id)
            if not matching:
                return None

            # 3+4. Try every above-threshold trip in similarity order: the first
            # one with an unseen, reachable stop wins. Falling through to the
            # next matching trip costs nothing in relevance (all passed the
            # threshold) and fires suggestions the single-best approach missed.
            liked_summary = get_attraction_summary(attr_conn, liked_place_id)
            ref_lat, ref_lng = self._reference_position(trip, liked_summary)
            max_walk_km = self._max_walk_km(trip)
            exclude_ids = set(excluded)
            exclude_ids.add(liked_place_id)

            for pt, sim in matching:
                stops = get_trip_candidate_stops(attr_conn, pt["popular_trip_id"], list(exclude_ids))
                if not stops:
                    logger.info(
                        f"[Companion] trip {trip_id}: popular trip {pt['popular_trip_id']} "
                        f"({pt.get('persona_slug')}, sim {sim:.3f}) has no unseen stops left — trying next"
                    )
                    continue

                chosen = self._pick_reachable_stop(stops, ref_lat, ref_lng, max_walk_km)
                if chosen is None:
                    logger.info(
                        f"[Companion] trip {trip_id}: {len(stops)} unseen stop(s) on popular trip "
                        f"{pt['popular_trip_id']} but none within {max_walk_km} km — trying next"
                    )
                    continue

                liked_name = (liked_summary or {}).get("name") or "that spot"
                logger.info(
                    f"[Companion] trip {trip_id}: suggesting {chosen.get('name')} "
                    f"({chosen.get('place_id')}) from popular trip {pt['popular_trip_id']} "
                    f"({pt.get('persona_slug')}, sim {sim:.3f}, {chosen.get('_distance_km')} km)"
                )
                return self._build_suggestion(chosen, pt, sim, liked_name)

            logger.info(
                f"[Companion] trip {trip_id}: exhausted all {len(matching)} matching "
                f"popular trip(s) without a reachable unseen stop — no suggestion"
            )
            return None

    def _matching_trips(self, candidate_trips, pref_vec, trip_id=None) -> List[Tuple[Dict[str, Any], float]]:
        """All candidate trips at/above the similarity threshold, best first."""
        matching = []
        sims = []
        for ct in candidate_trips:
            sim = _cosine(pref_vec, ct["persona_embedding"])
            sims.append(f"{ct.get('persona_slug')}={sim:.3f}")
            if sim >= SIM_THRESHOLD:
                matching.append((ct, sim))
        if not matching:
            logger.info(
                f"[Companion] trip {trip_id}: no persona above threshold {SIM_THRESHOLD} "
                f"({', '.join(sims)})"
            )
        matching.sort(key=lambda pair: pair[1], reverse=True)
        return matching

    def debug_affinity(self, trip_id: int, liked_place_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Diagnostic snapshot for the companion flow (never on the hot path).

        Cosine similarity between the trip's preference vector and EVERY
        persona, plus anti-nag state. If `liked_place_id` is given, also
        simulates a like step by step without mutating rate-limit state.
        """
        with get_users_conn() as users_conn:
            pref_vec = get_current_embedding(users_conn, trip_id)
            trip = get_trip(users_conn, trip_id)
            excluded = get_excluded_place_ids(users_conn, trip_id)

        result: Dict[str, Any] = {
            "trip_id": trip_id,
            "sim_threshold": SIM_THRESHOLD,
            "has_preference_vector": pref_vec is not None,
            "rate_limit": {
                "shown_count": self._shown_count.get(trip_id, 0),
                "max_per_trip": MAX_PER_TRIP,
                "likes_since_last_shown": self._likes_since_shown.get(trip_id),
                "cooldown_likes": COOLDOWN_LIKES,
                "currently_rate_limited": self._is_rate_limited(trip_id),
            },
            "personas": [],
        }
        if pref_vec is None:
            return result

        with get_attr_conn() as attr_conn:
            personas = get_all_personas(attr_conn)
            scored = []
            for p in personas:
                sim = _cosine(pref_vec, p["embedding"])
                scored.append({
                    "slug": p["slug"],
                    "name": p["name"],
                    "similarity": round(sim, 4),
                    "passes_threshold": sim >= SIM_THRESHOLD,
                    "gap_to_threshold": round(SIM_THRESHOLD - sim, 4) if sim < SIM_THRESHOLD else 0.0,
                })
            result["personas"] = sorted(scored, key=lambda s: s["similarity"], reverse=True)

            if liked_place_id:
                result["simulation"] = self._debug_simulate_like(
                    attr_conn, trip, pref_vec, excluded, liked_place_id
                )
        return result

    def _debug_simulate_like(self, attr_conn, trip, pref_vec, excluded, liked_place_id) -> Dict[str, Any]:
        """Dry-run of _suggest for one place_id, reporting why each step passed/failed."""
        sim_report: Dict[str, Any] = {"liked_place_id": liked_place_id}

        candidate_trips = get_popular_trips_for_place(attr_conn, liked_place_id)
        sim_report["popular_trips_containing_place"] = [
            {
                "popular_trip_id": ct["popular_trip_id"],
                "persona_slug": ct.get("persona_slug"),
                "similarity": round(_cosine(pref_vec, ct["persona_embedding"]), 4),
                "passes_threshold": _cosine(pref_vec, ct["persona_embedding"]) >= SIM_THRESHOLD,
            }
            for ct in candidate_trips
        ]
        if not candidate_trips:
            sim_report["outcome"] = "place is not part of any popular trip"
            return sim_report

        matching = self._matching_trips(candidate_trips, pref_vec)
        if not matching:
            sim_report["outcome"] = f"no containing trip's persona reaches threshold {SIM_THRESHOLD}"
            return sim_report

        liked_summary = get_attraction_summary(attr_conn, liked_place_id)
        ref_lat, ref_lng = self._reference_position(trip, liked_summary)
        max_walk_km = self._max_walk_km(trip)
        sim_report["reference_position"] = {"lat": ref_lat, "lng": ref_lng}
        sim_report["max_walk_km"] = max_walk_km

        exclude_ids = set(excluded)
        exclude_ids.add(liked_place_id)

        # Mirror _suggest: walk the matching trips best-first and report each
        # attempt, so the debug output shows exactly where the fallback landed.
        attempts = []
        outcome = None
        for pt, sim in matching:
            attempt: Dict[str, Any] = {
                "popular_trip_id": pt["popular_trip_id"],
                "persona_slug": pt.get("persona_slug"),
                "similarity": round(sim, 4),
            }
            stops = get_trip_candidate_stops(attr_conn, pt["popular_trip_id"], list(exclude_ids))
            if not stops:
                attempt["result"] = "no unseen stops left"
                attempts.append(attempt)
                continue

            stop_report = []
            for stop in stops:
                lat, lng = stop.get("latitude"), stop.get("longitude")
                dist = (
                    round(haversine(ref_lat, ref_lng, float(lat), float(lng)), 2)
                    if None not in (ref_lat, ref_lng, lat, lng)
                    else None
                )
                stop_report.append({
                    "place_id": stop["place_id"],
                    "name": stop["name"],
                    "position": stop.get("position"),
                    "distance_km": dist,
                    "reachable": dist is not None and dist <= max_walk_km,
                })
            attempt["unseen_stops"] = stop_report

            chosen = self._pick_reachable_stop(stops, ref_lat, ref_lng, max_walk_km)
            if chosen is None:
                attempt["result"] = f"no unseen stop within {max_walk_km} km"
                attempts.append(attempt)
                continue

            attempt["result"] = f"would suggest {chosen['name']} ({chosen['place_id']})"
            attempts.append(attempt)
            outcome = attempt["result"]
            break

        sim_report["attempts"] = attempts
        sim_report["outcome"] = outcome or (
            f"exhausted all {len(matching)} matching trip(s) without a reachable unseen stop"
        )
        return sim_report

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
