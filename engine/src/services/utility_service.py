"""
Utility Service — handles "I need X right now" requests (pharmacy, grocery, food, etc.)
Finds the closest matching places using category overlap + distance sorting.
"""
from typing import List, Optional
import re
from db.attractionsConnection import get_db_connection
from src.db.utility_queries import execute_closest_utility_query
from models.attraction import AttractionResponse
from src.services.geo_utils import haversine

# Maps a parent category (what the user asks for) to the exact DB category strings.
# "food" is also used by cluster_queries.py to exclude food from regular recommendations.
UTILITY_CATEGORY_MAP = {
    "pharmacy": ['Pharmacy', 'Drugstore', 'Health and Medicine', 'Eyecare Store', 'Cosmetics Store', 'Health and Beauty'],
    "medical": ['Hospital', 'Medical Center', "Doctor's Office"],
    "grocery": ['Grocery Store', 'Organic Grocery', 'Big Box Store', 'Fruit and Vegetable Store', 'Butcher', 'Cheese Store', 'Food and Beverage Retail', 'Dairy Store', 'Imported Food Store', 'Supermarket', 'Health Food Store'],
    "convenience": ['Convenience Store', 'Snack Place', 'Newsstand', 'Newsagent', 'Discount Store', 'Liquor Store', 'Miscellaneous Store', 'Department Store', 'Retail', 'Stationery Store', 'Post Office', 'Smoke Shop', 'Florist', 'Hardware Store'],
    "police_emergency": ['Police Station', 'Fire Station', 'Ambulance Service'],
    "food": ['Restaurant', 'Cafe', 'Café', 'Coffee Shop', 'Bakery', 'Pizza Place', 'Pizzeria', 'Diner', 'Seafood Restaurant', 'Steakhouse', 'Burger Joint', 'Sushi Restaurant', 'Noodle House', 'BBQ Joint', 'Breakfast Spot', 'Sandwich Shop', 'Sandwich Spot', 'Ice Cream Shop', 'Deli', 'Bagel Shop', 'Fried Chicken Joint', 'Wings Joint']
}

# Food lives in the attractions table (type='attraction'), not in utilities
FOOD_CATEGORIES = {"food"}

async def get_closest_utilities(
    parent_category: str, 
    lat: float, 
    lng: float, 
    location_id: int,
    current_hour: Optional[int] = None, 
    limit: int = 5
) -> List[dict]:
    
    db_categories = UTILITY_CATEGORY_MAP.get(parent_category.lower(), [])
    type_filter = 'attraction' if parent_category.lower() in FOOD_CATEGORIES else 'utility'

    with get_db_connection() as conn:
        query_limit = limit * 3 if current_hour is not None else limit

        rows, cols = execute_closest_utility_query(
            conn=conn,
            categories=db_categories,
            lat=lat,
            lng=lng,
            location_id=location_id,
            current_hour=current_hour,
            limit=query_limit,
            type_filter=type_filter
        )
        
        results = []
        for row in rows:
            record = dict(zip(cols, row))

            if record.get('latitude') is not None and record.get('longitude') is not None:
                record['distance'] = haversine(lat, lng, record['latitude'], record['longitude'])
            else:
                record['distance'] = None

            results.append(record)

        # Re-sort by accurate haversine distance. The SQL orders by an approximate
        # (flat-earth) distance for a fast index-friendly scan; sorting here on the
        # exact great-circle distance guarantees true-nearest-first ordering.
        # Records without coordinates sort last.
        results.sort(key=lambda r: r['distance'] if r['distance'] is not None else float('inf'))

        return results[:limit]
