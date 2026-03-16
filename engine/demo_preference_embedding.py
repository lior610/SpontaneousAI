#!/usr/bin/env python3
"""
Demo: Preference Embedding

Inserts a synthetic user + trip into the users DB, runs PreferenceComposer,
and prints the resulting preference vector and its similarity to various
category phrases.

Usage (from project root):
    $env:POSTGRES_HOST="localhost"
    python engine/demo_preference_embedding.py

Optional flags:
    --user-id   ID of an existing user  (skips seed insert)
    --trip-id   ID of an existing trip  (skips seed insert)
    --clean     Delete the synthetic seed data after the demo
"""
import argparse
import asyncio
import os
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("demo")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "engine"))
sys.path.insert(0, str(PROJECT_ROOT / "shared" / "python"))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _insert_seed(conn):
    """Insert (or reuse) a demo user + trip and return (user_id, trip_id)."""
    with conn.cursor() as cur:
        # Upsert user
        cur.execute("""
            INSERT INTO users
                (username, email, password_hash, age_group, travel_style,
                 pace_preference, dietary_style, energy_level, hunger_level)
            VALUES
                ('demo_user', 'demo@spontaneous.ai', 'demo_hash', '20s', 'balanced',
                 'normal', 'none', 3.5, 2.0)
            ON CONFLICT (username) DO UPDATE SET updated_at = NOW()
            RETURNING id
        """)
        user_id = cur.fetchone()[0]

        # Reuse existing demo trip for this user if one exists
        cur.execute(
            "SELECT trip_id FROM trips WHERE user_id = %s AND destination = 'London' LIMIT 1",
            (user_id,),
        )
        row = cur.fetchone()
        if row:
            trip_id = row[0]
        else:
            cur.execute("""
                INSERT INTO trips
                    (user_id, destination, start_date, end_date, budget,
                     preference_breakdown, max_walking_distance, preferred_transportation,
                     max_travel_time_min, with_kids)
                VALUES
                    (%s, 'London', '2026-06-01', '2026-06-07', 2000,
                     '{"food": 80, "art": 60, "history": 50, "nature": 30}'::jsonb,
                     3.0, 'walking', 30, false)
                RETURNING trip_id
            """, (user_id,))
            trip_id = cur.fetchone()[0]

    conn.commit()
    logger.info(f"Seed data: user_id={user_id}  trip_id={trip_id}")
    return user_id, trip_id


def _delete_seed(conn, user_id):
    """Remove the demo user (trips cascade)."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
    conn.commit()
    logger.info(f"Cleaned up user_id={user_id} and related data")


def _cosine_sim(a, b):
    import numpy as np
    a = a / (np.linalg.norm(a) + 1e-9)
    b = b / (np.linalg.norm(b) + 1e-9)
    return float(a @ b)


# ---------------------------------------------------------------------------
# Main demo
# ---------------------------------------------------------------------------

async def run_demo(user_id: int, trip_id: int):
    from src.services.preference_service import PreferenceComposer
    from src.services.embedding_service import generate_embedding
    from db.usersConnection import get_db_connection as get_users_conn
    from src.db.user_queries import get_user, get_trip
    import numpy as np

    # Load user and trip for display
    with get_users_conn() as conn:
        user = get_user(conn, user_id)
        trip = get_trip(conn, trip_id)

    print("\n" + "=" * 60)
    print("USER")
    print(f"  travel_style:      {user['travel_style']}")
    print(f"  pace_preference:   {user['pace_preference']}")
    print(f"  dietary_style:     {user['dietary_style']}")

    print("\nTRIP")
    print(f"  destination:          {trip['destination']}")
    print(f"  preference_breakdown: {trip['preference_breakdown']}")
    print(f"  with_kids:            {trip['with_kids']}")
    print(f"  transportation:       {trip['preferred_transportation']}")

    # Build preference vector
    print("\nBuilding preference vector (force_rebuild=True)...")
    composer = PreferenceComposer()
    pref_vec = await composer.build(user_id=user_id, trip_id=trip_id, force_rebuild=True)

    print(f"\nPreference vector shape: {pref_vec.shape}")
    print(f"L2 norm: {float(np.linalg.norm(pref_vec)):.4f}  (should be ~1.0)")

    # Similarity to category phrases
    probe_phrases = {
        "food dining restaurants cafes":           "food",
        "art museums galleries culture":           "art",
        "history monuments heritage sightseeing":  "history",
        "nature parks outdoors greenery":          "nature",
        "nightlife bars clubs entertainment":      "nightlife",
        "shopping markets boutiques retail":       "shopping",
        "budget traveler cheap free":              "budget travel",
        "premium luxury upscale":                  "premium travel",
    }

    print("\n--- Cosine similarity to category probes ---")
    sims = {}
    for phrase, label in probe_phrases.items():
        emb = np.array(await generate_embedding(phrase), dtype="float32")
        sim = _cosine_sim(pref_vec, emb)
        sims[label] = sim

    for label, sim in sorted(sims.items(), key=lambda x: -x[1]):
        bar = "█" * int(sim * 40)
        print(f"  {label:<25} {sim:.3f}  {bar}")

    print("\n→ Higher similarity = preference vector aligns with that category.")
    print("  Food, art, history should rank highest given the trip setup.")
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Demo: Preference Embedding")
    parser.add_argument("--user-id", type=int, default=None)
    parser.add_argument("--trip-id", type=int, default=None)
    parser.add_argument("--clean", action="store_true", help="Delete seed data after demo")
    args = parser.parse_args()

    from db.usersConnection import get_db_connection as get_users_conn

    seeded_user_id = None
    user_id = args.user_id
    trip_id = args.trip_id

    if user_id is None or trip_id is None:
        with get_users_conn() as conn:
            user_id, trip_id = _insert_seed(conn)
        seeded_user_id = user_id

    asyncio.run(run_demo(user_id, trip_id))

    if args.clean and seeded_user_id is not None:
        with get_users_conn() as conn:
            _delete_seed(conn, seeded_user_id)


if __name__ == "__main__":
    main()
