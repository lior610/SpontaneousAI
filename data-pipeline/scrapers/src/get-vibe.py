import google.generativeai as genai
import time
import json
import os
import sys
import random
import dotenv
import logging
from pathlib import Path
from collections import Counter
from google.api_core.exceptions import TooManyRequests

# Load environment variables
BASE_DIR = Path(__file__).resolve().parents[1]
dotenv.load_dotenv(BASE_DIR / ".env")

# --- Configuration ---
BATCH_SIZE_ATTRACTIONS = int(os.getenv("BATCH_SIZE_ATTRACTIONS", 20))    
BATCH_SIZE_CHAINS      = int(os.getenv("BATCH_SIZE_CHAINS", 5))            # Smaller batch for chains because output is larger (3 vars)
THRESHOLD_BIG_CHAIN    = int(os.getenv("THRESHOLD_BIG_CHAIN", 5))          # 5 or more -> 3 variations
THRESHOLD_SMALL_CHAIN  = int(os.getenv("THRESHOLD_SMALL_CHAIN", 2))        # 2 to 4 -> 1 variation
WAIT_SECONDS           = int(os.getenv("WAIT_SECONDS", 2))                 # Wait between requests

# --- File Paths ---
CITY                   = os.getenv("CITY", "london").strip().lower()
DATA_DIR               = BASE_DIR / "data" / CITY
CACHE_DIR              = BASE_DIR / "cache" / CITY
CHAIN_CACHE_FILE       = os.getenv("CHAIN_CACHE_FILE", str(CACHE_DIR / "chain_cache.json"))
ATTRACTION_CACHE_FILE  = os.getenv("ATTRACTION_CACHE_FILE", str(CACHE_DIR / "attraction_cache.json"))
INPUT_FILE             = os.getenv("PLACES_JSON", str(DATA_DIR / "filtered_places.json"))
OUTPUT_FILE            = os.getenv("OUTPUT_JSON", str(DATA_DIR / "places_enriched.json"))

# --- Gemini Configuration ---
generation_config = {
    "max_output_tokens": 8192, # High limit needed for multi-variation JSONs
    "temperature": 0.7,        
    "top_p": 0.9,
    "response_mime_type": "application/json"
}

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(BASE_DIR / 'enrichment_process.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Gemini Setup
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel(os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
                              generation_config=generation_config)

# --- Helper Functions ---

def is_attraction(place):
    return 'type' in place and place['type'] == 'attraction'

def clean_json_string(json_str):
    return json_str.replace('```json', '').replace('```', '').strip()

def get_utility_data(name):
    """Generates data for utilities (30% chance of 24/7)."""
    if random.random() < 0.30:
        hours = "00:00-23:59"
    else:
        opens = random.choice(["07:00", "08:00", "09:00"])
        closes = random.choice(["18:00", "19:00", "20:00", "21:00"])
        hours = f"{opens}-{closes}"
    
    return {
        "budget": "0",
        "hours": hours,
        "desc": f"{name} is a functional utility location providing standard services."
    }

# --- Cache Management ---

def load_cache(cache_file):
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return {}
    return {}

def save_cache(cache_data, cache_file):
    try:
        Path(cache_file).parent.mkdir(parents=True, exist_ok=True)
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save backup: {e}")

# --- Prompts ---

def generate_big_chain_prompt(chains_list):
    """
    For chains with >= 5 locations.
    Demands 3 variations per chain.
    """
    return f"""
    Task: Create diverse profiles for large chain businesses.
    Input: List of chain names, categories and city.
    
    Instructions for each chain:
    1. Generate **3 DIFFERENT variations** of the venue.
    2. **Budget:** Must be the SAME for all 3 variations (it's the same chain).  Estimate based on vibe (In dollars). Integer string.
    3. **Hours:** Must be DIFFERENT for each variation but in the same fields.
    4. **desc:** Single English sentence combining atmosphere, crowd, and critical reputation (Be Honest and avoid marketing fluff) for vector embedding. each variation must differ.
    
    Output Format:
    [
      {{
        "name": "Chain Name",
        "variations": [
           {{"budget": "20", "hours": "07:00-20:00", "desc": "Quiet morning spot..."}},
           {{"budget": "20", "hours": "08:00-23:00", "desc": "Bustling central location..."}},
           {{"budget": "20", "hours": "06:00-22:00", "desc": "Highway stop vibe..."}}
        ]
      }}
    ]
    
    Input List:
    {json.dumps(chains_list)}
    """

def generate_small_chain_prompt(chains_list):
    """
    For chains with 2-4 locations.
    Demands 1 single profile.
    """
    return f"""
    Task: Create a standard profile for chain businesses.
    Input: List of names, categories and city.
    
    Instructions:
    1. Provide ONE set of details (Budget, Hours, Vibe) that fits this chain.
    2. **Budget:** Must be the SAME for all 3 variations (it's the same chain).  Estimate based on vibe (In dollars). Integer string.
    3. **Hours:** Must be DIFFERENT for each variation but in the same fields.
    4. **desc**: Single English sentence combining atmosphere, crowd, and critical reputation (Be Honest and avoid marketing fluff) for vector embedding.
    Output Format:
    [
      {{
        "name": "Chain Name",
        "variations": [
           {{"budget": "...", "hours": "...", "desc": "..."}}
        ]
      }}
    ]
    
    Input List:
    {json.dumps(chains_list)}
    """

def generate_attraction_prompt(batch_places):
    lean_data = [{"placeID": p["place_id"], "name": p["name"], 
                  "categories": p.get("categories"), "city": p.get("region", "Unknown City")} 
                 for p in batch_places]
    return f"""
    Task: Enrich venue data into a JSON List.
    Fields per venue:
    1. "placeID": String.
    2. "budget": Average money spent on this place. Estimate based on vibe (In dollars). Integer string.
    3. "hours": "HH:MM-HH:MM". Estimate typical operating window based on category.
    4. "desc": Single English sentence combining atmosphere, crowd, and critical reputation (Be Honest and avoid marketing fluff) for vector embedding.
    Input List: {json.dumps(lean_data)}
    """

# --- Main Logic ---

def process_chains_step(all_places):
    # 1. Analyze Counts
    place_info = {} 
    for p in all_places:
        name = p.get("name")
        if not name or p.get("type") != "attraction": 
            continue
        if name not in place_info: 
            place_info[name] = {"count": 0, "cats": [], "regions": []}
        place_info[name]["count"] += 1
        if p.get("categories"): 
            place_info[name]["cats"].extend(p["categories"])
        # collect region/city for chain grouping
        place_info[name]["regions"].append(p.get("region", "Unknown City"))

    # 2. Split into Lists
    big_chains = []   # Count >= 5
    small_chains = [] # 2 <= Count < 5
    
    for name, data in place_info.items():
        count = data["count"]
        if count >= THRESHOLD_SMALL_CHAIN:
            cat = Counter(data["cats"]).most_common(1)[0][0] if data["cats"] else "General"
            city = Counter(data["regions"]).most_common(1)[0][0] if data["regions"] else "Unknown City"
            obj = {"name": name, "category": cat, "city": city}
            
            if count >= THRESHOLD_BIG_CHAIN:
                big_chains.append(obj)
            else:
                small_chains.append(obj)

    logger.info(f"Chains Found: {len(big_chains)} Big (>=5), {len(small_chains)} Small (2-4).")
    
    # Calculate and log batch counts
    big_chain_batches = (len(big_chains) + BATCH_SIZE_CHAINS - 1) // BATCH_SIZE_CHAINS  # Ceiling division
    small_chain_batches = (len(small_chains) + (BATCH_SIZE_CHAINS * 2) - 1) // (BATCH_SIZE_CHAINS * 2)
    
    logger.info(f"Big chains will be processed in {big_chain_batches} batch(es) (batch size: {BATCH_SIZE_CHAINS})")
    logger.info(f"Small chains will be processed in {small_chain_batches} batch(es) (batch size: {BATCH_SIZE_CHAINS * 2})")

    # 3. Process Loops
    chain_cache = load_cache(CHAIN_CACHE_FILE)
    
    # --- Helper to process a list ---
    def run_chain_batch(target_list, prompt_func, batch_size):
        buffer = []
        for item in target_list:
            if item["name"] in chain_cache: continue
            
            buffer.append(item)
            if len(buffer) >= batch_size:
                try:
                    logger.info(f"Processing chain batch ({len(buffer)})...")
                    prompt = prompt_func(buffer)
                    response = model.generate_content(prompt)
                    results = json.loads(clean_json_string(response.text))
                    
                    for res in results:
                        # Save in cache as Name -> List of Variations
                        chain_cache[res["name"]] = res["variations"]
                    
                    save_cache(chain_cache, CHAIN_CACHE_FILE)
                    time.sleep(WAIT_SECONDS)
                except TooManyRequests as e:
                    logger.error(f"Rate limit hit (429): {e}")
                    sys.exit(1)
                except Exception as e:
                    logger.error(f"Chain batch failed: {e}")
                buffer = []
        
        # Leftovers
        if buffer:
            try:
                prompt = prompt_func(buffer)
                res = json.loads(clean_json_string(model.generate_content(prompt).text))
                for r in res: 
                    chain_cache[r["name"]] = r["variations"]
                save_cache(chain_cache, CHAIN_CACHE_FILE)
            except TooManyRequests as e:
                logger.error(f"Rate limit hit (429): {e}")
                sys.exit(1)
            except Exception as e: logger.error(f"Final chain batch failed: {e}")

    # Run Big Chains (Prompt asks for 3 vars)
    if big_chains:
        logger.info("Processing Big Chains...")
        run_chain_batch(big_chains, generate_big_chain_prompt, BATCH_SIZE_CHAINS)

    # Run Small Chains (Prompt asks for 1 var)
    if small_chains:
        logger.info("Processing Small Chains...")
        run_chain_batch(small_chains, generate_small_chain_prompt, BATCH_SIZE_CHAINS * 2)

    return chain_cache

def main():
    logger.info(f"City: {CITY}")
    logger.info(f"Input file: {INPUT_FILE}")
    logger.info(f"Output file: {OUTPUT_FILE}")
    logger.info(f"Chain cache file: {CHAIN_CACHE_FILE}")
    logger.info(f"Attraction cache file: {ATTRACTION_CACHE_FILE}")

    if not os.path.exists(INPUT_FILE):
        logger.error(f"Input file not found: {INPUT_FILE}")
        sys.exit(1)

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        all_places = json.load(f)

    # Phase 1: Chain Logic (Big vs Small)
    chain_cache = process_chains_step(all_places)
    attraction_cache = load_cache(ATTRACTION_CACHE_FILE)

    # Phase 2: Assign Data
    final_data = []
    unique_attractions = []

    logger.info("Assigning data to places...")
    
    for place in all_places:
        name = place.get("name")
        place_id = place.get("place_id")
        
        # A. IS IT A CHAIN? (In Chain Cache)
        if name in chain_cache:
            variations = chain_cache[name]
            chosen_var = random.choice(variations)
            
            place["budget"] = chosen_var.get("budget")
            place["hours"] = chosen_var.get("hours")
            place["embedding_desc"] = chosen_var.get("desc")
            final_data.append(place)

        # B. IS IT AN ATTRACTION IN CACHE?
        elif is_attraction(place) and place_id in attraction_cache:
            cached_data = attraction_cache[place_id]
            place["budget"] = cached_data.get("budget")
            place["hours"] = cached_data.get("hours")
            place["embedding_desc"] = cached_data.get("desc")
            final_data.append(place)

        # C. IS IT A UTILITY?
        elif not is_attraction(place):
            util_info = get_utility_data(name)
            place["budget"] = util_info["budget"]
            place["hours"] = util_info["hours"]
            place["embedding_desc"] = util_info["desc"]
            final_data.append(place)
            
        # D. UNIQUE ATTRACTION TO BE PROCESSED
        else:
            unique_attractions.append(place)

    # Phase 3: Unique Attractions Batching
    attraction_batches = (len(unique_attractions) + BATCH_SIZE_ATTRACTIONS - 1) // BATCH_SIZE_ATTRACTIONS
    logger.info(f"Processing {len(unique_attractions)} unique attractions in {attraction_batches} batch(es) (batch size: {BATCH_SIZE_ATTRACTIONS})...")
    
    for i in range(0, len(unique_attractions), BATCH_SIZE_ATTRACTIONS):
        batch = unique_attractions[i : i + BATCH_SIZE_ATTRACTIONS]
        
        # Filter out attractions that are already in the cache (should not happen with current logic, but good practice)
        batch_to_process = [p for p in batch if p["place_id"] not in attraction_cache]

        if not batch_to_process:
            # If all items in batch were somehow already cached, just add them and continue
            for p in batch:
                if p["place_id"] in attraction_cache:
                    cached_data = attraction_cache[p["place_id"]]
                    p["budget"] = cached_data.get("budget")
                    p["hours"] = cached_data.get("hours")
                    p["embedding_desc"] = cached_data.get("desc")
                final_data.append(p)
            continue

        try:
            logger.info(f"Processing batch of {len(batch_to_process)} attractions...")
            prompt = generate_attraction_prompt(batch_to_process)
            response = model.generate_content(prompt)
            results = json.loads(clean_json_string(response.text))
            
            res_map = {r["placeID"]: r for r in results if "placeID" in r}
            
            for p in batch: # Iterate through original batch to maintain order
                if p["place_id"] in res_map:
                    data = res_map[p["place_id"]]
                    p["budget"] = data.get("budget")
                    p["hours"] = data.get("hours")
                    p["embedding_desc"] = data.get("desc")
                    
                    # Add to cache
                    attraction_cache[p["place_id"]] = {
                        "budget": data.get("budget"),
                        "hours": data.get("hours"),
                        "desc": data.get("desc")
                    }
                final_data.append(p)

            save_cache(attraction_cache, ATTRACTION_CACHE_FILE)
            time.sleep(WAIT_SECONDS)

        except TooManyRequests as e:
            logger.error(f"Rate limit hit (429): {e}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Error processing attraction batch: {e}")
            
    # Save final enriched data
    Path(OUTPUT_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, indent=2, ensure_ascii=False)
    logger.info("Done.")

if __name__ == "__main__":
    main()