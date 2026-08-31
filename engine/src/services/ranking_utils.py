"""
Shared raw scoring utilities used by all ranking algorithms.

These functions compute individual dimension scores (0-1) for a candidate
attraction given the current user/trip context. No weights are applied here —
each ranker decides how to combine them.
"""

from typing import Optional, Tuple, Dict, Any, List

from src.services.geo_utils import haversine
from src.services.transit_config import transit_distance_penalty, transit_max_radius_km, transit_preference_margin


def score_distance(
    attraction_lat: Optional[float],
    attraction_lng: Optional[float],
    user_lat: Optional[float],
    user_lng: Optional[float],
    max_walk_km: float,
    reachable_by: Optional[str] = None,
    transit_radius_km: Optional[float] = None,
    transit_penalty: Optional[float] = None,
) -> Tuple[float, Optional[float]]:
    if (
        attraction_lat is not None and attraction_lng is not None
        and user_lat is not None and user_lng is not None
    ):
        dist_km = haversine(user_lat, user_lng, attraction_lat, attraction_lng)
        if reachable_by == "transit":
            radius = transit_radius_km if transit_radius_km is not None else transit_max_radius_km()
            penalty = transit_penalty if transit_penalty is not None else transit_distance_penalty()
            dist_score = penalty * max(0.0, 1.0 - (dist_km / max(0.1, radius)))
            return dist_score, dist_km
        return max(0.0, 1.0 - (dist_km / max(0.1, max_walk_km))), dist_km
    return 0.0, None


def annotate_reachability(
    candidates: List[Dict[str, Any]],
    user_lat: Optional[float],
    user_lng: Optional[float],
    max_walk_km: float,
) -> None:
    """Tag each candidate walking vs transit using Haversine vs max_walk_km."""
    for candidate in candidates:
        lat = candidate.get("latitude")
        lng = candidate.get("longitude")
        if lat is not None and lng is not None and user_lat is not None and user_lng is not None:
            dist_km = haversine(user_lat, user_lng, float(lat), float(lng))
            candidate["distance_km"] = round(dist_km, 2)
            candidate["reachable_by"] = "walking" if dist_km <= max(0.0, max_walk_km) else "transit"
        else:
            candidate.setdefault("reachable_by", "walking")


def apply_transit_preference_gate(
    candidates: List[Dict[str, Any]],
    margin: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Keep a transit candidate in the mixed stream only if its semantic score
    beats the best walkable candidate by `margin`.
    """
    if not candidates:
        return candidates
    gate = transit_preference_margin() if margin is None else margin
    walking = [c for c in candidates if c.get("reachable_by") != "transit"]
    transit = [c for c in candidates if c.get("reachable_by") == "transit"]
    if not walking or not transit:
        return candidates
    best_walk_semantic = max(float(c.get("similarity") or 0.0) for c in walking)
    kept_transit = [
        c for c in transit
        if float(c.get("similarity") or 0.0) >= best_walk_semantic + gate
    ]
    # Preserve original relative order (walking and kept transit interleaved as fetched).
    kept_ids = {id(c) for c in walking} | {id(c) for c in kept_transit}
    return [c for c in candidates if id(c) in kept_ids]


def score_hours(hours_str: Optional[str], current_hour: Optional[int]) -> float:
    if not hours_str or current_hour is None:
        return 0.5
    try:
        parts = hours_str.split('-')
        if len(parts) == 2:
            open_hr = int(parts[0].split(':')[0])
            close_hr = int(parts[1].split(':')[0])
            if open_hr <= close_hr:
                return 1.0 if open_hr <= current_hour < close_hr else 0.0
            else:
                # Overnight e.g. 22:00-02:00
                return 1.0 if current_hour >= open_hr or current_hour < close_hr else 0.0
    except Exception:
        pass
    return 0.5


def score_budget(attr_budget_str: str, travel_style: str) -> float:
    budget_val = None
    if attr_budget_str:
        numeric_str = ''.join(c for c in attr_budget_str if c.isdigit() or c == '.')
        if numeric_str:
            try:
                budget_val = float(numeric_str)
            except ValueError:
                pass

    if budget_val is None:
        return 0.5

    if travel_style == 'budget':
        return 1.0 if budget_val <= 15.0 else 0.2
    elif travel_style == 'balanced':
        return 1.0 if 10.0 <= budget_val <= 50.0 else 0.5
    elif travel_style == 'premium':
        return 1.0 if budget_val >= 40.0 else 0.5
    return 0.5


def score_popularity(popularity_val: Any) -> float:
    try:
        return max(0.0, min(1.0, float(popularity_val)))
    except (ValueError, TypeError):
        return 0.2


def compute_raw_scores(
    candidate: Dict[str, Any],
    user_lat: Optional[float],
    user_lng: Optional[float],
    max_walk_km: float,
    travel_style: str,
    current_hour: Optional[int],
) -> Dict[str, Any]:
    """
    Compute all individual dimension scores for a candidate.
    Returns a dict with keys: semantic, distance, hours, budget, popularity, dist_km, is_closed.
    """
    semantic = candidate.get('similarity', 0.0)
    distance, dist_km = score_distance(
        candidate.get('latitude'), candidate.get('longitude'),
        user_lat, user_lng, max_walk_km,
        reachable_by=candidate.get('reachable_by'),
        transit_radius_km=transit_max_radius_km(),
        transit_penalty=transit_distance_penalty(),
    )
    hours = score_hours(candidate.get('hours'), current_hour)
    budget = score_budget(str(candidate.get('budget', '')).strip(), travel_style)
    popularity = score_popularity(candidate.get('popularity'))

    return {
        'semantic': semantic,
        'distance': distance,
        'hours': hours,
        'budget': budget,
        'popularity': popularity,
        'dist_km': dist_km,
        'is_closed': hours == 0.0,
    }
