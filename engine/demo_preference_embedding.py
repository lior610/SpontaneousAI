#!/usr/bin/env python3
"""
Demo: Preference Embedding — 3 user personas

Creates three demo users with distinct taste profiles, builds a preference
vector for each, and prints a ranked similarity table so you can visually
confirm the vectors point where they should.

Usage (from project root):
    python engine/demo_preference_embedding.py

Optional flags:
    --clean     Delete the synthetic seed data after the demo
"""
import argparse
import asyncio
import sys
import logging
from pathlib import Path
from typing import Dict, List, Tuple

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("demo")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "engine"))
sys.path.insert(0, str(PROJECT_ROOT / "shared" / "python"))

# ---------------------------------------------------------------------------
# Persona definitions
# ---------------------------------------------------------------------------

PERSONAS = [
    {
        "label":    "Museum Lover",
        "username": "demo_museum_lover",
        "email":    "museum@demo.ai",
        "user": {
            "age_group":          "30s",
            "travel_style":       "balanced",
            "pace_preference":    "slow",
            "dietary_style":      "none",
            "energy_level":       2.5,
            "hunger_level":       2.0,
        },
        "trip": {
            "destination":             "London",
            "start_date":              "2026-07-01",
            "end_date":                "2026-07-07",
            "budget":                  3000,
            "preference_breakdown":    '{"art": 90, "history": 80, "architecture": 70, "food": 20, "nature": 10}',
            "max_walking_distance":    4.0,
            "preferred_transportation":"walking",
            "max_travel_time_min":     40,
            "with_kids":               False,
        },
    },
    {
        "label":    "Foodie",
        "username": "demo_foodie",
        "email":    "foodie@demo.ai",
        "user": {
            "age_group":          "20s",
            "travel_style":       "balanced",
            "pace_preference":    "normal",
            "dietary_style":      "none",
            "energy_level":       3.5,
            "hunger_level":       4.5,
        },
        "trip": {
            "destination":             "London",
            "start_date":              "2026-07-01",
            "end_date":                "2026-07-05",
            "budget":                  1500,
            "preference_breakdown":    '{"food": 95, "shopping": 50, "entertainment": 30, "art": 10}',
            "max_walking_distance":    2.0,
            "preferred_transportation":"walking",
            "max_travel_time_min":     20,
            "with_kids":               False,
        },
    },
    {
        "label":    "Nightlife Seeker",
        "username": "demo_nightlife",
        "email":    "nightlife@demo.ai",
        "user": {
            "age_group":          "20s",
            "travel_style":       "balanced",
            "pace_preference":    "fast",
            "dietary_style":      "none",
            "energy_level":       5.0,
            "hunger_level":       2.0,
        },
        "trip": {
            "destination":             "London",
            "start_date":              "2026-07-01",
            "end_date":                "2026-07-04",
            "budget":                  2000,
            "preference_breakdown":    '{"nightlife": 95, "entertainment": 70, "food": 40, "shopping": 20}',
            "max_walking_distance":    1.5,
            "preferred_transportation":"public",
            "max_travel_time_min":     30,
            "with_kids":               False,
        },
    },
]

# Probes used to evaluate all vectors — ordered for display
PROBES: List[Tuple[str, str]] = [
    ("art museums galleries exhibitions culture",        "art / museums"),
    ("history monuments heritage landmarks sightseeing", "history"),
    ("architecture buildings design urban exploration",  "architecture"),
    ("food dining restaurants cafes eating",             "food / dining"),
    ("nightlife bars clubs evening drinks",              "nightlife"),
    ("entertainment shows theater cinema",               "entertainment"),
    ("shopping markets boutiques retail",                "shopping"),
    ("nature parks outdoors greenery hiking",            "nature"),
    ("wellness spa relaxation yoga meditation",          "wellness"),
]

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _upsert_persona(conn, persona: dict) -> Tuple[int, int]:
    """Upsert the persona's user + trip, return (user_id, trip_id)."""
    u = persona["user"]
    t = persona["trip"]
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users
                (username, email, password_hash, age_group, travel_style,
                 pace_preference, dietary_style, energy_level, hunger_level)
            VALUES (%s, %s, 'demo_hash', %s, %s, %s, %s, %s, %s)
            ON CONFLICT (username) DO UPDATE SET updated_at = NOW()
            RETURNING id
            """,
            (
                persona["username"], persona["email"],
                u["age_group"], u["travel_style"], u["pace_preference"],
                u["dietary_style"], u["energy_level"], u["hunger_level"],
            ),
        )
        user_id = cur.fetchone()[0]

        cur.execute(
            "SELECT trip_id FROM trips WHERE user_id = %s AND destination = %s LIMIT 1",
            (user_id, t["destination"]),
        )
        row = cur.fetchone()
        if row:
            trip_id = row[0]
        else:
            cur.execute(
                f"""
                INSERT INTO trips
                    (user_id, destination, start_date, end_date, budget,
                     preference_breakdown, max_walking_distance,
                     preferred_transportation, max_travel_time_min, with_kids)
                VALUES
                    (%s, %s, %s, %s, %s,
                     '{t["preference_breakdown"]}'::jsonb, %s, %s, %s, %s)
                RETURNING trip_id
                """,
                (
                    user_id, t["destination"], t["start_date"], t["end_date"], t["budget"],
                    t["max_walking_distance"], t["preferred_transportation"],
                    t["max_travel_time_min"], t["with_kids"],
                ),
            )
            trip_id = cur.fetchone()[0]

    conn.commit()
    return user_id, trip_id


def _delete_persona(conn, user_id: int):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Cosine similarity
# ---------------------------------------------------------------------------

def _cosine_sim(a, b):
    import numpy as np
    a = a / (float((a ** 2).sum() ** 0.5) + 1e-9)
    b = b / (float((b ** 2).sum() ** 0.5) + 1e-9)
    return float(a @ b)


# ---------------------------------------------------------------------------
# Demo runner
# ---------------------------------------------------------------------------

async def run_all_demos(personas_data: List[Tuple[dict, int, int]]):
    from src.services.preference_service import PreferenceComposer
    from src.services.embedding_service import generate_embedding
    import numpy as np

    composer = PreferenceComposer()

    # Pre-compute probe embeddings once (shared across all users)
    print("\nComputing probe embeddings...")
    probe_vecs = {}
    for phrase, label in PROBES:
        probe_vecs[label] = np.array(await generate_embedding(phrase), dtype="float32")

    # Header
    col_w = 20
    label_w = 18
    header = f"  {'Probe':<{label_w}}" + "".join(f"  {p['label']:>{col_w}}" for p in [d for d, _, _ in personas_data])
    separator = "  " + "-" * (label_w + (col_w + 2) * len(personas_data))

    results = []  # list of (label, {persona_label: sim})

    for _, label in PROBES:
        results.append((label, {}))

    for persona, user_id, trip_id in personas_data:
        print(f"\nBuilding vector for: {persona['label']}...")
        pref_vec = await composer.build(user_id=user_id, trip_id=trip_id, force_rebuild=True)
        norm = float(np.linalg.norm(pref_vec))

        for label, sim_dict in results:
            sim_dict[persona["label"]] = _cosine_sim(pref_vec, probe_vecs[label])

        print(f"  L2 norm = {norm:.4f}  (should be ~1.0)")
        breakdown = [p for p in PERSONAS if p["label"] == persona["label"]][0]["trip"]["preference_breakdown"]
        print(f"  preference_breakdown = {breakdown}")

    # Print comparison table
    print("\n\n" + "=" * (label_w + (col_w + 2) * len(personas_data) + 4))
    print("  COSINE SIMILARITY TO CATEGORY PROBES")
    print("  (higher = preference vector aligns more with that category)")
    print("=" * (label_w + (col_w + 2) * len(personas_data) + 4))
    print(header)
    print(separator)

    for probe_label, sim_dict in results:
        row = f"  {probe_label:<{label_w}}"
        for persona, _, _ in personas_data:
            sim = sim_dict[persona["label"]]
            bar = "█" * int(sim * 15)
            cell = f"{sim:.3f} {bar}"
            row += f"  {cell:>{col_w}}"
        print(row)

    print(separator)
    print("\n  Expected top probes per persona:")
    print("    Museum Lover    → art / museums, history, architecture should lead")
    print("    Foodie          → food / dining should dominate")
    print("    Nightlife Seeker→ nightlife, entertainment should dominate")
    print("=" * (label_w + (col_w + 2) * len(personas_data) + 4) + "\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Demo: Preference Embedding (3 personas)")
    parser.add_argument("--clean", action="store_true", help="Delete seed data after demo")
    args = parser.parse_args()

    from db.usersConnection import get_db_connection as get_users_conn

    seeded_ids = []
    personas_data = []

    with get_users_conn() as conn:
        for persona in PERSONAS:
            user_id, trip_id = _upsert_persona(conn, persona)
            seeded_ids.append(user_id)
            personas_data.append((persona, user_id, trip_id))
            logger.warning(f"Seeded {persona['label']}: user_id={user_id} trip_id={trip_id}")

    asyncio.run(run_all_demos(personas_data))

    if args.clean:
        with get_users_conn() as conn:
            for uid in seeded_ids:
                _delete_persona(conn, uid)
        print("Seed data cleaned up.")


if __name__ == "__main__":
    main()
