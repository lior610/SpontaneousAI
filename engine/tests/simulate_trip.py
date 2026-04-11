import urllib.request
import json
import sys
import os
import ast
from datetime import datetime, timedelta
import psycopg2
from dotenv import load_dotenv

load_dotenv()

host = os.getenv("POSTGRES_HOST")
port = os.getenv("POSTGRES_PORT")
user = os.getenv("POSTGRES_USER")
pwd = os.getenv("POSTGRES_PASSWORD")
db = os.getenv("POSTGRES_USERS_DB")

# Connect natively to PostgreSQL to handle test loop Teardown Operations
conn = psycopg2.connect(host=host, port=port, user=user, password=pwd, dbname=db)

test_cases = [
    # Standard morning configurations
    {"user_id": 3, "trip_id": 2, "location_id": 1, "travel_style": "balanced", "max_walk_km": 3.00, "lat": 51.5237, "lng": -0.1585, "time": "2026-03-10T10:00:00.000Z", "time_step_hours": 2.0, "name": "Standard Trip"},
    {"user_id": 4, "trip_id": 3, "location_id": 1, "travel_style": "balanced", "max_walk_km": 4.00, "lat": 51.5237, "lng": -0.1585, "time": "2026-03-10T10:00:00.000Z", "time_step_hours": 2.0, "name": "Standard Trip"},
    {"user_id": 5, "trip_id": 4, "location_id": 1, "travel_style": "balanced", "max_walk_km": 2.00, "lat": 51.5237, "lng": -0.1585, "time": "2026-03-10T10:00:00.000Z", "time_step_hours": 2.0, "name": "Standard Trip"},
    # Specialized Nightlife User configuration (Fast Bar-Hopping through Soho at midnight)
    {"user_id": 6, "trip_id": 5, "location_id": 1, "travel_style": "balanced", "max_walk_km": 1.50, "lat": 51.5136, "lng": -0.1365, "time": "2026-03-10T23:00:00.000Z", "time_step_hours": 1.5, "name": "Nightlife Bar-Hopper"}, 
]

def parse_time(t_str):
    return datetime.strptime(t_str, "%Y-%m-%dT%H:%M:%S.%fZ")

def format_time(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")

def teardown_database_state(trip_id):
    """Purges the Feedback and Preferences databases to restore 100% Day 1 Baseline"""
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM trip_feedback WHERE trip_id = %s;", (trip_id,))
        cur.execute("DELETE FROM user_preference_embeddings WHERE trip_id = %s;", (trip_id,))
        conn.commit()
        cur.close()
        print(f"    [Teardown] Trip {trip_id} perfectly restored to Database Baseline.\n")
    except Exception as e:
        print(f"    [Teardown] Error restoring baseline for Trip {trip_id}: {e}")
        conn.rollback()

def fetch_recommendations(case, current_lat, current_lng, current_time):
    """Hits the vector similarity engine and returns ranked candidates."""
    payload = {
        "user_id": case["user_id"],
        "trip_id": case["trip_id"],
        "current_location": {"lat": current_lat, "lng": current_lng},
        "current_time": current_time
    }
    
    req = urllib.request.Request(
        'http://localhost:8000/recommendations/', 
        data=json.dumps(payload).encode('utf-8'), 
        headers={'Content-Type': 'application/json', 'Accept': 'application/json'}
    )
    
    response = urllib.request.urlopen(req)
    return json.loads(response.read().decode('utf-8'))

def send_feedback(user_id, trip_id, place_id, action="liked"):
    """Fires a feedback action to trigger EMA vector warping."""
    payload = {
        "user_id": user_id,
        "trip_id": trip_id,
        "place_id": place_id,
        "action": action
    }
    
    req = urllib.request.Request(
        'http://localhost:8000/recommendations/feedback', 
        data=json.dumps(payload).encode('utf-8'), 
        headers={'Content-Type': 'application/json', 'Accept': 'application/json'}
    )
    
    urllib.request.urlopen(req)

def run_simulation(hops=3):
    print(f"=== Beginning Dynamic {hops}-Hop Feedback Loop Simulation ===\n")
    
    for case in test_cases:
        print(f"[*] Initializing Simulation for User {case['user_id']} | Scenario: {case['name']}")
        current_lat = case["lat"]
        current_lng = case["lng"]
        current_time = case["time"]
        seen_places = set()
        
        # Track deep analytical history
        simulation_log = {
            "metadata": {
                "user_id": case["user_id"],
                "trip_id": case["trip_id"],
                "scenario": case["name"],
                "start_time": case["time"],
                "start_location": {"lat": current_lat, "lng": current_lng},
                "travel_style": case["travel_style"],
                "max_walk_km": case["max_walk_km"],
                "simulated_hops": hops
            },
            "hops": []
        }

        for hop in range(1, hops + 1):
            print(f"  [Hop {hop}] Time: {current_time} | Loc: {round(current_lat, 4)}, {round(current_lng, 4)}")
            try:
                # 1. Fetch
                candidates = fetch_recommendations(case, current_lat, current_lng, current_time)
                if not candidates:
                    print(f"    -> No candidates returned! Geography might be too constrained.")
                    break
                
                # 2. Select Top Valid Hit
                top_hit = candidates[0]
                place_id = top_hit['attraction']['place_id']
                name = top_hit['attraction']['name']
                category = top_hit['attraction']['categories'][0] if isinstance(top_hit['attraction']['categories'], list) and top_hit['attraction']['categories'] else (str(top_hit['attraction']['categories']).split(',')[0] if top_hit['attraction']['categories'] else "Unknown")
                new_lat = top_hit['attraction']['latitude']
                new_lng = top_hit['attraction']['longitude']
                
                # 3. Duplicate Guarantee Analysis
                if place_id in seen_places:
                    print(f"    -> [!] CRITICAL FAILURE: Engine recommended '{name}' twice!")
                    break
                seen_places.add(place_id)
                
                # Extract Top 3 Pool competitors to observe AI shifts
                top_competitors = []
                for idx, c in enumerate(candidates[:3]):
                    math_str = c.get('reasoning', '{}')
                    try:
                        math_dict = ast.literal_eval(math_str) if math_str and math_str != 'None' else {}
                    except:
                        math_dict = {}
                        
                    top_competitors.append({
                        "rank": idx + 1,
                        "name": c['attraction']['name'],
                        "category": c['attraction']['categories'],
                        "cluster_id": c['attraction'].get('location_cluster_id'),
                        "distance_km": round(c.get('distance_km', 0), 2),
                        "final_score": c.get('score', 0),
                        "mathematics": math_dict
                    })
                
                top_math_str = top_hit.get('reasoning', '{}')
                try:
                    top_math_dict = ast.literal_eval(top_math_str) if top_math_str and top_math_str != 'None' else {}
                except:
                    top_math_dict = {}
                
                distance_km = top_hit.get('distance_km', 0)
                print(f"    -> Engine Recommended: {name} ({category}) | Dist: {round(distance_km, 2)}km | Score: {top_hit.get('score', top_hit.get('final_score'))}")
                print(f"    -> User 'likes' {name}. Truncating vector towards {category}...")
                
                # Log Hop details mathematically
                simulation_log["hops"].append({
                    "hop_number": hop,
                    "state_before_action": {
                        "time": current_time,
                        "location": {"lat": current_lat, "lng": current_lng}
                    },
                    "action_taken": {
                        "type": "liked",
                        "attraction_name": name,
                        "place_id": place_id,
                        "category": category,
                        "cluster_id": top_hit['attraction'].get('location_cluster_id'),
                        "distance_km": round(distance_km, 2),
                        "semantic_affinity": top_math_dict.get('semantic', "N/A"),
                        "distance_penalty": top_math_dict.get('distance', "N/A")
                    },
                    "candidate_pool_shift": top_competitors
                })
                
                # 4. Trigger Feedback & EMA Recalculation
                send_feedback(case['user_id'], case['trip_id'], place_id, "liked")
                
                # 5. Move Physical Loc / Time To The Attraction
                current_lat = new_lat
                current_lng = new_lng
                
                dt = parse_time(current_time)
                dt += timedelta(hours=case["time_step_hours"])
                current_time = format_time(dt)
                
            except Exception as e:
                print(f"    -> [!] HTTP Error during sequence: {e}")
                if hasattr(e, 'read'):
                    print(e.read().decode('utf-8'))
                break
        
        # 6. Safety Teardown Validation
        teardown_database_state(case['trip_id'])
        
        # 7. Dump Deep Analysis JSON
        file_name = f"simulation_user_{case['user_id']}_analytics.json"
        with open(file_name, 'w') as f:
            json.dump(simulation_log, f, indent=4)
        print(f"    [Analytics] Detailed logs dumped to {file_name}\n")

if __name__ == "__main__":
    run_simulation(hops=3)
