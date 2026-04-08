#!/usr/bin/env python3
"""
Enrich places_enriched.json with OpenTripMap data: popularity, image_url, wikipedia_extract.

Fetches rate (1-3), image, and wikipedia_extracts.text from OpenTripMap API.
Normalizes: rate 3→1.0, 2→0.7, 1→0.4, no match→0.2.

Rate limit: 5,000 requests/day. Use --max-requests and --skip-processed to run daily batches.

Usage:
    python data-pipeline/scripts/enrich_opentripmap_rates.py
    python data-pipeline/scripts/enrich_opentripmap_rates.py --max-requests 5000 --skip-processed

Env vars:
    PLACES_JSON           - Path to places_enriched.json (or inferred from --input)
    OPENTRIPMAP_API_KEY   - API key from https://dev.opentripmap.org
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import requests
except ImportError:
    raise ImportError("Install requests: pip install requests")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env", override=True)
except ImportError:
    pass

RATE_TO_POPULARITY = {3: 1.0, 2: 0.7, 1: 0.4}
POPULARITY_NO_MATCH = 0.2
API_BASE = "https://api.opentripmap.com/0.1/en/places"
REQUEST_DELAY = 0.2  # seconds between requests

# HTTP status codes that indicate API key / rate limit issues (do not treat as "no match")
API_ERROR_STATUSES = {401, 403, 429}


class OpenTripMapAPIError(Exception):
    """Raised when API returns an error (rate limit, invalid key, etc.) instead of data."""

    def __init__(self, status_code: int, message: str = ""):
        self.status_code = status_code
        self.message = message or self._default_message()
        super().__init__(self.message)

    def _default_message(self) -> str:
        if self.status_code == 401:
            return "API key invalid or missing (401 Unauthorized)"
        if self.status_code == 403:
            return "API key forbidden or quota exceeded (403 Forbidden)"
        if self.status_code == 429:
            return "API rate limit exceeded (429 Too Many Requests). Try again tomorrow or use --skip-processed."
        return f"OpenTripMap API error: HTTP {self.status_code}"


def parse_rate(rate_val: Any) -> Optional[int]:
    """Extract numeric part from rate: '3h' -> 3, '1' -> 1, etc."""
    if rate_val is None:
        return None
    s = str(rate_val).strip()
    match = re.match(r"^([123])", s)
    return int(match.group(1)) if match else None


def fetch_radius(api_key: str, lon: float, lat: float, radius: int = 250, limit: int = 10) -> list:
    """Fetch places from OpenTripMap radius API. Raises OpenTripMapAPIError on rate limit / auth errors."""
    url = f"{API_BASE}/radius"
    params = {"lon": lon, "lat": lat, "radius": radius, "limit": limit, "format": "json", "apikey": api_key}
    r = requests.get(url, params=params, timeout=10)
    if r.status_code in API_ERROR_STATUSES:
        raise OpenTripMapAPIError(r.status_code)
    if r.status_code != 200:
        return []
    try:
        return r.json() if isinstance(r.json(), list) else []
    except Exception:
        return []


def fetch_xid(api_key: str, xid: str) -> Optional[Dict]:
    """Fetch place details by xid. Raises OpenTripMapAPIError on rate limit / auth errors."""
    url = f"{API_BASE}/xid/{xid}"
    r = requests.get(url, params={"apikey": api_key}, timeout=10)
    if r.status_code in API_ERROR_STATUSES:
        raise OpenTripMapAPIError(r.status_code)
    if r.status_code != 200:
        return None
    try:
        return r.json()
    except Exception:
        return None


# Common stopwords to ignore when comparing place names
_NAME_STOPWORDS = frozenset({
    "a", "an", "and", "at", "by", "for", "in", "of", "on", "or", "the", "to", "with",
})

def _normalize_name(name: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation, remove stopwords for comparison."""
    if not name:
        return ""
    s = re.sub(r"[^\w\s]", " ", str(name).lower())
    words = [w for w in s.split() if w and w not in _NAME_STOPWORDS]
    return " ".join(words)


def names_match(our_name: str, otm_name: str) -> bool:
    """
    Return True if names refer to the same or similar place.
    Requires at least one significant word from our name to appear in OTM name.
    If either name has 3+ words and the other has 2+ words, requires at least 2 overlaps.
    Avoids false matches like 'Subway' matching 'Gaumont Finchley' (different places, same coords).
    """
    our = _normalize_name(our_name)
    otm = _normalize_name(otm_name)
    if not our or not otm:
        return False
    if our == otm:
        return True
    if our in otm or otm in our:
        return True
    # Token overlap: significant words (len >= 2) from our name must appear in OTM (whole-word only)
    our_words = [w for w in our.split() if len(w) >= 2]
    otm_words = set(otm.split())
    matches = sum(1 for w in our_words if w in otm_words)
    otm_word_count = len(otm.split())
    both_long = (otm_word_count >= 3 and len(our_words) >= 2) or (len(our_words) >= 3 and otm_word_count >= 2)
    min_required = 2 if both_long else 1
    return matches >= min_required


def pick_best_match(candidates: list, place_name: str) -> Optional[Dict]:
    """
    Pick best match from radius results.
    Only considers candidates whose name matches ours (same or similar).
    Among matches, prefers closest by distance.
    """
    if not candidates or not place_name:
        return None
    # Filter to candidates with matching/similar names
    matching = [c for c in candidates if names_match(place_name, c.get("name", ""))]
    if not matching:
        return None
    # Prefer result with 'dist' (closest)
    with_dist = [c for c in matching if c.get("dist") is not None]
    if with_dist:
        return min(with_dist, key=lambda c: c.get("dist", float("inf")))
    return matching[0]


def enrich_place(
    place: Dict[str, Any],
    api_key: str,
    radius: int = 250,
) -> tuple:
    """
    Enrich a single place with popularity, image_url, wikipedia_extract.
    Returns (num_requests, found, otm_name) where found=True if OpenTripMap had a match.
    otm_name is the OpenTripMap place name when found, else None.
    """
    lat = place.get("latitude")
    lon = place.get("longitude")
    if lat is None or lon is None:
        place["popularity"] = POPULARITY_NO_MATCH
        place["image_url"] = None
        place["wikipedia_extract"] = None
        return (0, False, None)

    candidates = fetch_radius(api_key, lon, lat, radius=radius)
    time.sleep(REQUEST_DELAY)
    best = pick_best_match(candidates, place.get("name", ""))

    if not best:
        place["popularity"] = POPULARITY_NO_MATCH
        place["image_url"] = None
        place["wikipedia_extract"] = None
        return (1, False, None)

    xid = best.get("xid")
    if not xid:
        place["popularity"] = POPULARITY_NO_MATCH
        place["image_url"] = None
        place["wikipedia_extract"] = None
        return (1, False, None)

    details = fetch_xid(api_key, xid)
    time.sleep(REQUEST_DELAY)
    if not details:
        place["popularity"] = POPULARITY_NO_MATCH
        place["image_url"] = None
        place["wikipedia_extract"] = None
        return (2, False, None)

    rate_num = parse_rate(details.get("rate"))
    place["popularity"] = RATE_TO_POPULARITY.get(rate_num, POPULARITY_NO_MATCH) if rate_num else POPULARITY_NO_MATCH
    place["image_url"] = details.get("image")
    we = details.get("wikipedia_extracts") or {}
    place["wikipedia_extract"] = we.get("text") if isinstance(we, dict) else None
    otm_name = details.get("name")
    return (2, True, otm_name)


def main():
    parser = argparse.ArgumentParser(description="Enrich places with OpenTripMap popularity, image, wikipedia")
    parser.add_argument("--input", "-i", help="Path to places_enriched.json")
    parser.add_argument("--output", "-o", help="Output path (default: overwrite input)")
    parser.add_argument("--max-requests", type=int, default=5000, help="Max API requests per run (default: 5000)")
    parser.add_argument("--skip-processed", action="store_true", help="Skip places that already have popularity")
    parser.add_argument("--list", action="store_true", help="Print list of places found in OpenTripMap")
    parser.add_argument("--radius", type=int, default=250, help="Search radius in meters (default: 250)")
    args = parser.parse_args()

    json_path = Path(args.input or os.getenv("PLACES_JSON", str(PROJECT_ROOT / "data-pipeline" / "scrapers" / "data" / "places_enriched.json")))
    if not json_path.exists():
        # Try location-specific path
        alt = PROJECT_ROOT / "data-pipeline" / "scrapers" / "data" / "london" / "places_enriched.json"
        if alt.exists():
            json_path = alt
        else:
            print(f"Error: File not found: {json_path}")
            return 1

    api_key = os.getenv("OPENTRIPMAP_API_KEY")
    if not api_key:
        print("Error: Set OPENTRIPMAP_API_KEY in .env")
        return 1

    with open(json_path, "r", encoding="utf-8") as f:
        places = json.load(f)

    output_path = Path(args.output) if args.output else json_path
    requests_made = 0
    enriched = 0
    found_list = []
    api_error = False

    try:
        for i, place in enumerate(places):
            if requests_made >= args.max_requests:
                print(f"Reached max requests ({args.max_requests}). Stopping. Run again tomorrow with --skip-processed.")
                break

            if args.skip_processed and place.get("popularity") is not None:
                continue

            n, found, otm_name = enrich_place(place, api_key, radius=args.radius)
            requests_made += n
            enriched += 1
            if found:
                has_wikipedia = bool(place.get("wikipedia_extract"))
                found_list.append((place.get("place_id", "?"), place.get("name", "?"), otm_name or "?", place.get("popularity"), has_wikipedia))
            if (i + 1) % 100 == 0:
                print(f"Examined {i + 1}/{len(places)} places, enriched {enriched}, requests: {requests_made}")
    except OpenTripMapAPIError as e:
        api_error = True
        print(f"\nError: {e}", file=sys.stderr)
        print("Progress saved. Run again tomorrow with --skip-processed to continue.", file=sys.stderr)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(places, f, indent=2, ensure_ascii=False)

    print(f"Done. Enriched {enriched} places, {requests_made} API requests. Saved to {output_path}")
    if enriched > 0:
        pct = 100.0 * len(found_list) / enriched
        print(f"Found in OpenTripMap: {len(found_list)}/{enriched} ({pct:.1f}%)")
    if args.list and found_list:
        print(f"\nPlaces found in OpenTripMap ({len(found_list)}):")
        for pid, name, otm_name, pop, has_wikipedia in found_list:
            wiki = "wikipedia=yes" if has_wikipedia else "wikipedia=no"
            print(f"  {pid} | JSON: {name} | OTM: {otm_name} | popularity={pop} | {wiki}")
    return 1 if api_error else 0


if __name__ == "__main__":
    exit(main())
