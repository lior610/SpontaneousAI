"""
End-to-end integration tests for the companion-suggestion mechanism.

Unlike test_companion.py (which monkeypatches every DB boundary), these tests
run against the REAL databases and the REAL popular-trips pool. They seed a
throwaway user + trip in the users DB, point that user's preference vector at a
persona embedding taken from the pool, record a "like" on a real stop of that
persona's popular trip, and assert the service's behaviour.

Requirements to actually run (otherwise the whole module is SKIPPED):
    - Both databases reachable via POSTGRES_* env (users DB + attractions DB).
    - The popular-trips pool is populated (personas / popular_trips /
      popular_trip_attractions), e.g. after running generate_popular_trips.py.

Run:
    python -m pytest engine/tests/test_companion_integration.py -v

Everything seeded is namespaced with an "itest_" prefix and deleted in teardown
(deleting the user cascades to trips, feedback, and preference rows).

Core scenario the reviewer asked for:
    "make a user super close to a persona, give a like, and check we get the prompt"
  -> test_super_close_user_gets_prompt
"""
import json
import uuid

import numpy as np
import pytest

# conftest.py puts engine root + shared/python on sys.path.
from db.usersConnection import get_db_config as users_db_config
from db.attractionsConnection import get_db_config as attractions_db_config

import src.services.companion_service as cs
from src.services.companion_service import CompanionSuggestionService

import psycopg2

BIG_RADIUS_KM = 99.99   # NUMERIC(4,2) max; larger than any intra-city distance.
TINY_RADIUS_KM = 0.01   # ~10 m; forces "unreachable" for distinct stops.


# ---------------------------------------------------------------------------
# Low-level DB helpers (direct connections we fully control + commit).
# ---------------------------------------------------------------------------

def _connect(config):
    return psycopg2.connect(**config)


def _vec_literal(vec) -> str:
    """pgvector text format: '[0.1,0.2,...]'."""
    return "[" + ",".join(str(float(x)) for x in vec) + "]"


def _parse_vec(raw) -> list:
    if isinstance(raw, str):
        return list(json.loads(raw))
    return [float(x) for x in raw]


def _try_connect_both():
    """Return (users_cfg, attr_cfg) or None if either DB is unreachable."""
    users_cfg = users_db_config()
    attr_cfg = attractions_db_config()
    try:
        c1 = _connect(users_cfg)
        c1.close()
        c2 = _connect(attr_cfg)
        c2.close()
    except Exception:
        return None
    return users_cfg, attr_cfg


def _pick_pool_scenario(attr_cfg):
    """
    Find a deterministic scenario from the real pool:

      - a place_id that belongs to EXACTLY ONE popular trip (no cross-trip
        ambiguity about which trip/persona is matched),
      - whose trip has >= 2 stops with coordinates.

    Returns a dict or None if the pool can't provide one.
    """
    conn = _connect(attr_cfg)
    try:
        cur = conn.cursor()
        # Candidate "liked" places that live in exactly one popular trip.
        cur.execute(
            """
            SELECT pta.place_id, MIN(pta.popular_trip_id) AS trip_id
            FROM popular_trip_attractions pta
            JOIN attractions a ON a.place_id = pta.place_id
            WHERE a.latitude IS NOT NULL AND a.longitude IS NOT NULL
            GROUP BY pta.place_id
            HAVING COUNT(DISTINCT pta.popular_trip_id) = 1
            """
        )
        candidates = cur.fetchall()
        for liked_place_id, trip_id in candidates:
            cur.execute(
                """
                SELECT pt.persona_id, per.slug, per.name, per.embedding, pt.location_id
                FROM popular_trips pt
                JOIN personas per ON per.id = pt.persona_id
                WHERE pt.id = %s
                """,
                (trip_id,),
            )
            row = cur.fetchone()
            if row is None:
                continue
            persona_id, persona_slug, persona_name, persona_emb, location_id = row

            cur.execute(
                """
                SELECT a.place_id, a.latitude, a.longitude, pta.position
                FROM popular_trip_attractions pta
                JOIN attractions a ON a.place_id = pta.place_id
                WHERE pta.popular_trip_id = %s
                  AND a.latitude IS NOT NULL AND a.longitude IS NOT NULL
                ORDER BY pta.position ASC
                """,
                (trip_id,),
            )
            stops = [
                {"place_id": p, "lat": float(la), "lng": float(lo), "position": pos}
                for (p, la, lo, pos) in cur.fetchall()
            ]
            others = [s for s in stops if s["place_id"] != liked_place_id]
            if len(others) < 1 or not any(s["place_id"] == liked_place_id for s in stops):
                continue

            liked = next(s for s in stops if s["place_id"] == liked_place_id)
            # First OTHER stop in route order == what the service should pick
            # first when everything is reachable and unseen.
            expected_first_other = others[0]["place_id"]
            return {
                "liked_place_id": liked_place_id,
                "liked_lat": liked["lat"],
                "liked_lng": liked["lng"],
                "popular_trip_id": trip_id,
                "persona_id": persona_id,
                "persona_slug": persona_slug,
                "persona_name": persona_name,
                "persona_embedding": _parse_vec(persona_emb),
                "location_id": location_id,
                "other_place_ids": [s["place_id"] for s in others],
                "expected_first_other": expected_first_other,
            }
        # Also grab a place that is NOT in any popular trip (for the negative case).
        return None
    finally:
        conn.close()


def _pick_place_not_in_pool(attr_cfg):
    conn = _connect(attr_cfg)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT a.place_id, a.latitude, a.longitude
            FROM attractions a
            WHERE a.latitude IS NOT NULL AND a.longitude IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM popular_trip_attractions pta WHERE pta.place_id = a.place_id
              )
            LIMIT 1
            """
        )
        row = cur.fetchone()
        return None if row is None else {"place_id": row[0], "lat": float(row[1]), "lng": float(row[2])}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def env():
    cfgs = _try_connect_both()
    if cfgs is None:
        pytest.skip("Users/attractions DB not reachable; skipping DB integration tests.")
    users_cfg, attr_cfg = cfgs
    scenario = _pick_pool_scenario(attr_cfg)
    if scenario is None:
        pytest.skip("Popular-trips pool not populated with a usable scenario; run generate_popular_trips.py.")
    not_in_pool = _pick_place_not_in_pool(attr_cfg)
    return {
        "users_cfg": users_cfg,
        "attr_cfg": attr_cfg,
        "scenario": scenario,
        "not_in_pool": not_in_pool,
    }


@pytest.fixture
def seeder(env):
    """
    Factory that seeds a throwaway user + trip + preference vector + feedback,
    returns (user_id, trip_id), and cleans up everything afterwards.
    """
    created_user_ids = []

    def _seed(
        *,
        pref_embedding,
        liked_place_id,
        current_lat,
        current_lng,
        max_walk_km=BIG_RADIUS_KM,
        seen_place_ids=(),
    ):
        conn = _connect(env["users_cfg"])
        try:
            cur = conn.cursor()
            tag = f"itest_{uuid.uuid4().hex[:12]}"
            cur.execute(
                """
                INSERT INTO users (username, email, password_hash)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (tag, f"{tag}@example.test", "x"),
            )
            user_id = cur.fetchone()[0]
            created_user_ids.append(user_id)

            cur.execute(
                """
                INSERT INTO trips (
                    user_id, destination, start_date, end_date,
                    max_walking_distance, current_lat, current_lng
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING trip_id
                """,
                (
                    user_id, "itest-city", "2026-01-01", "2026-01-02",
                    max_walk_km, current_lat, current_lng,
                ),
            )
            trip_id = cur.fetchone()[0]

            cur.execute(
                """
                INSERT INTO user_preference_embeddings
                    (user_id, trip_id, preference_text, embedding)
                VALUES (%s, %s, %s, %s::vector)
                """,
                (user_id, trip_id, "itest-preference", _vec_literal(pref_embedding)),
            )

            # The "like" that triggers the mechanism.
            cur.execute(
                "INSERT INTO trip_feedback (trip_id, place_id, action) VALUES (%s, %s, 'liked')",
                (trip_id, liked_place_id),
            )
            for pid in seen_place_ids:
                cur.execute(
                    "INSERT INTO trip_feedback (trip_id, place_id, action) VALUES (%s, %s, 'visited')",
                    (trip_id, pid),
                )
            conn.commit()
            return user_id, trip_id
        finally:
            conn.close()

    yield _seed

    if created_user_ids:
        conn = _connect(env["users_cfg"])
        try:
            cur = conn.cursor()
            # Deleting the user cascades to trips -> feedback + preference rows.
            cur.execute("DELETE FROM users WHERE id = ANY(%s)", (created_user_ids,))
            conn.commit()
        finally:
            conn.close()


@pytest.fixture(autouse=True)
def reset_constants(monkeypatch):
    """Keep runtime knobs at defaults unless a test overrides them."""
    monkeypatch.setattr(cs, "SIM_THRESHOLD", 0.45)
    monkeypatch.setattr(cs, "MAX_PER_TRIP", 3)
    monkeypatch.setattr(cs, "COOLDOWN_LIKES", 1)


# ---------------------------------------------------------------------------
# Tests: the happy path the reviewer asked for + weird/edge cases.
# ---------------------------------------------------------------------------

def test_super_close_user_gets_prompt(env, seeder):
    """A user whose preference vector == the persona embedding (cosine ~1.0)
    must receive a companion suggestion for a real, unseen, reachable stop."""
    sc = env["scenario"]
    user_id, trip_id = seeder(
        pref_embedding=sc["persona_embedding"],   # identical -> cosine ~1.0
        liked_place_id=sc["liked_place_id"],
        current_lat=sc["liked_lat"],
        current_lng=sc["liked_lng"],
        max_walk_km=BIG_RADIUS_KM,
    )

    result = CompanionSuggestionService().suggest(user_id, trip_id, sc["liked_place_id"])

    assert result is not None, "expected a prompt for a persona-aligned user"
    assert result["place_id"] == sc["expected_first_other"]
    assert result["place_id"] != sc["liked_place_id"]
    assert result["persona_slug"] == sc["persona_slug"]
    assert result["similarity"] >= cs.SIM_THRESHOLD
    assert result["similarity"] > 0.99, "identical vectors should be ~1.0"
    assert result["distance_km"] is not None
    assert result["reason"]


def test_orthogonal_user_below_threshold_gets_no_prompt(env, seeder, monkeypatch):
    """Same aligned data, but raise the threshold above 1.0 so even a perfect
    match fails: proves the persona-similarity gate blocks non-matching users."""
    monkeypatch.setattr(cs, "SIM_THRESHOLD", 1.01)
    sc = env["scenario"]
    user_id, trip_id = seeder(
        pref_embedding=sc["persona_embedding"],
        liked_place_id=sc["liked_place_id"],
        current_lat=sc["liked_lat"],
        current_lng=sc["liked_lng"],
    )
    assert CompanionSuggestionService().suggest(user_id, trip_id, sc["liked_place_id"]) is None


def test_opposite_vector_gets_no_prompt(env, seeder):
    """A preference vector pointing away from the persona (cosine ~ -1.0) is far
    below threshold -> no prompt (semantic 'user unlike persona')."""
    sc = env["scenario"]
    opposite = [-x for x in sc["persona_embedding"]]
    user_id, trip_id = seeder(
        pref_embedding=opposite,
        liked_place_id=sc["liked_place_id"],
        current_lat=sc["liked_lat"],
        current_lng=sc["liked_lng"],
    )
    assert CompanionSuggestionService().suggest(user_id, trip_id, sc["liked_place_id"]) is None


def test_all_other_stops_seen_gets_no_prompt(env, seeder):
    """Aligned user, but every other stop of the trip is already visited ->
    no unseen candidate -> no prompt."""
    sc = env["scenario"]
    user_id, trip_id = seeder(
        pref_embedding=sc["persona_embedding"],
        liked_place_id=sc["liked_place_id"],
        current_lat=sc["liked_lat"],
        current_lng=sc["liked_lng"],
        seen_place_ids=sc["other_place_ids"],
    )
    assert CompanionSuggestionService().suggest(user_id, trip_id, sc["liked_place_id"]) is None


def test_unreachable_stops_get_no_prompt(env, seeder):
    """Aligned user, but max walking distance is ~10 m -> mandatory reachability
    filters out every other stop -> no prompt."""
    sc = env["scenario"]
    user_id, trip_id = seeder(
        pref_embedding=sc["persona_embedding"],
        liked_place_id=sc["liked_place_id"],
        current_lat=sc["liked_lat"],
        current_lng=sc["liked_lng"],
        max_walk_km=TINY_RADIUS_KM,
    )
    result = CompanionSuggestionService().suggest(user_id, trip_id, sc["liked_place_id"])
    # If another stop happens to sit within 10 m of the liked one (degenerate
    # data), reachability is legitimately satisfied; don't assert in that case.
    if result is not None:
        assert result["distance_km"] is not None and result["distance_km"] <= TINY_RADIUS_KM
    else:
        assert result is None


def test_liked_place_not_in_pool_gets_no_prompt(env, seeder):
    """Liking an attraction that is in NO popular trip yields no prompt, even
    for a persona-aligned user."""
    if env["not_in_pool"] is None:
        pytest.skip("Every attraction is part of some popular trip; cannot test this case.")
    sc = env["scenario"]
    outsider = env["not_in_pool"]
    user_id, trip_id = seeder(
        pref_embedding=sc["persona_embedding"],
        liked_place_id=outsider["place_id"],
        current_lat=outsider["lat"],
        current_lng=outsider["lng"],
    )
    assert CompanionSuggestionService().suggest(user_id, trip_id, outsider["place_id"]) is None


def test_no_live_position_falls_back_to_liked_coordinates(env, seeder):
    """When the trip has no GPS, reachability is measured from the liked
    attraction's own coordinates -> aligned user still gets a prompt."""
    sc = env["scenario"]
    user_id, trip_id = seeder(
        pref_embedding=sc["persona_embedding"],
        liked_place_id=sc["liked_place_id"],
        current_lat=None,
        current_lng=None,
        max_walk_km=BIG_RADIUS_KM,
    )
    result = CompanionSuggestionService().suggest(user_id, trip_id, sc["liked_place_id"])
    assert result is not None
    assert result["place_id"] == sc["expected_first_other"]


def test_per_trip_cap_stops_prompting(env, seeder, monkeypatch):
    """Anti-nag: after MAX_PER_TRIP suggestions on one trip, further likes on the
    same trip produce no prompt (cooldown disabled to isolate the cap)."""
    monkeypatch.setattr(cs, "MAX_PER_TRIP", 1)
    monkeypatch.setattr(cs, "COOLDOWN_LIKES", 0)
    sc = env["scenario"]
    user_id, trip_id = seeder(
        pref_embedding=sc["persona_embedding"],
        liked_place_id=sc["liked_place_id"],
        current_lat=sc["liked_lat"],
        current_lng=sc["liked_lng"],
    )
    service = CompanionSuggestionService()
    assert service.suggest(user_id, trip_id, sc["liked_place_id"]) is not None
    assert service.suggest(user_id, trip_id, sc["liked_place_id"]) is None
