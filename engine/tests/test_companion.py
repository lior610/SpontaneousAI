"""
Unit tests for CompanionSuggestionService.

The service orchestrates across two databases and the popular-trips pool. Here we
monkeypatch the DB query functions and connection context managers so the tests
exercise pure selection logic: persona-similarity gating, exclusion of
seen/liked stops, and MANDATORY walking-distance reachability.
"""
from contextlib import contextmanager

import numpy as np
import pytest

from src.services import companion_service as cs
from src.services.companion_service import CompanionSuggestionService

LIKED_ID = "liked-place"
SEEN_ID = "seen-place"
NEAR_ID = "near-place"
FAR_ID = "far-place"

# Reference position (the trip's live location) and nearby / far stops.
REF_LAT, REF_LNG = 51.5100, -0.1200
NEAR_LAT, NEAR_LNG = 51.5105, -0.1205   # ~ 60 m away
FAR_LAT, FAR_LNG = 51.6000, -0.2000     # ~ 12 km away

PREF_VEC = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
PERSONA_ALIGNED = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)   # cosine 1.0
PERSONA_ORTHOGONAL = np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)  # cosine 0.0


@contextmanager
def _dummy_conn():
    yield None


def _stop(place_id, lat, lng, position):
    return {
        "place_id": place_id,
        "name": f"Name {place_id}",
        "description": "desc",
        "categories": ["culture"],
        "latitude": lat,
        "longitude": lng,
        "address": "1 Test St",
        "budget": "10",
        "hours": "09:00-18:00",
        "image_url": None,
        "position": position,
    }


def _install(
    monkeypatch,
    *,
    pref_vec=PREF_VEC,
    trip=None,
    excluded=None,
    popular_trips=None,
    stops=None,
    persona_embedding=PERSONA_ALIGNED,
):
    """Patch all external boundaries of the service with in-memory fakes."""
    trip = trip if trip is not None else {
        "current_lat": REF_LAT,
        "current_lng": REF_LNG,
        "max_walking_distance": 2.0,
    }
    excluded = excluded if excluded is not None else set()
    if popular_trips is None:
        popular_trips = [{
            "popular_trip_id": 1,
            "persona_id": 7,
            "persona_slug": "art-and-culture-lover",
            "persona_name": "Art & Culture Lover",
            "persona_embedding": persona_embedding,
        }]
    stops = stops if stops is not None else [
        _stop(NEAR_ID, NEAR_LAT, NEAR_LNG, 0),
        _stop(FAR_ID, FAR_LAT, FAR_LNG, 1),
    ]

    monkeypatch.setattr(cs, "get_users_conn", _dummy_conn)
    monkeypatch.setattr(cs, "get_attr_conn", _dummy_conn)
    monkeypatch.setattr(cs, "get_current_embedding", lambda conn, trip_id: pref_vec)
    monkeypatch.setattr(cs, "get_trip", lambda conn, trip_id: trip)
    monkeypatch.setattr(cs, "get_excluded_place_ids", lambda conn, trip_id: set(excluded))
    monkeypatch.setattr(cs, "get_popular_trips_for_place", lambda conn, place_id: popular_trips)

    def _candidate_stops(conn, popular_trip_id, exclude_place_ids):
        exclude = set(exclude_place_ids)
        return [s for s in stops if s["place_id"] not in exclude]

    monkeypatch.setattr(cs, "get_trip_candidate_stops", _candidate_stops)
    monkeypatch.setattr(
        cs, "get_attraction_summary",
        lambda conn, place_id: {"place_id": LIKED_ID, "name": "Louvre", "latitude": REF_LAT, "longitude": REF_LNG},
    )


def test_no_popular_trip_returns_none(monkeypatch):
    _install(monkeypatch, popular_trips=[])
    service = CompanionSuggestionService()
    assert service.suggest(1, 1, LIKED_ID) is None


def test_no_preference_vector_returns_none(monkeypatch):
    _install(monkeypatch, pref_vec=None)
    service = CompanionSuggestionService()
    assert service.suggest(1, 1, LIKED_ID) is None


def test_below_threshold_returns_none(monkeypatch):
    _install(monkeypatch, persona_embedding=PERSONA_ORTHOGONAL)
    service = CompanionSuggestionService()
    assert service.suggest(1, 1, LIKED_ID) is None


def test_match_returns_reachable_unseen_stop(monkeypatch):
    _install(monkeypatch)
    service = CompanionSuggestionService()
    result = service.suggest(1, 1, LIKED_ID)

    assert result is not None
    assert result["place_id"] == NEAR_ID
    assert result["popular_trip_id"] == 1
    assert result["persona_slug"] == "art-and-culture-lover"
    assert result["similarity"] >= cs.SIM_THRESHOLD
    assert "Louvre" in result["reason"]
    assert result["distance_km"] is not None


def test_excludes_seen_and_liked_stops(monkeypatch):
    # The near stop is marked seen; only the far stop remains -> unreachable -> None.
    _install(monkeypatch, excluded={SEEN_ID, NEAR_ID})
    service = CompanionSuggestionService()
    assert service.suggest(1, 1, LIKED_ID) is None


def test_unreachable_stops_return_none(monkeypatch):
    _install(monkeypatch, stops=[_stop(FAR_ID, FAR_LAT, FAR_LNG, 0)])
    service = CompanionSuggestionService()
    assert service.suggest(1, 1, LIKED_ID) is None


def test_reachability_uses_liked_place_when_no_live_position(monkeypatch):
    # No trip GPS -> fall back to the liked attraction's coordinates (== REF here).
    _install(monkeypatch, trip={"current_lat": None, "current_lng": None, "max_walking_distance": 2.0})
    service = CompanionSuggestionService()
    result = service.suggest(1, 1, LIKED_ID)
    assert result is not None
    assert result["place_id"] == NEAR_ID


def test_skips_far_stop_and_picks_next_reachable(monkeypatch):
    # Route order puts the FAR stop first; the service must skip it (mandatory
    # reachability) and pick the next reachable stop in order.
    _install(monkeypatch, stops=[
        _stop(FAR_ID, FAR_LAT, FAR_LNG, 0),
        _stop(NEAR_ID, NEAR_LAT, NEAR_LNG, 1),
    ])
    service = CompanionSuggestionService()
    result = service.suggest(1, 1, LIKED_ID)
    assert result is not None
    assert result["place_id"] == NEAR_ID


def test_picks_highest_similarity_persona_among_candidates(monkeypatch):
    # The liked place belongs to two popular trips; the service must match the
    # trip whose persona is most similar to the user's preference vector.
    _install(monkeypatch, popular_trips=[
        {
            "popular_trip_id": 10,
            "persona_id": 1,
            "persona_slug": "off-persona",
            "persona_name": "Off Persona",
            "persona_embedding": PERSONA_ORTHOGONAL,  # cosine 0.0 -> below threshold
        },
        {
            "popular_trip_id": 20,
            "persona_id": 2,
            "persona_slug": "matched-persona",
            "persona_name": "Matched Persona",
            "persona_embedding": PERSONA_ALIGNED,     # cosine 1.0 -> chosen
        },
    ])
    service = CompanionSuggestionService()
    result = service.suggest(1, 1, LIKED_ID)
    assert result is not None
    assert result["popular_trip_id"] == 20
    assert result["persona_slug"] == "matched-persona"


def test_falls_back_to_next_matching_trip(monkeypatch):
    # Two above-threshold trips contain the liked place. The higher-similarity
    # trip (id 30) has only an unreachable stop; the service must fall through
    # to the next matching trip (id 40) instead of giving up.
    aligned_ish = np.array([1.0, 0.3, 0.0, 0.0], dtype=np.float32)  # cosine ~0.958
    _install(monkeypatch, popular_trips=[
        {
            "popular_trip_id": 30,
            "persona_id": 1,
            "persona_slug": "best-persona",
            "persona_name": "Best Persona",
            "persona_embedding": PERSONA_ALIGNED,   # cosine 1.0 -> tried first
        },
        {
            "popular_trip_id": 40,
            "persona_id": 2,
            "persona_slug": "second-persona",
            "persona_name": "Second Persona",
            "persona_embedding": aligned_ish,       # above threshold -> tried second
        },
    ])

    stops_by_trip = {
        30: [_stop(FAR_ID, FAR_LAT, FAR_LNG, 0)],           # unreachable only
        40: [_stop(NEAR_ID, NEAR_LAT, NEAR_LNG, 0)],        # reachable
    }
    monkeypatch.setattr(
        cs, "get_trip_candidate_stops",
        lambda conn, popular_trip_id, exclude_place_ids: [
            s for s in stops_by_trip[popular_trip_id]
            if s["place_id"] not in set(exclude_place_ids)
        ],
    )

    service = CompanionSuggestionService()
    result = service.suggest(1, 1, LIKED_ID)
    assert result is not None
    assert result["popular_trip_id"] == 40
    assert result["place_id"] == NEAR_ID


def test_falls_back_when_best_trip_fully_seen(monkeypatch):
    # The best trip's stops are all already seen; the second matching trip
    # still has an unseen reachable stop and must be used.
    _install(monkeypatch, excluded={SEEN_ID}, popular_trips=[
        {
            "popular_trip_id": 50,
            "persona_id": 1,
            "persona_slug": "best-persona",
            "persona_name": "Best Persona",
            "persona_embedding": PERSONA_ALIGNED,
        },
        {
            "popular_trip_id": 60,
            "persona_id": 2,
            "persona_slug": "second-persona",
            "persona_name": "Second Persona",
            "persona_embedding": PERSONA_ALIGNED,
        },
    ])

    stops_by_trip = {
        50: [_stop(SEEN_ID, NEAR_LAT, NEAR_LNG, 0)],        # excluded -> empty
        60: [_stop(NEAR_ID, NEAR_LAT, NEAR_LNG, 0)],
    }
    monkeypatch.setattr(
        cs, "get_trip_candidate_stops",
        lambda conn, popular_trip_id, exclude_place_ids: [
            s for s in stops_by_trip[popular_trip_id]
            if s["place_id"] not in set(exclude_place_ids)
        ],
    )

    service = CompanionSuggestionService()
    result = service.suggest(1, 1, LIKED_ID)
    assert result is not None
    assert result["popular_trip_id"] == 60
    assert result["place_id"] == NEAR_ID


def test_per_trip_cap(monkeypatch):
    _install(monkeypatch)
    monkeypatch.setattr(cs, "COOLDOWN_LIKES", 0)  # disable cooldown to isolate the cap
    monkeypatch.setattr(cs, "MAX_PER_TRIP", 2)
    service = CompanionSuggestionService()

    assert service.suggest(1, 1, LIKED_ID) is not None
    assert service.suggest(1, 1, LIKED_ID) is not None
    # Third like on the same trip is capped.
    assert service.suggest(1, 1, LIKED_ID) is None
