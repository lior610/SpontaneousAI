#!/usr/bin/env python3
"""
Load places from places_enriched.json into PostgreSQL attractions table.

Generates embeddings from categories, name, and description using sentence-transformers
(all-MiniLM-L6-v2), then upserts records into the attractions table.

Usage:
    python data-pipeline/scripts/load_places_to_db.py

Env vars:
    PLACES_JSON       - Path to places_enriched.json
    BATCH_SIZE        - Embedding batch size (default: 100)
    POSTGRES_HOST     - DB host (default: localhost)
    POSTGRES_PORT     - DB port (default: 5432)
    POSTGRES_ATTRACTIONS_DB - Database name (default: attractions)
    POSTGRES_USER     - DB user
    POSTGRES_PASSWORD - DB password
"""
import json
import os
import sys
import logging
from pathlib import Path

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
from typing import List, Dict, Any, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "shared" / "python"))

import psycopg2
from psycopg2.extras import execute_values

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_JSON = PROJECT_ROOT / "data-pipeline" / "scrapers" / "data" / "places_enriched.json"
EMBEDDING_DIM = 384  # all-MiniLM-L6-v2


def get_db_config() -> dict:
    return {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "database": os.getenv("POSTGRES_ATTRACTIONS_DB", "attractions"),
        "user": os.getenv("POSTGRES_USER", "postgres"),
        "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
    }


def load_places(json_path: Path) -> List[Dict[str, Any]]:
    """Load places from JSON file, excluding scraped_at."""
    logger.info(f"Loading places from {json_path}...")
    with open(json_path, "r", encoding="utf-8") as f:
        places = json.load(f)
    cleaned = [{k: v for k, v in p.items() if k != "scraped_at"} for p in places]
    logger.info(f"Loaded {len(cleaned)} places")
    return cleaned


def _normalize_chain_name(name: str) -> str:
    """Normalize name for chain grouping: lower, strip, collapse whitespace."""
    if not name:
        return ""
    return " ".join((name or "").lower().strip().split())


def _get_name_cat_key(place: Dict[str, Any]) -> tuple:
    """Return (name_lower, cat_str) for grouping. cat_str is sorted for consistency."""
    name = _normalize_chain_name(place.get("name") or "")
    categories = place.get("categories") or []
    cat_str = " ".join(sorted(str(c) for c in categories)) if isinstance(categories, list) else str(categories)
    return (name, cat_str)


def _get_chain_name_key(place: Dict[str, Any]) -> str:
    """Return normalized name only - for name-only chain detection."""
    return _normalize_chain_name(place.get("name") or "")


def _get_cat_str(place: Dict[str, Any]) -> str:
    """Get categories as string (order preserved for display)."""
    categories = place.get("categories") or []
    return " ".join(str(c) for c in categories) if isinstance(categories, list) else str(categories)


def _compute_chain_keys(places: List[Dict[str, Any]]) -> Tuple[set, dict, dict]:
    """
    Return (chain_keys, chain_desc_map).
    Uses NAME ONLY for chain detection - so "Dunkin'" with different category combos
    still clusters together. chain_key = normalized name.
    """
    from collections import Counter
    name_keys = [_get_chain_name_key(p) for p in places]
    counts = Counter(name_keys)
    chain_names = {n for n, c in counts.items() if c >= 2 and n}
    # Pick first non-empty description per chain as representative
    chain_desc_map = {}
    chain_cat_map = {}  # representative categories for embedding
    for p in places:
        name_key = _get_chain_name_key(p)
        if name_key in chain_names and name_key not in chain_desc_map:
            desc = p.get("embedding_desc") or p.get("description") or ""
            if desc:
                chain_desc_map[name_key] = desc
        if name_key in chain_names and name_key not in chain_cat_map:
            chain_cat_map[name_key] = _get_cat_str(p)
    chain_keys = chain_names
    chain_items = [(n, counts[n]) for n in chain_names]
    logger.info(f"Found {len(chain_keys)} chains (name with 2+ locations):")
    for name_key, count in sorted(chain_items, key=lambda x: -x[1]):
        logger.info(f"  {count:4d} places: {name_key}")
    return chain_keys, chain_desc_map, chain_cat_map


def build_embedding_text(
    place: Dict[str, Any], chain_keys: set, chain_desc_map: dict, chain_cat_map: dict
) -> str:
    """
    Build text for embedding.
    - If name is a chain (2+ locations): use name+categories+one_shared_description → identical embeddings.
    - Otherwise: use categories | name | description for rich semantic search.
    """
    name = place.get("name", "") or ""
    cat_str = _get_cat_str(place)
    desc = place.get("embedding_desc") or place.get("description") or ""

    name_key = _get_chain_name_key(place)
    if name_key in chain_keys:
        # Chain: name+categories+representative desc → identical embedding for all locations
        rep_cat = chain_cat_map.get(name_key, cat_str)
        parts = []
        if rep_cat:
            parts.append(rep_cat)
        if name:
            parts.append(name)
        shared_desc = chain_desc_map.get(name_key, "")
        if shared_desc:
            parts.append(shared_desc)
        return " | ".join(parts) if parts else name or "unknown"

    # Unique place: full text for semantic search
    parts = []
    if cat_str:
        parts.append(cat_str)
    if name:
        parts.append(name)
    if desc:
        parts.append(desc)
    return " | ".join(parts) if parts else name or "unknown"


def format_embedding_for_pgvector(embedding: List[float]) -> str:
    """Convert embedding to pgvector format string."""
    return "[" + ",".join(map(str, embedding)) + "]"


def upsert_places(conn, places: List[Dict[str, Any]], model) -> int:
    """Upsert places with embeddings. Returns count of rows."""
    chain_keys, chain_desc_map, chain_cat_map = _compute_chain_keys(places)
    batch_size = int(os.getenv("BATCH_SIZE", "100"))
    total = 0

    for i in range(0, len(places), batch_size):
        batch = places[i : i + batch_size]
        texts = [build_embedding_text(p, chain_keys, chain_desc_map, chain_cat_map) for p in batch]
        embeddings = model.encode(texts)

        rows = []
        for p, emb in zip(batch, embeddings):
            desc = p.get("embedding_desc") or p.get("description")
            rows.append((
                p.get("place_id"),
                p.get("source"),
                p.get("name", ""),
                p.get("categories"),
                p.get("category_id"),
                p.get("latitude"),
                p.get("longitude"),
                p.get("address"),
                p.get("city"),
                p.get("region"),
                p.get("country"),
                p.get("telephone"),
                p.get("url"),
                p.get("type"),
                p.get("budget"),
                p.get("hours"),
                desc,
                format_embedding_for_pgvector(emb.tolist()),
            ))

        with conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO attractions (
                    place_id, source, name, categories, category_id,
                    latitude, longitude, address, city, region, country,
                    telephone, url, type, budget, hours, description, embedding
                ) VALUES %s
                ON CONFLICT (place_id) DO UPDATE SET
                    source = EXCLUDED.source,
                    name = EXCLUDED.name,
                    categories = EXCLUDED.categories,
                    category_id = EXCLUDED.category_id,
                    latitude = EXCLUDED.latitude,
                    longitude = EXCLUDED.longitude,
                    address = EXCLUDED.address,
                    city = EXCLUDED.city,
                    region = EXCLUDED.region,
                    country = EXCLUDED.country,
                    telephone = EXCLUDED.telephone,
                    url = EXCLUDED.url,
                    type = EXCLUDED.type,
                    budget = EXCLUDED.budget,
                    hours = EXCLUDED.hours,
                    description = EXCLUDED.description,
                    embedding = EXCLUDED.embedding
                """,
                rows,
            )
        conn.commit()
        total += len(rows)
        logger.info(f"Upserted {total}/{len(places)} places")

    return total


def main():
    json_path = Path(os.getenv("PLACES_JSON", str(DEFAULT_JSON)))
    if not json_path.exists():
        logger.error(f"Places file not found: {json_path}")
        sys.exit(1)

    logger.info("Loading sentence-transformers model (all-MiniLM-L6-v2)...")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("all-MiniLM-L6-v2")

    places = load_places(json_path)
    if not places:
        logger.error("No places to load.")
        sys.exit(1)

    config = get_db_config()
    logger.info(f"Connecting to {config['host']}:{config['port']}/{config['database']}")

    with psycopg2.connect(**config) as conn:
        upsert_places(conn, places, model)

    logger.info("Done.")


if __name__ == "__main__":
    main()
