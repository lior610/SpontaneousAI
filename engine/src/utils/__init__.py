"""
Utility functions for the engine service.
"""
from .formatting import format_embedding_for_pgvector, normalize_attraction_row

__all__ = [
    'format_embedding_for_pgvector',
    'normalize_attraction_row',
]

