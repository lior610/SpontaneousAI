#!/usr/bin/env python3
"""Re-classify attractions.type using the corrected whole-word matching.

Part 2 of the "supermarket shows up as attraction" fix. Part 1 corrects the
substring bug in filter_places.py (is_attraction / is_utility). This script
re-runs that corrected classification over rows already in the DB and updates
the `type` column only. Embeddings and clusters are untouched.

Usage:
    DRY_RUN=1 python data-pipeline/scripts/reclassify_types.py   # preview only (default)
    DRY_RUN=0 python data-pipeline/scripts/reclassify_types.py   # apply changes

Env vars:
    DRY_RUN                 - "1" (default) previews; "0" applies the updates.
    POSTGRES_HOST/PORT/USER/PASSWORD
    POSTGRES_ATTRACTIONS_DB - Attractions database name (default: attractions)
"""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env", override=True)
except ImportError:
    pass
# Reuse the corrected classifier helpers from the pipeline (single source of truth).
sys.path.insert(0, str(PROJECT_ROOT / "data-pipeline" / "scrapers" / "src"))

import psycopg2
from psycopg2.extras import execute_values
from filter_places import is_attraction, is_utility


def classify_place(categories):
    """Mirror the per-place rule in filter_places(): attraction wins over utility."""
    if not categories:
        return None
    if any(is_attraction(c) for c in categories):
        return "attraction"
    if any(is_utility(c) for c in categories):
        return "utility"
    return None


def main():
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_ATTRACTIONS_DB", "attractions"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )

    changes = []  # (place_id, name, categories, current_type, new_type)
    with conn.cursor() as cur:
        cur.execute("SELECT place_id, name, categories, type FROM attractions")
        for place_id, name, categories, current_type in cur.fetchall():
            new_type = classify_place(categories)
            if new_type and new_type != current_type:
                changes.append((place_id, name, categories, current_type, new_type))

    dry_run = os.getenv("DRY_RUN", "1") != "0"

    to_util = sum(1 for c in changes if c[4] == "utility")
    to_attr = sum(1 for c in changes if c[4] == "attraction")

    if changes:
        header = "Rows to change (DRY RUN)" if dry_run else "Rows changed"
        print(f"\n{header}:")
        print(f"{'name':40.40} {'from':>10} -> {'to':<10} categories")
        print("-" * 100)
        for place_id, name, categories, current_type, new_type in changes:
            cats = ", ".join(categories) if categories else ""
            print(f"{(name or '(unnamed)'):40.40} {current_type or 'NULL':>10} -> {new_type:<10} [{place_id}] {cats}")
    else:
        print("\nNo rows need reclassification.")

    print(f"\nSummary: {len(changes)} rows would change "
          f"({to_util} -> utility, {to_attr} -> attraction)")

    if dry_run:
        print("DRY RUN: no changes written. Re-run with DRY_RUN=0 to apply.")
    elif changes:
        with conn.cursor() as cur:
            execute_values(
                cur,
                "UPDATE attractions AS a SET type = v.type "
                "FROM (VALUES %s) AS v(place_id, type) WHERE a.place_id = v.place_id",
                [(c[0], c[4]) for c in changes],
            )
        conn.commit()
        print(f"Applied: updated {len(changes)} rows.")

    conn.close()


if __name__ == "__main__":
    main()
