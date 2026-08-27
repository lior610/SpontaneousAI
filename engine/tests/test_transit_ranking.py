"""Unit tests for transit reachability tagging, distance penalty, and preference gate."""
from src.services.ranking_utils import (
    annotate_reachability,
    apply_transit_preference_gate,
    score_distance,
)


def test_score_distance_walking_decays_to_zero_at_walk_limit():
    score, dist = score_distance(0.0, 0.0, 0.0, 0.0, max_walk_km=2.0, reachable_by="walking")
    assert dist == 0.0
    assert score == 1.0


def test_score_distance_transit_applies_penalty():
    # ~1.11 km east of origin (0.01 deg lng at equator)
    score, dist = score_distance(
        0.0, 0.01, 0.0, 0.0,
        max_walk_km=0.5,
        reachable_by="transit",
        transit_radius_km=5.0,
        transit_penalty=0.6,
    )
    assert dist is not None and dist > 0.5
    walk_score, _ = score_distance(
        0.0, 0.01, 0.0, 0.0,
        max_walk_km=5.0,
        reachable_by="walking",
    )
    assert score == 0.6 * walk_score


def test_annotate_and_preference_gate():
    walking = {"place_id": "w", "latitude": 0.0, "longitude": 0.0, "similarity": 0.50}
    strong_transit = {"place_id": "t1", "latitude": 0.0, "longitude": 0.03, "similarity": 0.70}
    weak_transit = {"place_id": "t2", "latitude": 0.0, "longitude": 0.03, "similarity": 0.51}
    candidates = [walking, strong_transit, weak_transit]
    annotate_reachability(candidates, 0.0, 0.0, max_walk_km=1.0)
    assert walking["reachable_by"] == "walking"
    assert strong_transit["reachable_by"] == "transit"
    gated = apply_transit_preference_gate(candidates, margin=0.05)
    ids = {c["place_id"] for c in gated}
    assert "w" in ids
    assert "t1" in ids
    assert "t2" not in ids
