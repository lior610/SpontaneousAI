import urllib.request
import json
import sys

# Extracted directly from the PostgreSQL "users" and "trips" databases via psycopg2
test_cases = [
    {"user_id": 3, "trip_id": 2, "location_id": 1, "travel_style": "balanced", "max_walk_km": 3.00, "lat": 51.5237, "lng": -0.1585, "time": "2026-03-10T10:00:00.000Z"},
    {"user_id": 4, "trip_id": 3, "location_id": 1, "travel_style": "balanced", "max_walk_km": 4.00, "lat": 51.5237, "lng": -0.1585, "time": "2026-03-10T10:00:00.000Z"},
    {"user_id": 5, "trip_id": 4, "location_id": 1, "travel_style": "balanced", "max_walk_km": 2.00, "lat": 51.5237, "lng": -0.1585, "time": "2026-03-10T10:00:00.000Z"},
    {"user_id": 6, "trip_id": 5, "location_id": 1, "travel_style": "balanced", "max_walk_km": 1.50, "lat": 51.5136, "lng": -0.1365, "time": "2026-03-10T23:00:00.000Z"}, # Soho at 11:00 PM
]

def run_tests():
    print(f"=== Beginning Engine Batch Test For {len(test_cases)} Profiles ===\n")
    
    for case in test_cases:
        payload = {
            "user_id": case["user_id"],
            "trip_id": case["trip_id"],
            "location_id": case["location_id"],
            "current_location": {"lat": case["lat"], "lng": case["lng"]},
            "current_time": case["time"],
            "travel_style": case["travel_style"],
            "max_walk_km": case["max_walk_km"]
        }
        
        req = urllib.request.Request(
            'http://localhost:8000/recommendations/', 
            data=json.dumps(payload).encode('utf-8'), 
            headers={'Content-Type': 'application/json', 'Accept': 'application/json'}
        )
        
        print(f"[*] Testing User {case['user_id']} | Trip {case['trip_id']} | Max Walk: {case['max_walk_km']}km")
        try:
            response = urllib.request.urlopen(req)
            result = response.read().decode('utf-8')
            data = json.loads(result)
            
            print(f"    -> Engine Returned: {len(data)} Candidate Attractions")
            if data:
                top_hit = data[0]
                print(f"    -> Top Recommendation: {top_hit['attraction']['name']} (Final Score: {top_hit['score']})")
                print(f"    -> Top Hit Mathematics: {top_hit['reasoning']}")
            
            # Save output safely for inspection
            filename = f'api_response_test_user_{case["user_id"]}.json'
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            print(f"    -> Saved full payload to `{filename}`\n")
                
        except Exception as e:
            print(f"    -> ❌ Error executing recommendation fetch: {e}\n")
            if hasattr(e, 'read'):
                print(e.read().decode('utf-8'))

if __name__ == "__main__":
    run_tests()
