import urllib.request
import json
import sys
import time

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

def make_request(url, data, retries=3):
    req = urllib.request.Request(
        url, 
        data=json.dumps(data).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            if attempt == retries - 1:
                print(f"HTTP Error: {e.code} - {e.read().decode()}")
                raise
            time.sleep(0.5)
        except Exception as e:
            if attempt == retries - 1:
                print(f"Error: {e}")
                raise
            time.sleep(0.5)

locations = [
    {
      "name": "Covent Garden Center",
      "description": "High commercial density area, ideal for testing high volume of results within a small radius.",
      "lat": 51.5130,
      "long": -0.1240
    },
    {
      "name": "Islington Center",
      "description": "Urban residential area, suitable for testing medium density and standard search radius.",
      "lat": 51.5350,
      "long": -0.1050
    },
    {
      "name": "Richmond Center",
      "description": "Spacious suburban area, perfect for testing expanded search radius and edge cases with fewer results.",
      "lat": 51.4613,
      "long": -0.3033
    }
]

categories_to_test = ["medical", "pharmacy", "grocery", "convenience", "police_emergency"]
test_hour = 14
all_output_writes = {}

for loc in locations:
    print(f"\n=========================================")
    print(f"Testing Region: {loc['name']}")
    print(f"=========================================")
    
    loc_results = {}
    for category in categories_to_test:
        print(f"\nTesting {category.upper()} utilities...")
        try:
            res = make_request("http://localhost:8000/utilities/closest", {
                "lat": loc["lat"],
                "lng": loc["long"],
                "location_id": 1,
                "parent_category": category,
                "limit": 3,
                "current_hour": test_hour
            })
            loc_results[f"{category}_test"] = res
            print(f"Found {category.title()} utilities:")
            for place in res:
                dist = place.get('distance')
                dist_str = f"{round(dist, 2)} km" if dist is not None else "Unknown"
                print(f"- {place.get('name')} (Categories: {place.get('categories')}, Hours: {place.get('hours')}, Distance: {dist_str})")
        except Exception as e:
            print(f"Failed testing {category}: {e}")
            sys.exit(1)

    # Add results to a dictionary pointing to file destinations, write them at the end.
    safe_name = loc['name'].lower().replace(' ', '_')
    output_file = f"utilities_test_output_{safe_name}.json"
    all_output_writes[output_file] = loc_results

for file_name, data in all_output_writes.items():
    with open(file_name, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\nSUCCESS! Region validation complete. Results saved to {file_name}")

