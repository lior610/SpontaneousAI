import os
import json
import requests
import logging
import random
import time
from datetime import datetime
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FOURSQUARE_API_KEY = os.getenv("FOURSQUARE_API_KEY")
FOURSQUARE_BASE_URL = os.getenv("FOURSQUARE_BASE_URL")

HEADERS = {
    "Accept": "application/json",
    "X-Places-Api-Version": "2025-06-17",
    "Authorization": f"Bearer {FOURSQUARE_API_KEY}"
}

# NYC Bounds
# Load configuration from environment variables (Required)
try:
    LAT_MIN = float(os.environ["FOURSQUARE_LAT_MIN"])
    LAT_MAX = float(os.environ["FOURSQUARE_LAT_MAX"])
    LON_MIN = float(os.environ["FOURSQUARE_LON_MIN"])
    LON_MAX = float(os.environ["FOURSQUARE_LON_MAX"])
except KeyError as e:
    logger.error(f"Missing required environment variable for coordinates: {e}")
    raise
except ValueError as e:
    logger.error(f"Invalid coordinate value in environment variables: {e}")
    raise

def get_random_coords() -> str:
    lat = random.uniform(LAT_MIN, LAT_MAX)
    lon = random.uniform(LON_MIN, LON_MAX)
    return f"{lat},{lon}"

def search_attractions(ll: str, radius: int = 2000, limit: int = 100) -> Dict:
    params = {
        "ll": ll,
        "radius": radius,
        "limit": limit
    }
   
    response = requests.get(FOURSQUARE_BASE_URL, headers=HEADERS, params=params)
    response.raise_for_status()

    return response.json()


def normalize_place(p: Dict) -> Dict:
    return {
        "source": "foursquare",
        "place_id": p["fsq_place_id"],
        "name": p["name"],
        "categories": [c["name"] for c in p.get("categories", [])],
        "category_id": [c["fsq_category_id"] for c in p.get("categories", [])],
        "latitude": p.get("latitude"),
        "longitude": p.get("longitude"),
        "address": p["location"].get("formatted_address"),
        "city": p["location"].get("locality"),
        "region": p["location"].get("region"),
        "country": p["location"].get("country"),
        "telephone": p.get("tel"),
        "url": p.get("website"),
        "scraped_at": datetime.utcnow().isoformat()
    }

def load_existing_data(file_path: str) -> Dict[str, Dict]:
    """Loads existing data from a JSON file into a dictionary keyed by place_id."""
    if not os.path.exists(file_path):
        return {}
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            return {item["place_id"]: item for item in loaded if "place_id" in item}
    except json.JSONDecodeError:
        logger.error("Error decoding existing JSON, starting fresh.")
        return {}

def save_data(file_path: str, data: Dict[str, Dict]) -> None:
    """Saves the values of the data dictionary to a JSON file."""
    final_list = list(data.values())
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(final_list, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved {len(final_list)} total attractions (after dedup) to {file_path}")

def fetch_unique_places(target_count: int, max_retries: int = 5) -> List[Dict]:
    """
    Fetches a target number of unique places.
    Maintains its own 'seen' set to ensure uniqueness within the batch.
    """
    results: List[Dict] = []
    seen_ids: set = set()
    consecutive_failures = 0

    while len(results) < target_count:
        ll = get_random_coords()     
        try:
            data = search_attractions(ll=ll, radius=2000, limit=50)
            places = data.get("results", [])
            
            if not places:
                consecutive_failures += 1
                if consecutive_failures > max_retries:
                    logger.warning("Too many empty responses, stopping batch early.")
                    break
                continue
            
            consecutive_failures = 0
            
            for place in places:
                if len(results) >= target_count:
                    break
                
                pid = place.get("fsq_place_id")
                if pid and pid not in seen_ids:
                    results.append(normalize_place(place))
                    seen_ids.add(pid)
                    
        except Exception as e:
            logger.error(f"Error searching at {ll}: {e}")
            time.sleep(1)

    return results

def merge_data(existing: Dict[str, Dict], new_items: List[Dict]) -> Dict[str, Dict]:
    """
    Pure function to merge new items into existing data.
    Returns a new dictionary (or modifies copy) to be somewhat functional.
    """
    merged = existing.copy()
    for item in new_items:
        merged[item["place_id"]] = item
    return merged

def run_scraping_cycle(data_file: str, batch_size: int = 100) -> None:
    """Orchestrates one complete scraping cycle: Load -> Fetch -> Merge -> Save."""
    logger.info(f"[{datetime.now()}] Starting scrape job...")
    
    # 1. Load
    existing_data = load_existing_data(data_file)
    logger.info(f"Loaded {len(existing_data)} existing items.")
    
    # 2. Fetch
    new_attractions = fetch_unique_places(target_count=batch_size)
    logger.info(f"Scraped {len(new_attractions)} new unique items.")
    
    # 3. Merge
    updated_data = merge_data(existing_data, new_attractions)
    
    # 4. Save
    save_data(data_file, updated_data)

def main():
    DATA_FILE = os.getenv("FOURSQUARE_OUTPUT_FILE", "foursquare_ny_attractions.json")
    
    while True:
        try:
            run_scraping_cycle(DATA_FILE, batch_size=100)
        except Exception as e:
            logger.error(f"Critical error in scraping cycle: {e}")
        
        logger.info("Sleeping for 60 seconds...")
        time.sleep(60)

if __name__ == "__main__":
    main()
