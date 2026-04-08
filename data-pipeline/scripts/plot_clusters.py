#!/usr/bin/env python3
"""
Plot clusters from the database.

Loads attractions (place_id, embedding, location_cluster_id), reduces to 2D
with UMAP, and creates a scatter plot colored by cluster.

Usage:
    python data-pipeline/scripts/plot_clusters.py [--output clusters.png]
    python data-pipeline/scripts/plot_clusters.py --location london -o london_clusters.png

Env vars: LOCATION_SLUG (optional), POSTGRES_*
"""
import argparse
import json
import os
import sys
import logging
from pathlib import Path

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


def load_clusters(config: dict, location_slug: str = None):
    """Load place_id, embedding, location_cluster_id from database. Optionally filter by location."""
    with psycopg2.connect(**config) as conn:
        with conn.cursor() as cur:
            if location_slug:
                cur.execute("""
                    SELECT a.place_id, a.embedding, a.location_cluster_id
                    FROM attractions a
                    JOIN locations l ON a.location_id = l.id
                    WHERE a.embedding IS NOT NULL AND l.slug = %s
                """, (location_slug,))
            else:
                cur.execute("""
                    SELECT place_id, embedding, location_cluster_id
                    FROM attractions
                    WHERE embedding IS NOT NULL
                """)
            rows = cur.fetchall()

    def parse_embedding(emb):
        if emb is None:
            return None
        if isinstance(emb, (list, np.ndarray)):
            return np.asarray(emb, dtype=np.float32)
        return np.array(json.loads(emb) if isinstance(emb, str) else list(emb), dtype=np.float32)

    place_ids = []
    embeddings = []
    cluster_ids = []
    for row in rows:
        place_ids.append(str(row[0]))
        embeddings.append(parse_embedding(row[1]))
        cluster_ids.append(row[2] if row[2] is not None else -1)

    embeddings = np.array(embeddings, dtype=np.float32)
    cluster_ids = np.array(cluster_ids, dtype=np.int32)

    n_clusters = len(set(c for c in cluster_ids if c >= 0))
    n_noise = int((cluster_ids == -1).sum())
    logger.info(f"Loaded {len(place_ids)} attractions: {n_clusters} clusters, {n_noise} noise")

    return place_ids, embeddings, cluster_ids


def reduce_to_2d(embeddings: np.ndarray, n_neighbors: int = 15) -> np.ndarray:
    """Reduce 384d embeddings to 2D for visualization."""
    import umap

    logger.info("UMAP: 384d → 2d for visualization")
    reducer = umap.UMAP(
        n_components=2,
        n_neighbors=n_neighbors,
        metric="cosine",
        min_dist=0.0,
        random_state=42,
    )
    return reducer.fit_transform(embeddings)


def plot_clusters(
    coords_2d: np.ndarray,
    cluster_ids: np.ndarray,
    output_path: str,
) -> None:
    """Create scatter plot colored by cluster_id."""
    import matplotlib.pyplot as plt

    # Separate noise from clustered points
    noise_mask = cluster_ids == -1
    clustered_mask = ~noise_mask
    n_clusters = len(np.unique(cluster_ids[clustered_mask])) if clustered_mask.any() else 0
    n_noise = int(noise_mask.sum())

    fig, ax = plt.subplots(figsize=(14, 10))

    # Plot noise first (behind)
    if noise_mask.any():
        ax.scatter(
            coords_2d[noise_mask, 0],
            coords_2d[noise_mask, 1],
            c="#cccccc",
            s=8,
            alpha=0.4,
            label="noise",
        )

    # Plot clusters - each cluster gets a color from colormap
    if clustered_mask.any():
        unique_clusters = np.unique(cluster_ids[clustered_mask])
        n_clusters_val = len(unique_clusters)
        cmap = plt.colormaps["nipy_spectral"].resampled(n_clusters_val)

        for i, cid in enumerate(unique_clusters):
            mask = cluster_ids == cid
            ax.scatter(
                coords_2d[mask, 0],
                coords_2d[mask, 1],
                c=[cmap(i)],
                s=12,
                alpha=0.7,
                label=f"cluster {cid}" if n_clusters_val <= 20 else None,
            )

    ax.set_xlabel("UMAP 1")
    ax.set_ylabel("UMAP 2")
    ax.set_title(f"Attraction clusters (n_clusters={n_clusters}, noise={n_noise})")
    if n_clusters <= 20:
        ax.legend(loc="upper left", fontsize=8)
    ax.set_aspect("equal")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info(f"Saved plot to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Plot attraction clusters from DB")
    parser.add_argument(
        "--output", "-o",
        default="clusters_plot.png",
        help="Output image path (default: clusters_plot.png)",
    )
    parser.add_argument(
        "--location", "-l",
        default=None,
        help="Location slug to plot (e.g. london). Else plots all.",
    )
    args = parser.parse_args()

    location_slug = args.location or os.getenv("LOCATION_SLUG")

    config = get_db_config()
    logger.info(f"Connecting to {config['host']}:{config['port']}/{config['database']}")

    place_ids, embeddings, cluster_ids = load_clusters(config, location_slug)
    if not place_ids:
        logger.error("No attractions with embeddings. Run load_places_to_db.py first.")
        sys.exit(1)

    coords_2d = reduce_to_2d(embeddings)
    plot_clusters(coords_2d, cluster_ids, args.output)

    logger.info("Done.")


if __name__ == "__main__":
    main()
