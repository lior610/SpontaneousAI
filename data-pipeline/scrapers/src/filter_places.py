import json
import logging
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

CITY = os.getenv("CITY", "london").strip().lower()
DATA_DIR = BASE_DIR / "data" / CITY
INPUT_FILE = os.getenv("FILTER_INPUT_FILE", str(DATA_DIR / f"foursquare_{CITY}_attractions.json"))
OUTPUT_FILE = os.getenv("FILTER_OUTPUT_FILE", str(DATA_DIR / "filtered_places.json"))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(BASE_DIR / 'filter_places.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


ATTRACTION_KEYWORDS = [
    # Food
    "Pizza", "Restaurant", "Bakery", "Cafe", "Coffee", "Deli", "Donut", "Sandwich",
    "Steakhouse", "Burger", "Sushi", "Breakfast", "Diner", "Seafood", "Bagel",
    "Noodle", "Ramen", "Taco", "Burrito", "BBQ", "Wings", "Dumpling",
    "Ice Cream", "Dessert", "Yogurt", "Chocolate", "Candy",
    
    # Drink & Nightlife
    "Bar", "Pub", "Club", "Brewery", "Lounge", "Speakeasy", "Wine", "Beer", 
    "Cocktail", "Karaoke", "Dive",
    
    # Arts & Ent
    "Museum", "Gallery", "Theater", "Music", "Concert", "Comedy", "Arcade", 
    "Bowling", "Casino", "Stadium", "Cinema", "Movie",
    
    # Outdoors
    "Park", "Garden", "Plaza", "Beach", "Lookout", "Trail", "River", "Lake", 
    "Playground", "Monument", "Landmark",
    
    # Shopping (Curated)
    "Mall", "Bookstore", "Record", "Market", "Boutique", "Thrift", "Vintage"
]

UTILITY_KEYWORDS = [
    "Pharmacy", "Grocery", "Supermarket", "Convenience", "Drugstore", "ATM", 
    "Gas Station", "Gym", "Subway", "Station"
]

MINIMUM_COUNT = 3  # filter minimum occurrences of category


def extract_unique_categories(input_file):
    """Extract all unique categories from the foursquare JSON file with counts."""
    
    category_counts = {}
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        logger.error(f"Input file not found: {input_file}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {input_file}: {e}")
        raise
    
    # Iterate through all places and collect categories with counts
    for place in data:
        if 'categories' in place and isinstance(place['categories'], list):
            for category in place['categories']:
                category_counts[category] = category_counts.get(category, 0) + 1
    
    # Sort by count (descending), then by name (ascending)
    sorted_categories = sorted(category_counts.items(), key=lambda x: (-x[1], x[0]))
    output_data = [{"category": cat, "count": count} for cat, count in sorted_categories]
    
    logger.info(f"Extracted {len(output_data)} unique categories")
    return output_data

# Filter category helper functions
def is_attraction(cat_name):
    for keyword in ATTRACTION_KEYWORDS:
        if keyword.lower() in cat_name.lower():
            return True
    return False

def is_utility(cat_name):
    for keyword in UTILITY_KEYWORDS:
        if keyword.lower() in cat_name.lower():
            return True
    return False

def classify_category(category):
    """Classify category as 'attraction' or 'utility'."""
    
    # Check if it's an ATTRACTION first (takes priority)
    if is_attraction(category):
        return 'attraction'
    
    # Then check if it's a utility
    elif is_utility(category):
        return 'utility'
    return None

def filter_categories(categories):
    """Filter categories and divide into attractions and utilities."""


    attractions = []
    utilities = []
    
    for item in categories:
        cat_name = item['category']
        cat_count = item['count']
        
        if cat_count < MINIMUM_COUNT:
            continue
        
        # Classify
        if classify_category(cat_name) == 'utility':
            utilities.append(item)
        elif classify_category(cat_name) == 'attraction':
            attractions.append(item)
    
    return attractions, utilities


def filter_places(places_file, attractions_cats, utilities_cats):
    """Filter places and mark them as attraction or utility."""
    
    # Create sets of category names for faster lookup
    attractions_set = {item['category'] for item in attractions_cats}
    utilities_set = {item['category'] for item in utilities_cats}
    
    logger.info(f"Loaded {len(attractions_set)} attraction categories and {len(utilities_set)} utility categories")
    
    # Load places
    try:
        with open(places_file, 'r', encoding='utf-8') as f:
            places = json.load(f)
    except FileNotFoundError:
        logger.error(f"Places file not found: {places_file}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {places_file}: {e}")
        raise
    
    logger.info(f"Loaded {len(places)} total places from {places_file}")
    
    filtered_places = []
    excluded_count = 0
    
    for place in places:
        place_categories = place.get('categories', [])
        
        # Check if any category exists in our filtered lists
        matched_type = None
        for category in place_categories:
            if category in attractions_set:
                matched_type = 'attraction'
                break  # Prefer attraction if multiple categories
            elif category in utilities_set:
                matched_type = 'utility'
        
        # Only include places that have at least one valid category
        if matched_type:
            place['type'] = matched_type
            filtered_places.append(place)
        else:
            excluded_count += 1
    
    logger.info(f"Filtered places: {len(filtered_places)}, Excluded: {excluded_count}")
    return filtered_places, excluded_count

def identify_non_unique_names(places):
    """Get list of non-unique place names (chains/duplicates)."""
    
    name_counts = {}
    
    for place in places:
        name = place.get('name', '').strip()
        if name:
            name_counts[name] = name_counts.get(name, 0) + 1
    
    # Return only non-unique names (count > 1)
    non_unique = [name for name, count in name_counts.items() if count > 1]
    # return amount of unique names found
    all_places_count = len(name_counts)
    
    logger.info(f"Found {len(non_unique)} non-unique place names (chains/duplicates) out of {all_places_count} total places")
    return sorted(non_unique)

def main():
    input_file = INPUT_FILE
    output_file = OUTPUT_FILE
    
    logger.info("Starting filter process...")
    logger.info(f"City: {CITY}")
    logger.info(f"Input file: {input_file}")
    logger.info(f"Output file: {output_file}")
    
    try:
        # Check if input file exists
        if not Path(input_file).exists():
            logger.error(f"Input file not found: {input_file}")
            return False
        
        logger.info(f"Processing {input_file}...")
        
        # Extract and classify categories
        categories = extract_unique_categories(input_file)
        if not categories:
            logger.warning("No categories found in input file")
            return False
        
        attractions, utilities = filter_categories(categories)
        logger.info(f"Classified categories - Attractions: {len(attractions)}, Utilities: {len(utilities)}")
        
        # Filter places
        filtered_places, excluded_count = filter_places(input_file, attractions, utilities)
        
        # Save output
        try:
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(filtered_places, f, ensure_ascii=False, indent=2)
            logger.info(f"Successfully saved {len(filtered_places)} filtered places to {output_file}")
        except IOError as e:
            logger.error(f"Failed to write output file {output_file}: {e}")
            return False
        
        # Summary
        attractions_count = sum(1 for p in filtered_places if p['type'] == 'attraction')
        utilities_count = sum(1 for p in filtered_places if p['type'] == 'utility')
        
        logger.info(f"Summary - Total places: {len(filtered_places)}, "
                   f"Attractions: {attractions_count}, Utilities: {utilities_count}, Excluded: {excluded_count}")
        
        # Identify non-unique names
        non_unique_names = identify_non_unique_names(filtered_places)
        
        return True
        
    except Exception as e:
        logger.error(f"Unexpected error during processing: {e}", exc_info=True)
        return False


if __name__ == '__main__':
    success = main()
    if success:
        logger.info("Process completed successfully")
    else:
        logger.error("Process failed")
