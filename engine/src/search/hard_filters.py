"""
Hard Filters - SQL-level constraints for search queries.

Hard filters are strict requirements that must be satisfied. They are applied
as WHERE clauses in the database query, filtering results before they're returned.

Examples:
- Location: city, country
- Availability: is_open_now
- Required attributes: accessibility_features, age_min

These filters reduce the search space at the database level.
"""
from typing import Dict, Any


def build_hard_filters(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build hard filters dictionary from user context.
    
    Hard filters are strict constraints applied as SQL WHERE clauses.
    They filter results at the database level before similarity ranking.
    
    Note: Filter keys must match database column names exactly.
    
    Args:
        context: Dictionary containing user context (city, country, is_open_now, etc.)
        
    Returns:
        Dictionary of filters to apply in database query (keys = column names)
        
    Examples:
        >>> build_hard_filters({"city": "Paris", "is_open_now": True})
        {"city": "Paris", "is_open_now": True}
    """
    filters: Dict[str, Any] = {}

    # Location filters
    if context.get("city"):
        filters["city"] = context["city"]
    if context.get("country"):
        filters["country"] = context["country"]

    # Availability filter
    if context.get("is_open_now"):
        filters["is_open_now"] = True

    # TODO: Add more hard filters as needed:
    # - Location radius (requires geospatial query)
    # - Required accessibility features
    # - Minimum age requirements
    # - Required booking status

    return filters

