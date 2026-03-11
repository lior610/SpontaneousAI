#!/usr/bin/env python3
"""
Update attractions table with ONLY popularity, image_url, wikipedia_extract.

Finds attractions by place_id and updates only these three fields. Does NOT touch
embedding, description, or any other columns - safe to run after vectors are already in DB.

Usage:
    python data-pipeline/scripts/update_opentripmap_fields.py -i data-pipeline/scrapers/data/ny/places_enriched.json

Env vars:
    POSTGRES_HOST, POSTGRES_PORT, POSTGRES_ATTRACTIONS_DB, POSTGRES_USER, POSTGRES_PASSWORD
"""
import json
import os
import sys
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_PATH = PROJECT_ROOT / ".env"


def _load_env() -> None:
    """Load .env from project root so POSTGRES_* vars are set."""
    if _ENV_PATH.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(_ENV_PATH, override=True)
        except ImportError:
            # Fallback: manually parse .env
            with open(_ENV_PATH) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        os.environ[k.strip()] = v.strip().strip('"').strip("'")


_load_env()

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


def ensure_columns(conn) -> None:
    """Add OpenTripMap columns if they don't exist."""
    with conn.cursor() as cur:
        cur.execute("""
            ALTER TABLE attractions ADD COLUMN IF NOT EXISTS popularity NUMERIC(4, 3);
            ALTER TABLE attractions ADD COLUMN IF NOT EXISTS image_url TEXT;
            ALTER TABLE attractions ADD COLUMN IF NOT EXISTS wikipedia_extract TEXT;
        """)
    conn.commit()
    logger.info("Ensured popularity, image_url, wikipedia_extract columns exist")


def update_from_json(conn, json_path: Path) -> int:
    """
    Update ONLY popularity, image_url, wikipedia_extract for matching place_ids.
    Does not alter embedding or any other fields.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        places = json.load(f)

    updated = 0
    with conn.cursor() as cur:
        for p in places:
            place_id = p.get("place_id")
            if not place_id:
                continue
            popularity = p.get("popularity")
            image_url = p.get("image_url")
            wikipedia_extract = p.get("wikipedia_extract")

            cur.execute(
                """
                UPDATE attractions
                SET popularity = %s, image_url = %s, wikipedia_extract = %s
                WHERE place_id = %s
                """,
                (popularity, image_url, wikipedia_extract, place_id),
            )
            if cur.rowcount > 0:
                updated += 1

    conn.commit()
    return updated


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="Update attractions with ONLY popularity, image_url, wikipedia_extract (by place_id). Does not touch embeddings."
    )
    parser.add_argument("-i", "--input", required=True, help="Path to places_enriched.json")
    args = parser.parse_args()

    json_path = Path(args.input)
    if not json_path.exists():
        logger.error(f"File not found: {json_path}")
        return 1

    config = get_db_config()
    logger.info(f"Connecting to {config['host']}:{config['port']}/{config['database']} (from .env)")
    logger.info(f"Updating from {json_path} (only popularity, image_url, wikipedia_extract)")

    try:
        with psycopg2.connect(**config) as conn:
            ensure_columns(conn)
            n = update_from_json(conn, json_path)
            logger.info(f"Updated {n} attractions")
    except psycopg2.Error as e:
        logger.error(f"Database error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
