#!/usr/bin/env python3
"""
Cluster attractions using UMAP + HDBSCAN. Per-location clustering.

Loads embeddings per location_id, reduces dimensionality with UMAP,
clusters with HDBSCAN, creates location_clusters rows, and writes
location_cluster_id to attractions.

Run load_places_to_db.py first to populate embeddings.

Usage:
    python data-pipeline/scripts/cluster_attractions.py
    LOCATION_SLUG=london python data-pipeline/scripts/cluster_attractions.py  # one location only

Env vars:
    LOCATION_SLUG     - If set, cluster only this location. Else cluster all locations.
    UMAP_N_COMPONENTS - UMAP output dimensions (default: 15)
    UMAP_N_NEIGHBORS  - UMAP local vs global balance (default: 30)
    MIN_CLUSTER_SIZE  - HDBSCAN min cluster size (default: 100)
    MIN_SAMPLES       - HDBSCAN min samples (default: same as MIN_CLUSTER_SIZE)
    CLUSTER_SELECTION - HDBSCAN method: "eom" or "leaf" (default: eom)
    ASSIGN_NOISE      - If 1, assign noise to nearest cluster (default: 1)
    POSTGRES_*        - DB connection
"""
import json
import os
import sys
import logging
from pathlib import Path
from typing import List, Optional, Tuple, Any

# Add shared/python to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "shared" / "python"))

# Load .env from project root (for POSTGRES_* etc.)
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env", override=True)
except ImportError:
    pass

import numpy as np
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


def get_location_ids(config: dict, location_slug: Optional[str] = None) -> List[Tuple[int, str]]:
    """Return list of (location_id, slug) to cluster. If location_slug set, filter to that."""
    with psycopg2.connect(**config) as conn:
        with conn.cursor() as cur:
            if location_slug:
                cur.execute(
                    "SELECT id, slug FROM locations WHERE slug = %s",
                    (location_slug,),
                )
            else:
                cur.execute(
                    "SELECT l.id, l.slug FROM locations l "
                    "WHERE EXISTS (SELECT 1 FROM attractions a WHERE a.location_id = l.id AND a.embedding IS NOT NULL)"
                )
            return cur.fetchall()


def load_attractions_for_location(
    config: dict, location_id: int
) -> Tuple[List[str], np.ndarray]:
    """Load place_ids and embeddings for one location."""
    with psycopg2.connect(**config) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT place_id, embedding
                FROM attractions
                WHERE location_id = %s AND embedding IS NOT NULL
                """,
                (location_id,),
            )
            rows = cur.fetchall()

    place_ids = [str(row[0]) for row in rows]

    def parse_embedding(emb):
        if emb is None:
            return None
        if isinstance(emb, (list, np.ndarray)):
            return np.asarray(emb, dtype=np.float32)
        return np.array(json.loads(emb) if isinstance(emb, str) else list(emb), dtype=np.float32)

    embeddings = np.array([parse_embedding(row[1]) for row in rows], dtype=np.float32)
    logger.info(f"Loaded {len(place_ids)} attractions for location_id={location_id}")
    return place_ids, embeddings


def reduce_with_umap(embeddings: np.ndarray, n_components: int = 15, n_neighbors: int = 15) -> np.ndarray:
    """Reduce 384d embeddings to lower dimension for clustering."""
    import umap

    logger.info(f"UMAP: {embeddings.shape[1]}d → {n_components}d")
    reducer = umap.UMAP(
        n_components=n_components,
        n_neighbors=n_neighbors,
        metric="cosine",
        min_dist=0.0,
        random_state=42,
    )
    return reducer.fit_transform(embeddings).astype(np.float32)


def cluster_hdbscan(
    embeddings: np.ndarray,
    min_cluster_size: int = 5,
    min_samples: Optional[int] = None,
    cluster_selection_method: str = "eom",
) -> np.ndarray:
    """Run HDBSCAN. Returns labels (-1 = noise)."""
    import hdbscan

    if min_samples is None:
        min_samples = min_cluster_size
    logger.info(f"HDBSCAN (min_cluster_size={min_cluster_size}, min_samples={min_samples}, method={cluster_selection_method})")
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        metric="euclidean",
        cluster_selection_method=cluster_selection_method,
    )
    labels = clusterer.fit_predict(embeddings)
    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise = int((labels == -1).sum())
    logger.info(f"Found {n_clusters} clusters, {n_noise} noise points")
    return labels


def assign_noise_to_nearest_cluster(
    embeddings: np.ndarray,
    labels: np.ndarray,
) -> np.ndarray:
    """Assign each noise point (-1) to its nearest cluster centroid. Returns updated labels."""
    noise_mask = labels == -1
    if not noise_mask.any():
        return labels

    clustered_mask = ~noise_mask
    unique_clusters = np.unique(labels[clustered_mask])
    centroids = np.array([
        embeddings[labels == c].mean(axis=0) for c in unique_clusters
    ])

    from scipy.spatial.distance import cdist
    noise_embeddings = embeddings[noise_mask]
    dists = cdist(noise_embeddings, centroids, metric="euclidean")
    nearest = unique_clusters[np.argmin(dists, axis=1)]

    out = labels.copy()
    out[noise_mask] = nearest
    n_assigned = int(noise_mask.sum())
    logger.info(f"Assigned {n_assigned} noise points to nearest cluster")
    return out


def update_location_clusters(
    config: dict,
    location_id: int,
    place_ids: List[str],
    labels: np.ndarray,
) -> None:
    """Create location_clusters rows and update attractions with location_cluster_id."""
    unique_labels = sorted(set(int(l) for l in labels if l >= 0))
    if not unique_labels:
        logger.warning("No clusters to write")
        return

    with psycopg2.connect(**config) as conn:
        with conn.cursor() as cur:
            # Clear old location_clusters for this location
            cur.execute("DELETE FROM location_clusters WHERE location_id = %s", (location_id,))
            # Insert new location_clusters
            for local_cluster_id in unique_labels:
                cur.execute(
                    "INSERT INTO location_clusters (location_id, cluster_id) VALUES (%s, %s) RETURNING id",
                    (location_id, local_cluster_id),
                )
            conn.commit()

            # Build place_id -> location_cluster_id map
            cur.execute(
                "SELECT id, cluster_id FROM location_clusters WHERE location_id = %s",
                (location_id,),
            )
            lc_map = {row[1]: row[0] for row in cur.fetchall()}

            # Update attractions
            updates = []
            for pid, l in zip(place_ids, labels):
                lc_id = lc_map.get(int(l)) if l >= 0 else None
                updates.append((lc_id, pid))

            cur.executemany(
                "UPDATE attractions SET location_cluster_id = %s WHERE place_id = %s",
                updates,
            )
        conn.commit()
    logger.info(f"Updated {len(place_ids)} rows for location_id={location_id}")


def main():
    config = get_db_config()
    location_slug = os.getenv("LOCATION_SLUG")
    logger.info(f"Connecting to {config['host']}:{config['port']}/{config['database']}")

    locations = get_location_ids(config, location_slug)
    if not locations:
        logger.error(
            "No locations with embeddings. Run load_places_to_db.py first. "
            "Or LOCATION_SLUG may not match."
        )
        sys.exit(1)

    n_components = int(os.getenv("UMAP_N_COMPONENTS", "15"))
    n_neighbors = int(os.getenv("UMAP_N_NEIGHBORS", "30"))
    min_cluster_size_env = os.getenv("MIN_CLUSTER_SIZE")
    min_samples = os.getenv("MIN_SAMPLES")
    min_samples = int(min_samples) if min_samples else None
    cluster_selection = os.getenv("CLUSTER_SELECTION", "eom")

    for location_id, slug in locations:
        logger.info(f"Clustering location_id={location_id} ({slug})...")
        place_ids, embeddings = load_attractions_for_location(config, location_id)
        if not place_ids:
            logger.warning(f"No attractions for {slug}, skipping")
            continue

        # Adaptive min_cluster_size for smaller locations (unless explicitly set)
        if min_cluster_size_env:
            min_cluster_size = int(min_cluster_size_env)
        else:
            n = len(place_ids)
            min_cluster_size = min(100, max(5, n // 100))
            logger.info(f"Adaptive min_cluster_size={min_cluster_size} (n={n})")

        embeddings_reduced = reduce_with_umap(
            embeddings, n_components=n_components, n_neighbors=n_neighbors
        )
        labels = cluster_hdbscan(
            embeddings_reduced,
            min_cluster_size=min_cluster_size,
            min_samples=min_samples,
            cluster_selection_method=cluster_selection,
        )
        if os.getenv("ASSIGN_NOISE", "1") == "1":
            labels = assign_noise_to_nearest_cluster(embeddings_reduced, labels)
        update_location_clusters(config, location_id, place_ids, labels)

    logger.info("Done.")


if __name__ == "__main__":
    main()
