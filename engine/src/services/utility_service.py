"""
Service layer for immediate need utilities.
"""
from typing import List, Optional
import re
from db.attractionsConnection import get_db_connection
from src.db.utility_queries import execute_closest_utility_query
from models.attraction import AttractionResponse
from src.services.geo_utils import haversine

# Mapping from parent to exact DB categories (Type = utility)
UTILITY_CATEGORY_MAP = {
    "pharmacy": ['Pharmacy', 'Drugstore', 'Health and Medicine', 'Eyecare Store', 'Cosmetics Store', 'Health and Beauty'],
    "medical": ['Hospital', 'Medical Center', "Doctor's Office"],
    "grocery": ['Grocery Store', 'Organic Grocery', 'Big Box Store', 'Fruit and Vegetable Store', 'Butcher', 'Cheese Store', 'Food and Beverage Retail', 'Dairy Store', 'Imported Food Store', 'Supermarket', 'Health Food Store'],
    "convenience": ['Convenience Store', 'Snack Place', 'Newsstand', 'Newsagent', 'Discount Store', 'Liquor Store', 'Miscellaneous Store', 'Department Store', 'Retail', 'Stationery Store', 'Post Office', 'Smoke Shop', 'Florist', 'Hardware Store'],
    "police_emergency": ['Police Station', 'Fire Station', 'Ambulance Service']
}

async def get_closest_utilities(
    parent_category: str, 
    lat: float, 
    lng: float, 
    location_id: int,
    current_hour: Optional[int] = None, 
    limit: int = 5
) -> List[dict]:
    
    db_categories = UTILITY_CATEGORY_MAP.get(parent_category.lower(), [])
    
    with get_db_connection() as conn:
        # Fetch more than limit in case python filtering drops some rows
        query_limit = limit * 3 if current_hour is not None else limit
        
        rows, cols = execute_closest_utility_query(
            conn=conn, 
            categories=db_categories,
            lat=lat,
            lng=lng,
            location_id=location_id,
            current_hour=current_hour,
            limit=query_limit
        )
        
        results = []
        for row in rows:
            record = dict(zip(cols, row))
            
            # Map exact Haversine distance in Kilometers to return in output
            if record.get('latitude') is not None and record.get('longitude') is not None:
                record['distance'] = haversine(lat, lng, record['latitude'], record['longitude'])
            else:
                record['distance'] = None
                
            # Python fallback hour check for unpredictable hour strings (like "12 PM - 8 PM")
            # Currently we just let them pass as we don't have a reliable parser for custom strings,
            # but this is where complex NLP or time parsing logic would reside if implemented.
            if current_hour is not None and record.get('hours'):
                if not re.match(r'^\d{1,2}:\d{2}-\d{1,2}:\d{2}$', record['hours']):
                    pass # Keep the row
            
            results.append(record)
            if len(results) >= limit:
                break
                
        return results
