"""
Shared raw scoring utilities used by all ranking algorithms.

These functions compute individual dimension scores (0-1) for a candidate
attraction given the current user/trip context. No weights are applied here —
each ranker decides how to combine them.
"""

from typing import Optional, Tuple, Dict, Any

from src.services.geo_utils import haversine


def score_distance(
    attraction_lat: Optional[float],
    attraction_lng: Optional[float],
    user_lat: Optional[float],
    user_lng: Optional[float],
    max_walk_km: float,
) -> Tuple[float, Optional[float]]:
    if attraction_lat and attraction_lng and user_lat and user_lng:
        dist_km = haversine(user_lat, user_lng, attraction_lat, attraction_lng)
        return max(0.0, 1.0 - (dist_km / max(0.1, max_walk_km))), dist_km
    return 0.0, None


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
