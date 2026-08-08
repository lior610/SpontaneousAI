#!/usr/bin/env python3
"""
Generate the popular-trips pool (one-time, grounded, persona-tagged).

For every location + persona, asks Gemini for "popular routes" built ONLY from real
attractions in that city; place_ids are validated against the DB catalog (hallucinations
dropped) and written to personas, popular_trips, popular_trip_attractions. Trip embedding
is the L2-normalized mean of member attraction embeddings (tie-break vector only); persona
embedding is the persona description's embedding, matched against user preference vectors.

Regenerates a location's popular_trips from scratch each run (existing rows deleted first) —
UNLESS POPULAR_TRIPS_FILL_MISSING is set, in which case nothing is deleted and only personas
short of POPULAR_TRIPS_PER_PERSONA trips get topped up (for when a prior Gemini call failed
or returned invalid routes and left a persona short).

Usage:
    python data-pipeline/scripts/generate_popular_trips.py
    LOCATION_SLUG=london python data-pipeline/scripts/generate_popular_trips.py
    POPULAR_TRIPS_FILL_MISSING=1 python data-pipeline/scripts/generate_popular_trips.py

Env vars:
    GEMINI_API_KEY              - required; Google Gemini API key
    GEMINI_MODEL               - default: gemini-2.5-flash
    POPULAR_TRIPS_PER_PERSONA  - default: 10
    POPULAR_TRIP_MIN_STOPS     - default: 4
    POPULAR_TRIP_MAX_STOPS     - default: 6
    POPULAR_TRIPS_CATALOG_LIMIT- default: 150 (max attractions offered to the LLM per city)
    POPULAR_TRIPS_FILL_MISSING - optional; 1/true = top-up mode (no delete, only
                                 personas below the per-persona target)
    LOCATION_SLUG              - optional; restrict generation to one location
    POSTGRES_*                 - DB connection (see load_places_to_db.py)

Loads project-root .env first, then scrapers/.env for any missing keys (GEMINI_*).
"""
import json
import os
import sys
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
try:
    from dotenv import load_dotenv
    # Root .env for DB/shared config; scrapers .env fills Gemini key/model if missing.
    load_dotenv(PROJECT_ROOT / ".env", override=True)
    load_dotenv(PROJECT_ROOT / "data-pipeline" / "scrapers" / ".env", override=False)
except ImportError:
    pass
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import psycopg2
import requests

from personas import PERSONAS
from db_utils import get_db_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

EMBEDDING_DIM = 384  # all-MiniLM-L6-v2
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TRIPS_PER_PERSONA = int(os.getenv("POPULAR_TRIPS_PER_PERSONA", "10"))
MIN_STOPS = int(os.getenv("POPULAR_TRIP_MIN_STOPS", "4"))
MAX_STOPS = int(os.getenv("POPULAR_TRIP_MAX_STOPS", "6"))
CATALOG_LIMIT = int(os.getenv("POPULAR_TRIPS_CATALOG_LIMIT", "150"))
FILL_MISSING = os.getenv("POPULAR_TRIPS_FILL_MISSING", "").strip().lower() in ("1", "true", "yes")


def _format_embedding(embedding: List[float]) -> str:
    """Convert a vector to pgvector string format '[0.1,0.2,...]'."""
    return "[" + ",".join(map(str, embedding)) + "]"


def _l2_normalize(vec: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vec)
    return vec / norm if norm > 0 else vec


# ---------------------------------------------------------------------------
# Persona persistence
# ---------------------------------------------------------------------------

def upsert_personas(conn, model) -> Dict[str, int]:
    """Embed each persona description and upsert. Returns slug -> persona_id."""
    slugs = [p["slug"] for p in PERSONAS]
    descriptions = [p["description"] for p in PERSONAS]
    embeddings = model.encode(descriptions)

    slug_to_id: Dict[str, int] = {}
    with conn.cursor() as cur:
        for persona, emb in zip(PERSONAS, embeddings):
            cur.execute(
                """
                INSERT INTO personas (slug, name, description, embedding, updated_at)
                VALUES (%s, %s, %s, %s::vector, NOW())
                ON CONFLICT (slug) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    embedding = EXCLUDED.embedding,
                    updated_at = NOW()
                RETURNING id
                """,
                (persona["slug"], persona["name"], persona["description"],
                 _format_embedding(emb.tolist())),
            )
            slug_to_id[persona["slug"]] = cur.fetchone()[0]
    conn.commit()
    logger.info(f"Upserted {len(slug_to_id)} personas")
    return slug_to_id


# ---------------------------------------------------------------------------
# Catalog loading
# ---------------------------------------------------------------------------

def get_locations(conn) -> List[Dict[str, Any]]:
    slug_filter = os.getenv("LOCATION_SLUG")
    with conn.cursor() as cur:
        if slug_filter:
            cur.execute("SELECT id, slug, name FROM locations WHERE slug = %s", (slug_filter,))
        else:
            cur.execute("SELECT id, slug, name FROM locations ORDER BY id")
        rows = cur.fetchall()
    return [{"id": r[0], "slug": r[1], "name": r[2]} for r in rows]


def get_catalog(conn, location_id: int) -> List[Dict[str, Any]]:
    """Fetch real, tourist (non-utility) attractions for a location, most popular first."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT place_id, name, categories, description
            FROM attractions
            WHERE location_id = %s
              AND embedding IS NOT NULL
              AND (type IS NULL OR type <> 'utility')
            ORDER BY popularity DESC NULLS LAST, name ASC
            LIMIT %s
            """,
            (location_id, CATALOG_LIMIT),
        )
        rows = cur.fetchall()
    catalog = []
    for place_id, name, categories, description in rows:
        cats = ", ".join(categories) if isinstance(categories, list) else (categories or "")
        catalog.append({
            "place_id": place_id,
            "name": name,
            "categories": cats,
            "description": (description or "")[:160],
        })
    return catalog


def get_member_embeddings(conn, place_ids: List[str]) -> Dict[str, np.ndarray]:
    if not place_ids:
        return {}
    with conn.cursor() as cur:
        cur.execute(
            "SELECT place_id, embedding FROM attractions WHERE place_id = ANY(%s) AND embedding IS NOT NULL",
            (place_ids,),
        )
        rows = cur.fetchall()
    result: Dict[str, np.ndarray] = {}
    for place_id, emb in rows:
        if isinstance(emb, str):
            result[place_id] = np.array(json.loads(emb), dtype=np.float32)
        else:
            result[place_id] = np.array(list(emb), dtype=np.float32)
    return result


# ---------------------------------------------------------------------------
# LLM generation
# ---------------------------------------------------------------------------

def build_prompt(
    persona: Dict[str, str],
    city_name: str,
    catalog: List[Dict[str, Any]],
    n_trips: int,
    existing_names: Optional[List[str]] = None,
) -> str:
    lines = [
        f"{i + 1}. [{a['place_id']}] {a['name']} ({a['categories']})"
        for i, a in enumerate(catalog)
    ]
    catalog_block = "\n".join(lines)
    avoid_block = ""
    if existing_names:
        names = "\n".join(f"- {n}" for n in existing_names)
        avoid_block = (
            f"\nThe following routes already exist for this persona; make the new "
            f"routes clearly different from them:\n{names}\n"
        )
    return (
        f"You are a local travel expert for {city_name}.\n\n"
        f"Traveler persona: {persona['name']}. {persona['description']}\n\n"
        f"Below is the ONLY list of real attractions you may use. Each line is "
        f"\"[place_id] Name (categories)\".\n\n"
        f"{catalog_block}\n"
        f"{avoid_block}\n"
        f"Compose {n_trips} distinct popular day-trip routes that this persona "
        f"would love. Each route must be an ordered sequence of {MIN_STOPS} to {MAX_STOPS} "
        f"attractions chosen strictly from the list above, using the exact place_id values. "
        f"Do not invent place_ids. Avoid repeating the same attraction within a route.\n\n"
        f"Return ONLY valid JSON of this exact shape:\n"
        f'{{"trips": [{{"name": "short route title", "description": "one sentence", '
        f'"place_ids": ["id1", "id2", "id3", "id4"]}}]}}'
    )


def call_gemini(prompt: str, max_retries: int = 6) -> Optional[Dict[str, Any]]:
    """Call Gemini with backoff on transient 503/429 overload errors."""
    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not set; cannot generate popular trips")
        return None
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 2048,
            "responseMimeType": "application/json",
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    for attempt in range(1, max_retries + 1):
        try:
            res = requests.post(
                url, json=payload, timeout=90,
                headers={"Content-Type": "application/json"},
            )
            if res.status_code in (429, 503):
                wait = min(60, 2 ** attempt)
                logger.warning(
                    f"Gemini {res.status_code} on {GEMINI_MODEL} "
                    f"(attempt {attempt}/{max_retries}); retrying in {wait}s"
                )
                time.sleep(wait)
                continue
            res.raise_for_status()
            text = res.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)
        except (requests.RequestException, KeyError, IndexError, json.JSONDecodeError) as err:
            logger.error(f"Gemini request/parse failed: {err}")
            return None
    logger.error(f"Gemini still unavailable for {GEMINI_MODEL} after {max_retries} attempts")
    return None


def validate_trip(trip: Dict[str, Any], catalog_ids: set) -> Optional[Dict[str, Any]]:
    """Drop hallucinated ids, dedupe, enforce stop bounds. Returns None if invalid."""
    raw_ids = trip.get("place_ids") or []
    seen = set()
    valid_ids: List[str] = []
    for pid in raw_ids:
        if pid in catalog_ids and pid not in seen:
            seen.add(pid)
            valid_ids.append(pid)
        elif pid not in catalog_ids:
            logger.warning(f"Dropping hallucinated place_id: {pid}")
    valid_ids = valid_ids[:MAX_STOPS]
    if len(valid_ids) < MIN_STOPS:
        logger.warning(f"Trip '{trip.get('name')}' has too few valid stops ({len(valid_ids)}); skipping")
        return None
    return {
        "name": (trip.get("name") or "Popular route")[:120],
        "description": trip.get("description"),
        "place_ids": valid_ids,
    }


# ---------------------------------------------------------------------------
# Persistence of trips
# ---------------------------------------------------------------------------

def clear_location_trips(conn, location_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM popular_trips WHERE location_id = %s", (location_id,))
    conn.commit()


def get_existing_trip_names(conn, location_id: int, persona_id: int) -> List[str]:
    """Names of trips already stored for this (location, persona) pair."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT name FROM popular_trips WHERE location_id = %s AND persona_id = %s ORDER BY id",
            (location_id, persona_id),
        )
        return [row[0] for row in cur.fetchall()]


def insert_trip(conn, location_id: int, persona_id: int, trip: Dict[str, Any],
                member_embeddings: Dict[str, np.ndarray]) -> bool:
    embs = [member_embeddings[pid] for pid in trip["place_ids"] if pid in member_embeddings]
    if not embs:
        logger.warning(f"No member embeddings for trip '{trip['name']}'; skipping")
        return False
    trip_embedding = _l2_normalize(np.mean(np.stack(embs), axis=0))

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO popular_trips (location_id, persona_id, name, description, embedding, model)
            VALUES (%s, %s, %s, %s, %s::vector, %s)
            RETURNING id
            """,
            (location_id, persona_id, trip["name"], trip.get("description"),
             _format_embedding(trip_embedding.tolist()), GEMINI_MODEL),
        )
        popular_trip_id = cur.fetchone()[0]
        for position, place_id in enumerate(trip["place_ids"]):
            cur.execute(
                """
                INSERT INTO popular_trip_attractions (popular_trip_id, place_id, position)
                VALUES (%s, %s, %s)
                ON CONFLICT (popular_trip_id, place_id) DO NOTHING
                """,
                (popular_trip_id, place_id, position),
            )
    conn.commit()
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY is required. Aborting.")
        sys.exit(1)

    logger.info("Loading sentence-transformers model (all-MiniLM-L6-v2)...")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("all-MiniLM-L6-v2")

    config = get_db_config()
    logger.info(f"Connecting to {config['host']}:{config['port']}/{config['database']}")
    conn = psycopg2.connect(**config)
    try:
        slug_to_persona_id = upsert_personas(conn, model)

        locations = get_locations(conn)
        if not locations:
            logger.error("No locations found. Load attractions first.")
            sys.exit(1)

        total_trips = 0
        for loc in locations:
            catalog = get_catalog(conn, loc["id"])
            if len(catalog) < MIN_STOPS:
                logger.warning(f"Location '{loc['slug']}' has too few attractions; skipping")
                continue
            catalog_ids = {a["place_id"] for a in catalog}
            logger.info(f"Location '{loc['name']}' ({loc['slug']}): {len(catalog)} attractions offered to LLM")

            if FILL_MISSING:
                logger.info("Fill-missing mode: keeping existing trips, topping up short personas")
            else:
                clear_location_trips(conn, loc["id"])

            for persona in PERSONAS:
                persona_id = slug_to_persona_id[persona["slug"]]

                existing_names: List[str] = []
                n_trips = TRIPS_PER_PERSONA
                if FILL_MISSING:
                    existing_names = get_existing_trip_names(conn, loc["id"], persona_id)
                    n_trips = TRIPS_PER_PERSONA - len(existing_names)
                    if n_trips <= 0:
                        logger.info(
                            f"  persona '{persona['slug']}': already has "
                            f"{len(existing_names)}/{TRIPS_PER_PERSONA} trips; skipping"
                        )
                        continue
                    logger.info(
                        f"  persona '{persona['slug']}': has {len(existing_names)}, "
                        f"requesting {n_trips} more"
                    )

                prompt = build_prompt(persona, loc["name"], catalog, n_trips, existing_names)
                result = call_gemini(prompt)
                if not result or "trips" not in result:
                    logger.warning(f"No trips returned for persona '{persona['slug']}' in '{loc['slug']}'")
                    continue

                valid_trips = []
                for raw_trip in result["trips"]:
                    validated = validate_trip(raw_trip, catalog_ids)
                    if validated:
                        valid_trips.append(validated)
                # Cap at n_trips even if Gemini returned more than asked.
                valid_trips = valid_trips[:n_trips]

                all_ids = [pid for t in valid_trips for pid in t["place_ids"]]
                member_embeddings = get_member_embeddings(conn, all_ids)

                for trip in valid_trips:
                    if insert_trip(conn, loc["id"], persona_id, trip, member_embeddings):
                        total_trips += 1
                logger.info(f"  persona '{persona['slug']}': {len(valid_trips)} trips")
                time.sleep(2)  # ease rate pressure between persona calls

        logger.info(f"Done. Generated {total_trips} popular trips across {len(locations)} location(s).")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
