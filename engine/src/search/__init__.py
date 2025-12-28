"""
Search module for vector similarity search and filtering.

This module contains:
- Vector search execution
- Hard filters (SQL-level constraints)
- Soft filters (post-query scoring and ranking)
"""
from .vector_search import search_similar_attractions
from .hard_filters import build_hard_filters
from .soft_filters import apply_soft_filters, calculate_combined_score

__all__ = [
    'search_similar_attractions',
    'build_hard_filters',
    'apply_soft_filters',
    'calculate_combined_score',
]

