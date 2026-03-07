#!/usr/bin/env python3
"""
Merge clusters that share the same attraction name.

When the same chain/brand (e.g. "Starbucks") has multiple locations with
identical names but different descriptions, they can end up in different
clusters. This script groups attractions by name and assigns all locations
with the same name to the same cluster (the most common cluster among them).

Run after cluster_attractions.py.

Usage:
    python data-pipeline/scripts/merge_chain_clusters.py

Env vars: same as cluster_attractions.py (POSTGRES_*)
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
    config = get_db_config()
    logger.info(f"Connecting to {config['host']}:{config['port']}/{config['database']}")

    with psycopg2.connect(**config) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT place_id, name, cluster_id
                FROM attractions
            """)
            rows = cur.fetchall()

    # Group by name (same name = same chain)
    name_to_places = {}  # normalized_name -> [(place_id, cluster_id), ...]
    for place_id, name, cluster_id in rows:
        key = normalize_name(name or "")
        if not key:
            continue
        if key not in name_to_places:
            name_to_places[key] = []
        name_to_places[key].append((place_id, cluster_id))

    # For names with 2+ locations in different clusters, assign all to mode cluster
    updates = []
    for name_key, places in name_to_places.items():
        if len(places) < 2:
            continue
        cluster_ids = [c for _, c in places if c is not None]
        if not cluster_ids:
            continue  # all noise - skip
        mode_cluster = Counter(cluster_ids).most_common(1)[0][0]
        for place_id, cluster_id in places:
            if cluster_id != mode_cluster:
                updates.append((mode_cluster, place_id))

    if not updates:
        logger.info("No chain merges needed.")
        return

    with psycopg2.connect(**config) as conn:
        with conn.cursor() as cur:
            cur.executemany(
                "UPDATE attractions SET cluster_id = %s WHERE place_id = %s",
                updates,
            )
        conn.commit()

    logger.info(f"Merged {len(updates)} locations into same cluster (same-name fix)")


if __name__ == "__main__":
    main()
