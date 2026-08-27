"""
Google Routes TRANSIT validation for public-transport candidates.

Only the top TRANSIT_MAX_DIRECTIONS_CALLS transit-tagged candidates are looked
up per batch. Results are cached in-memory by rounded origin + place_id.
"""
import json
import logging
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from src.services.transit_config import google_maps_api_key, transit_max_directions_calls

logger = logging.getLogger(__name__)

ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
FIELD_MASK = "routes.duration,routes.legs.steps.transitDetails"

# origin_key:place_id -> (minutes, summary) or None if unreachable
_TRANSIT_CACHE: Dict[str, Optional[Tuple[Optional[int], Optional[str]]]] = {}


def _origin_key(lat: float, lng: float) -> str:
    return f"{round(lat, 3)}:{round(lng, 3)}"


def _cache_key(origin_lat: float, origin_lng: float, place_id: str) -> str:
    return f"{_origin_key(origin_lat, origin_lng)}:{place_id}"


def _parse_duration_seconds(duration: Optional[str]) -> Optional[int]:
    if not duration or not isinstance(duration, str):
        return None
    if duration.endswith("s"):
        try:
            return int(float(duration[:-1]))
        except ValueError:
            return None
    return None


def _summarize_transit(route: Dict[str, Any]) -> Optional[str]:
    lines = []
    for leg in route.get("legs") or []:
        for step in leg.get("steps") or []:
            details = step.get("transitDetails") or {}
            line = details.get("transitLine") or {}
            name = line.get("nameShort") or line.get("name")
            vehicle = ((line.get("vehicle") or {}).get("name")) if isinstance(line.get("vehicle"), dict) else None
            headsign = details.get("headsign")
            if name:
                parts = [name]
                if vehicle:
                    parts.append(vehicle)
                if headsign:
                    parts.append(f"to {headsign}")
                lines.append(" ".join(parts))
            elif vehicle:
                lines.append(vehicle)
    # Unique, keep order, cap length
    seen = []
    for item in lines:
        if item not in seen:
            seen.append(item)
    if not seen:
        return None
    return " → ".join(seen[:3])


def lookup_transit_route(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    place_id: str,
    api_key: Optional[str] = None,
) -> Optional[Tuple[Optional[int], Optional[str]]]:
    """
    Returns (minutes, summary) or None if no route / request failed.
    Cached by rounded origin + place_id.
    """
    key = _cache_key(origin_lat, origin_lng, place_id)
    if key in _TRANSIT_CACHE:
        return _TRANSIT_CACHE[key]

    token = api_key if api_key is not None else google_maps_api_key()
    if not token:
        logger.warning("VITE_GOOGLE_MAPS_API_KEY is empty; skipping TRANSIT validation")
        _TRANSIT_CACHE[key] = None
        return None

    body = {
        "origin": {"location": {"latLng": {"latitude": origin_lat, "longitude": origin_lng}}},
        "destination": {"location": {"latLng": {"latitude": dest_lat, "longitude": dest_lng}}},
        "travelMode": "TRANSIT",
        "computeAlternativeRoutes": False,
    }
    payload = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        ROUTES_URL,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": token,
            "X-Goog-FieldMask": FIELD_MASK,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as err:
        logger.warning("Routes TRANSIT HTTP %s for %s: %s", err.code, place_id, err.reason)
        _TRANSIT_CACHE[key] = None
        return None
    except Exception as err:
        logger.warning("Routes TRANSIT lookup failed for %s: %s", place_id, err)
        _TRANSIT_CACHE[key] = None
        return None

    routes = data.get("routes") or []
    if not routes:
        _TRANSIT_CACHE[key] = None
        return None

    route = routes[0]
    seconds = _parse_duration_seconds(route.get("duration"))
    minutes = int(round(seconds / 60.0)) if seconds is not None else None
    summary = _summarize_transit(route)
    result = (minutes, summary)
    _TRANSIT_CACHE[key] = result
    return result


def validate_transit_candidates(
    ranked_candidates: List[Dict[str, Any]],
    user_lat: Optional[float],
    user_lng: Optional[float],
    max_travel_time_min: int,
    max_calls: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Validate the top transit candidates via Google Routes. Walking candidates
    pass through. Unvalidated or over-time transit candidates are dropped.

    When VITE_GOOGLE_MAPS_API_KEY is missing, keep transit candidates with a
    haversine-based time estimate so local/dev still works.
    """
    api_key = google_maps_api_key()
    if not api_key:
        logger.warning("VITE_GOOGLE_MAPS_API_KEY is empty; using estimated transit times")
        kept = []
        for candidate in ranked_candidates:
            if candidate.get("reachable_by") != "transit":
                kept.append(candidate)
                continue
            dist_km = candidate.get("distance_km")
            if dist_km is None:
                continue
            # ~20 km/h average urban transit including waits
            minutes = max(1, int(round((float(dist_km) / 20.0) * 60.0)))
            if minutes > max_travel_time_min:
                continue
            candidate["transit_minutes"] = minutes
            candidate["transit_summary"] = candidate.get("transit_summary") or "Public transport (estimated)"
            kept.append(candidate)
        return kept

    if user_lat is None or user_lng is None:
        return [c for c in ranked_candidates if c.get("reachable_by") != "transit"]

    cap = transit_max_directions_calls() if max_calls is None else max_calls
    result: List[Dict[str, Any]] = []
    transit_lookups = 0

    for candidate in ranked_candidates:
        if candidate.get("reachable_by") != "transit":
            result.append(candidate)
            continue

        if transit_lookups >= cap:
            # Cost cap: do not serve remaining unvalidated transit candidates.
            continue

        dest_lat = candidate.get("latitude")
        dest_lng = candidate.get("longitude")
        place_id = candidate.get("place_id") or candidate.get("activity_id") or ""
        if dest_lat is None or dest_lng is None or not place_id:
            continue

        transit_lookups += 1
        lookup = lookup_transit_route(
            float(user_lat), float(user_lng),
            float(dest_lat), float(dest_lng),
            str(place_id),
        )
        if lookup is None:
            continue
        minutes, summary = lookup
        if minutes is None or minutes > max_travel_time_min:
            continue
        candidate["transit_minutes"] = minutes
        candidate["transit_summary"] = summary
        result.append(candidate)

    return result
