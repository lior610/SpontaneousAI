#!/usr/bin/env python3
"""
Cluster attractions using UMAP + HDBSCAN.

Loads embeddings from the database, reduces dimensionality with UMAP,
clusters with HDBSCAN, and writes cluster_id back to the database.

Run load_places_to_db.py first to populate embeddings.

Usage:
    python data-pipeline/scripts/cluster_attractions.py

Env vars:
    UMAP_N_COMPONENTS - UMAP output dimensions (default: 15)
    UMAP_N_NEIGHBORS  - UMAP local vs global balance (default: 15)
    MIN_CLUSTER_SIZE  - HDBSCAN min cluster size (default: 5)
    MIN_SAMPLES       - HDBSCAN min samples for core points (default: same as MIN_CLUSTER_SIZE; lower = less noise)
    CLUSTER_SELECTION - HDBSCAN method: "eom" or "leaf" (default: eom; leaf = fewer clusters)
    ASSIGN_NOISE       - If 1, assign noise points to nearest cluster (default: 0)
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
from typing import List, Optional, Tuple

# Add shared/python to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "shared" / "python"))

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


def load_attractions(config: dict) -> Tuple[List[str], np.ndarray]:
    """Load place_ids and embeddings from database."""
    with psycopg2.connect(**config) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT place_id, embedding
                FROM attractions
                WHERE embedding IS NOT NULL
            """)
            rows = cur.fetchall()

    place_ids = [str(row[0]) for row in rows]
    # pgvector returns embedding as string '[0.1,0.2,...]' - parse to list
    def parse_embedding(emb):
        if emb is None:
            return None
        if isinstance(emb, (list, np.ndarray)):
            return np.asarray(emb, dtype=np.float32)
        return np.array(json.loads(emb) if isinstance(emb, str) else list(emb), dtype=np.float32)
    embeddings = np.array([parse_embedding(row[1]) for row in rows], dtype=np.float32)

    logger.info(f"Loaded {len(place_ids)} attractions with embeddings")
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


def update_cluster_ids(config: dict, place_ids: List[str], labels: np.ndarray) -> None:
    """Write cluster_id to database (NULL for noise)."""
    values = [(int(l) if l >= 0 else None, pid) for pid, l in zip(place_ids, labels)]
    with psycopg2.connect(**config) as conn:
        with conn.cursor() as cur:
            cur.executemany("UPDATE attractions SET cluster_id = %s WHERE place_id = %s", values)
        conn.commit()
    logger.info(f"Updated {len(place_ids)} rows")


def main():
    config = get_db_config()
    logger.info(f"Connecting to {config['host']}:{config['port']}/{config['database']}")

    place_ids, embeddings = load_attractions(config)
    if not place_ids:
        logger.error("No attractions with embeddings. Run load_places_to_db.py first.")
        sys.exit(1)

    n_components = int(os.getenv("UMAP_N_COMPONENTS", "15"))
    n_neighbors = int(os.getenv("UMAP_N_NEIGHBORS", "15"))
    min_cluster_size = int(os.getenv("MIN_CLUSTER_SIZE", "5"))
    min_samples = os.getenv("MIN_SAMPLES")
    min_samples = int(min_samples) if min_samples else None
    cluster_selection = os.getenv("CLUSTER_SELECTION", "eom")

    embeddings_reduced = reduce_with_umap(embeddings, n_components=n_components, n_neighbors=n_neighbors)
    labels = cluster_hdbscan(
        embeddings_reduced,
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        cluster_selection_method=cluster_selection,
    )
    if os.getenv("ASSIGN_NOISE", "0") == "1":
        labels = assign_noise_to_nearest_cluster(embeddings_reduced, labels)
    update_cluster_ids(config, place_ids, labels)

    logger.info("Done.")


if __name__ == "__main__":
    main()
