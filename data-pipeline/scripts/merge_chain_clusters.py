#!/usr/bin/env python3
"""
Merge clusters that share the same attraction name (per location).

When the same chain/brand (e.g. "Starbucks") has multiple locations with
identical names but different descriptions, they can end up in different
clusters. This script groups attractions by (location_id, name) and assigns
all same-name places to the most common location_cluster_id within that location.

Run after cluster_attractions.py.

Usage:
    python data-pipeline/scripts/merge_chain_clusters.py
    LOCATION_SLUG=london python data-pipeline/scripts/merge_chain_clusters.py

Env vars: LOCATION_SLUG (optional), POSTGRES_*
"""
import os
import sys
import logging
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "shared" / "python"))

import psycopg2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_db_config() -> dict:
    return {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "database": os.getenv("POSTGRES_ATTRACTIONS_DB", "attractions"),
        "user": os.getenv("POSTGRES_USER", "postgres"),
        "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
    }


def normalize_name(name: str) -> str:
    """Normalize name for grouping (case-insensitive, stripped)."""
    if not name or not isinstance(name, str):
        return ""
    return name.strip().lower()


def main():
    import os

    config = get_db_config()
    location_slug = os.getenv("LOCATION_SLUG")
    logger.info(f"Connecting to {config['host']}:{config['port']}/{config['database']}")

    with psycopg2.connect(**config) as conn:
        with conn.cursor() as cur:
            if location_slug:
                cur.execute(
                    """
                    SELECT a.place_id, a.name, a.location_id, a.location_cluster_id
                    FROM attractions a
                    JOIN locations l ON a.location_id = l.id
                    WHERE l.slug = %s
                    """,
                    (location_slug,),
                )
            else:
                cur.execute("""
                    SELECT place_id, name, location_id, location_cluster_id
                    FROM attractions
                """)
            rows = cur.fetchall()

    # Group by (location_id, normalized_name) -> [(place_id, location_cluster_id), ...]
    key_to_places = {}  # (location_id, name_key) -> [(place_id, location_cluster_id), ...]
    for place_id, name, location_id, location_cluster_id in rows:
        key = normalize_name(name or "")
        if not key:
            continue
        k = (location_id, key)
        if k not in key_to_places:
            key_to_places[k] = []
        key_to_places[k].append((place_id, location_cluster_id))

    # For (location_id, name) with 2+ places in different clusters, assign all to mode
    updates = []
    for (location_id, name_key), places in key_to_places.items():
        if len(places) < 2:
            continue
        lc_ids = [lc for _, lc in places if lc is not None]
        if not lc_ids:
            continue
        mode_lc_id = Counter(lc_ids).most_common(1)[0][0]
        for place_id, lc_id in places:
            if lc_id != mode_lc_id:
                updates.append((mode_lc_id, place_id))

    if not updates:
        logger.info("No chain merges needed.")
        return

    with psycopg2.connect(**config) as conn:
        with conn.cursor() as cur:
            cur.executemany(
                "UPDATE attractions SET location_cluster_id = %s WHERE place_id = %s",
                updates,
            )
        conn.commit()

    logger.info(f"Merged {len(updates)} places into same cluster (same-name fix)")


if __name__ == "__main__":
    main()
