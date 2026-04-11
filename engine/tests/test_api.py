import urllib.request
import json

payload = {
  "user_id": 1,
  "trip_id": 1,
  "location_id": 1,
  "current_location": {"lat": 51.5237, "lng": -0.1585},
  "current_time": "2026-03-10T10:04:04.396Z",
  "travel_style": "balanced",
  "max_walk_km": 2.0
}

req = urllib.request.Request(
    'http://localhost:8000/recommendations/', 
    data=json.dumps(payload).encode('utf-8'), 
    headers={'Content-Type': 'application/json', 'Accept': 'application/json'}
)

try:
    response = urllib.request.urlopen(req)
    result = response.read().decode('utf-8')
    with open('api_response_test.json', 'w', encoding='utf-8') as f:
        f.write(result)
    print("Success! Output written to api_response_test.json")
except Exception as e:
    print(f"Error: {e}")
    if hasattr(e, 'read'):
        result = e.read().decode('utf-8')
        with open('api_response_test.json', 'w', encoding='utf-8') as f:
            f.write(result)
        print("Error content written to api_response_test.json")
