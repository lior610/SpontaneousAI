"""
Shared helpers for the data-pipeline maintenance scripts.

These scripts are run manually, outside Docker, so POSTGRES_HOST defaults to
localhost here (unlike the containerized services, which default to the
Docker service name).
"""
import json
import os

import numpy as np


def get_db_config() -> dict:
    return {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "database": os.getenv("POSTGRES_ATTRACTIONS_DB", "attractions"),
        "user": os.getenv("POSTGRES_USER", "postgres"),
        "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
    }


def parse_embedding(emb):
    if emb is None:
        return None
    if isinstance(emb, (list, np.ndarray)):
        return np.asarray(emb, dtype=np.float32)
    return np.array(json.loads(emb) if isinstance(emb, str) else list(emb), dtype=np.float32)
