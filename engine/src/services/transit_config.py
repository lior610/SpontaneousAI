"""
Env-backed config for public-transport-aware recommendations.
"""
import os
from typing import Any, Dict, Optional


def _as_bool(value: Optional[str], default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def transit_suggestions_enabled() -> bool:
    return _as_bool(os.getenv("TRANSIT_SUGGESTIONS_ENABLED"), True)


def transit_max_radius_km() -> float:
    try:
        return max(0.1, float(os.getenv("TRANSIT_MAX_RADIUS_KM", "5")))
    except (TypeError, ValueError):
        return 5.0


def transit_distance_penalty() -> float:
    try:
        return max(0.0, min(1.0, float(os.getenv("TRANSIT_DISTANCE_PENALTY", "0.6"))))
    except (TypeError, ValueError):
        return 0.6


def transit_preference_margin() -> float:
    try:
        return float(os.getenv("TRANSIT_PREFERENCE_MARGIN", "0.05"))
    except (TypeError, ValueError):
        return 0.05


def transit_max_directions_calls() -> int:
    try:
        return max(0, int(os.getenv("TRANSIT_MAX_DIRECTIONS_CALLS", "5")))
    except (TypeError, ValueError):
        return 5


def google_maps_api_key() -> str:
    """Same key the web map uses (VITE_GOOGLE_MAPS_API_KEY)."""
    return (os.getenv("VITE_GOOGLE_MAPS_API_KEY") or "").strip()


def trip_transit_active(trip_data: Optional[Dict[str, Any]]) -> bool:
    """
    Transit overlay is on when the global flag is enabled, the trip's preferred
    transportation is 'public' (not walking-only), and max_travel_time_min > 0.
    """
    if not transit_suggestions_enabled():
        return False
    if not trip_data:
        return False
    preferred = (trip_data.get("preferred_transportation") or "").strip().lower()
    if preferred != "public":
        return False
    max_travel = trip_data.get("max_travel_time_min")
    try:
        return max_travel is not None and int(max_travel) > 0
    except (TypeError, ValueError):
        return False


def trip_max_travel_time_min(trip_data: Optional[Dict[str, Any]], default: int = 30) -> int:
    if not trip_data:
        return default
    raw = trip_data.get("max_travel_time_min")
    try:
        if raw is None:
            return default
        return max(0, int(raw))
    except (TypeError, ValueError):
        return default
