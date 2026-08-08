"""Hard filters - strict constraints applied as SQL WHERE clauses (location, availability, required attrs)."""
from typing import Dict, Any


def build_hard_filters(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build the filters dict from user context. Keys must match DB column names exactly.
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

