import os
import json
import requests
from datetime import datetime
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

FOURSQUARE_API_KEY = os.getenv("FOURSQUARE_API_KEY")

BASE_URL = "https://api.foursquare.com/v3/places/search"

HEADERS = {
    "Accept": "application/json",
    "Authorization": FOURSQUARE_API_KEY
}


def search_attractions(near: str, limit: int = 50, cursor: str = None) -> Dict:
    params = {
        "query": "tourist attraction",
        "near": near,
        "limit": limit,
        "categories": "16000"
    }

    if cursor:
        params["cursor"] = cursor

    response = requests.get(BASE_URL, headers=HEADERS, params=params)
    response.raise_for_status()

    return response.json()


def normalize_place(p: Dict) -> Dict:
    return {
        "source": "foursquare",
        "place_id": p["fsq_id"],
        "name": p["name"],
        "categories": [c["name"] for c in p.get("categories", [])],
        "latitude": p["geocodes"]["main"]["latitude"],
        "longitude": p["geocodes"]["main"]["longitude"],
        "address": p["location"].get("formatted_address"),
        "city": p["location"].get("locality"),
        "region": p["location"].get("region"),
        "country": p["location"].get("country"),
        "rating": p.get("rating"),
        "popularity": p.get("popularity"),
        "url": p.get("website"),
        "scraped_at": datetime.utcnow().isoformat()
    }


def extract_top_attractions_new_york(max_results: int = 100) -> List[Dict]:
    results = []
    cursor = None

    while len(results) < max_results:
        data = search_attractions(
            near="New York, NY",
            limit=50,
            cursor=cursor
        )

        places = data.get("results", [])
        if not places:
            break

        for place in places:
            if len(results) >= max_results:
                break
            results.append(normalize_place(place))

        cursor = data.get("context", {}).get("next_cursor")
        if not cursor:
            break

    return results


if __name__ == "__main__":
    data = extract_top_attractions_new_york()

    with open("foursquare_ny_attractions.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Saved {len(data)} attractions")
