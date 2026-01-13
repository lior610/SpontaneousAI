import pandas as pd
import numpy as np
from faker import Faker
import random
import time
import sys
import asyncio
from datetime import datetime
from pathlib import Path

# Import shared database connection modules
shared_path = str(Path(__file__).resolve().parents[2] / "shared" / "python")
if shared_path not in sys.path:
    sys.path.insert(0, shared_path)
from db.attractionsConnection import get_db_connection as get_attractions_connection
from db.usersConnection import get_db_connection as get_users_connection

# Import embedding service
engine_path = str(Path(__file__).resolve().parents[2] / "engine" / "src")
if engine_path not in sys.path:
    sys.path.insert(0, engine_path)
from services.embedding_service import generate_embeddings_batch, get_embedding_dimension

# --- CONFIGURATION ---
NUM_ATTRACTIONS = 500
NUM_USERS = 1
NUM_TRIPS =1 # 1 trip per user

fake = Faker()

# --- HELPER LISTS ---
countries = ['USA', 'Israel', 'Germany', 'Japan', 'France', 'UK', 'Greece', 'Spain']
# Map cities to their correct countries for consistency
city_country_map = {
    'New York': 'USA',
    'Arizona': 'USA',
    'London': 'UK',
    'Paris': 'France',
    'Berlin': 'Germany',
    'Athens': 'Greece',
    'Tokyo': 'Japan',
    'Tel Aviv': 'Israel',
    'Barcelona': 'Spain',
}
cities = list(city_country_map.keys())
age_groups = ['teen', '20s', '30s', '40+']
travel_styles = ['budget', 'balanced', 'premium']
paces = ['slow', 'normal', 'fast']
intensities = ['low', 'medium', 'high']
diets = ['none', 'veg', 'vegan', 'kosher']
vibes = ['chill', 'social', 'adventure', 'romantic', 'quiet', 'educational']
good_for_options = ['solo', 'couple', 'friends', 'kids']
sources = ['google_maps', 'tripadvisor', 'yelp']
# --- 1. GENERATE USERS (FULL SCHEMA) ---
async def generate_users_dataset(n):
    print(f"Generating {n} users (Full Schema)...")
    users = []
    user_texts = []
    
    # First pass: collect all user data and texts for embedding
    for _ in range(n):
        uid = fake.uuid4()
        
        # Interest Preferences (0.0 - 1.0)
        prefs = {
            "pref_movies": round(random.random(), 2),
            "pref_food": round(random.random(), 2),
            "pref_nature": round(random.random(), 2),
            "pref_museums": round(random.random(), 2),
            "pref_shopping": round(random.random(), 2),
            "pref_nightlife": round(random.random(), 2),
            "pref_adventure": round(random.random(), 2),
            "pref_relaxation": round(random.random(), 2),
            "pref_sports": round(random.random(), 2),
            "pref_music_events": round(random.random(), 2),
        }

        # Build User Vector (Top 3 interests)
        top_interests = sorted(prefs, key=prefs.get, reverse=True)[:3]
        clean_interests = [k.replace('pref_', '') for k in top_interests]
        user_desc_text = f"I am a traveler who loves {', '.join(clean_interests)}."
        
        created = fake.date_time_this_year()
        record = {
            "user_id": uid,
            "created_at": created,
            "updated_at": created,  # Initially same as created_at
            "home_country": random.choice(countries) if random.random() > 0.2 else None,
            "age_group": random.choice(age_groups),
            "travel_style": random.choice(travel_styles),
            "pace_preference": random.choice(paces),
            "crowd_tolerance": random.choice(intensities),
            "activity_intensity_preference": random.choice(intensities),
            "night_owl": fake.boolean(),
            **prefs,
            "dietary_style": random.choice(diets),
            "accessibility_needs": fake.boolean(chance_of_getting_true=10),
            "with_kids": fake.boolean(chance_of_getting_true=20),
            "tiredness_level": round(random.random(), 2),
            "hunger_level": round(random.random(), 2),
            "energy_level": round(random.random(), 2) if random.random() > 0.1 else None,
            "preference_vector": None  # Will be filled after batch embedding
        }
        users.append(record)
        user_texts.append(user_desc_text)
    
    # Batch generate all embeddings at once
    user_vectors = await generate_embeddings_batch(user_texts)
    
    # Assign embeddings back to records
    for i, user_vector in enumerate(user_vectors):
        users[i]["preference_vector"] = user_vector
        
    return pd.DataFrame(users)

# --- 2. GENERATE TRIPS (DYNAMIC CONTEXT) ---
def generate_trips_dataset(users_df):
    print(f"Generating trips for {len(users_df)} users...")
    trips = []
    
    cities_map = {
        'New York': {'lat': 40.71, 'lng': -74.00, 'tz': 'EST'},
        'London': {'lat': 51.50, 'lng': -0.12, 'tz': 'GMT'},
        'Tel Aviv': {'lat': 32.08, 'lng': 34.78, 'tz': 'IST'},
        'Tokyo': {'lat': 35.67, 'lng': 139.65, 'tz': 'JST'}
    }
    
    for index, user in users_df.iterrows():
        city_name = random.choice(list(cities_map.keys()))
        city_data = cities_map[city_name]
        
        # Budget Logic
        budget = random.randint(500, 1500) if user['travel_style'] == 'budget' else random.randint(2000, 5000)

        record = {
            "trip_id": fake.uuid4(),
            "user_id": user['user_id'],
            "destination": city_name,
            "dates": fake.date_this_year(),
            "budget": budget,
            "current_lat": city_data['lat'] + random.uniform(-0.05, 0.05),
            "current_lng": city_data['lng'] + random.uniform(-0.05, 0.05),
            "current_city": city_name,
            "timezone": city_data['tz'],
            "local_hour_last_seen": random.randint(8, 23),
            "day_of_week_last_seen": random.randint(0, 6),
            "desired_vibe": random.choice(vibes),
            "desired_indoor": random.choice([True, False, None]),
            "max_travel_time_min": random.choice([15, 30, 45, 60]),
            "avoid_category_1": random.choice(['Nightlife', 'Museum', 'Shopping', None]),
            "avoid_category_2": random.choice(['Bar', 'Hiking', None]) if random.random() > 0.7 else None,
            "avoid_category_3": random.choice(['Restaurant', 'Cafe', None]) if random.random() > 0.9 else None
        }
        trips.append(record)
        
    return pd.DataFrame(trips)

# --- UNIQUE DESCRIPTION GENERATOR ---
def generate_unique_description(category, tags, vibe, good_for):
    """Generate detailed, unique descriptions for each attraction category"""
    
    # Convert lists to strings once
    tags_str = ', '.join(tags)
    good_for_str = ', '.join(good_for)
    
    # Category-specific description templates
    templates = {
        'Museum': [
            f"Explore fascinating exhibits featuring {random.choice(['ancient artifacts', 'modern art', 'historical documents', 'interactive displays', 'rare collections', 'cultural treasures'])}. "
            f"{random.choice(['Guided tours available', 'Self-guided audio tours', 'Expert curators on site', 'Educational programs offered'])}. "
            f"Perfect for {good_for_str} seeking {tags_str} experience.",
            
            f"Discover {random.choice(['world-class exhibitions', 'rotating collections', 'permanent galleries', 'multimedia presentations'])} "
            f"showcasing {random.choice(['science and technology', 'natural history', 'contemporary art', 'local heritage', 'world cultures'])}. "
            f"Great for {good_for_str} looking for {vibe} atmosphere.",
        ],
        'Park': [
            f"Beautiful {random.choice(['urban park', 'botanical garden', 'nature reserve', 'public square', 'green space'])} featuring "
            f"{random.choice(['walking trails', 'playgrounds', 'picnic areas', 'scenic viewpoints', 'water features', 'sports facilities'])}. "
            f"Ideal for {good_for_str} wanting {tags_str} outdoor activities.",
            
            f"Spacious {random.choice(['recreational area', 'community park', 'wildlife sanctuary', 'garden oasis'])} with "
            f"{random.choice(['mature trees', 'flower gardens', 'open lawns', 'pond views', 'running paths', 'bike trails'])}. "
            f"Perfect spot for {vibe} time with {good_for_str}.",
        ],
        'Restaurant': [
            f"Authentic {random.choice(['Italian', 'Japanese', 'Mexican', 'French', 'Thai', 'Mediterranean', 'Indian', 'Chinese'])} cuisine featuring "
            f"{random.choice(['farm-to-table ingredients', 'chef specials', 'traditional recipes', 'fusion dishes', 'seasonal menu', 'signature cocktails'])}. "
            f"{random.choice(['Cozy ambiance', 'Modern decor', 'Family-friendly', 'Upscale dining', 'Casual atmosphere'])}. Great for {good_for_str}.",
            
            f"Popular {random.choice(['bistro', 'eatery', 'dining spot', 'gourmet restaurant', 'local favorite'])} serving "
            f"{random.choice(['fresh seafood', 'grilled meats', 'vegetarian options', 'artisan pizzas', 'homemade pasta', 'tapas'])}. "
            f"Known for {vibe} atmosphere, perfect for {good_for_str}.",
        ],
        'Cafe': [
            f"Charming {random.choice(['coffee shop', 'espresso bar', 'tea house', 'bakery cafe', 'artisan cafe'])} offering "
            f"{random.choice(['specialty coffee', 'fresh pastries', 'homemade desserts', 'light meals', 'organic teas', 'breakfast items'])}. "
            f"{random.choice(['Free WiFi available', 'Outdoor seating', 'Cozy indoor space', 'Local art displayed'])}. Perfect for {tags_str} vibes.",
            
            f"Trendy {random.choice(['coffee house', 'brunch spot', 'patisserie', 'sandwich shop'])} with "
            f"{random.choice(['craft beverages', 'vegan options', 'gluten-free menu', 'fresh smoothies', 'gourmet sandwiches'])}. "
            f"Welcoming atmosphere for {good_for_str} seeking {vibe} experience.",
        ],
        'Bar': [
            f"{random.choice(['Sophisticated', 'Lively', 'Intimate', 'Rooftop', 'Underground', 'Historic'])} bar featuring "
            f"{random.choice(['craft cocktails', 'local beers', 'wine selection', 'live music', 'DJ sets', 'happy hour specials'])}. "
            f"{random.choice(['Late night hours', 'Weekend entertainment', 'Games available', 'Outdoor terrace'])}. Great for {good_for_str}.",
            
            f"Popular {random.choice(['pub', 'cocktail lounge', 'sports bar', 'wine bar', 'taproom'])} known for "
            f"{random.choice(['signature drinks', 'bar snacks', 'social atmosphere', 'craft selections', 'themed nights'])}. "
            f"Perfect for {vibe} evenings with {good_for_str}.",
        ],
        'Historical': [
            f"Remarkable {random.choice(['historical landmark', 'heritage site', 'ancient monument', 'cultural site', 'preserved structure'])} dating back to "
            f"{random.choice(['medieval times', 'the Renaissance', 'ancient civilizations', 'colonial era', '19th century', 'early 20th century'])}. "
            f"Features {random.choice(['guided tours', 'informational plaques', 'museum exhibits', 'restoration work', 'archaeological findings'])}. Fascinating for {good_for_str}.",
            
            f"Impressive {random.choice(['ruins', 'fortress', 'palace', 'temple', 'cathedral', 'memorial', 'historic district'])} showcasing "
            f"{random.choice(['architectural beauty', 'historical significance', 'cultural importance', 'artistic details', 'engineering marvels'])}. "
            f"Offers {vibe} experience for those interested in {tags_str} exploration.",
        ],
        'Shopping': [
            f"{random.choice(['Bustling', 'Upscale', 'Local', 'Modern', 'Traditional', 'Artisan'])} shopping area featuring "
            f"{random.choice(['boutique stores', 'international brands', 'local crafts', 'designer outlets', 'specialty shops', 'souvenir stands'])}. "
            f"Great for {good_for_str} looking for {tags_str} shopping experience.",
            
            f"{random.choice(['Shopping district', 'Market', 'Mall', 'Shopping center', 'Bazaar', 'Arcade'])} offering "
            f"{random.choice(['unique finds', 'bargain deals', 'luxury goods', 'handmade items', 'local products', 'fashion trends'])}. "
            f"Perfect for {vibe} atmosphere and {good_for_str}.",
        ],
        'Hiking': [
            f"Scenic {random.choice(['hiking trail', 'mountain path', 'forest walk', 'coastal route', 'nature trail'])} with "
            f"{random.choice(['panoramic views', 'waterfall viewpoints', 'wildlife spotting', 'elevation gain', 'challenging terrain', 'gentle slopes'])}. "
            f"{random.choice(['Well-marked trail', 'Moderate difficulty', 'Suitable for beginners', 'Advanced level', 'Family-friendly path'])}. Great for {good_for_str}.",
            
            f"Beautiful {random.choice(['trekking route', 'backcountry trail', 'summit hike', 'ridge walk', 'valley path'])} featuring "
            f"{random.choice(['stunning vistas', 'natural formations', 'diverse ecosystems', 'peaceful surroundings', 'adventure opportunities'])}. "
            f"Ideal for {tags_str} outdoor experience with {good_for_str}.",
        ],
        'Cinema': [
            f"{random.choice(['Modern', 'Historic', 'Art-house', 'Multiplex', 'Independent', 'Luxury'])} cinema showing "
            f"{random.choice(['latest blockbusters', 'indie films', 'foreign cinema', 'classic movies', 'documentaries', '3D features'])}. "
            f"Features {random.choice(['comfortable seating', 'premium screens', 'concession stand', 'reserved seating', 'surround sound'])}. Perfect for {good_for_str}.",
            
            f"Popular {random.choice(['movie theater', 'film house', 'screening venue', 'picture palace'])} offering "
            f"{random.choice(['first-run movies', 'matinee shows', 'late-night screenings', 'special events', 'film festivals'])}. "
            f"Great {vibe} atmosphere for {tags_str} movie experience.",
        ],
        'Theater': [
            f"{random.choice(['Historic', 'Contemporary', 'Intimate', 'Grand', 'Community', 'Experimental'])} theater presenting "
            f"{random.choice(['Broadway shows', 'local productions', 'dramatic plays', 'musical performances', 'comedy acts', 'avant-garde works'])}. "
            f"Features {random.choice(['excellent acoustics', 'tiered seating', 'ornate interior', 'state-of-art stage', 'professional performers'])}. Amazing for {good_for_str}.",
            
            f"Renowned {random.choice(['playhouse', 'performance venue', 'drama theater', 'opera house', 'concert hall'])} hosting "
            f"{random.choice(['world-class performances', 'emerging artists', 'touring productions', 'original works', 'repertory theater'])}. "
            f"Offers {vibe} cultural experience for {tags_str} enthusiasts.",
        ],
    }
    
    # Select random template for the category
    return random.choice(templates.get(category, [f"Wonderful {category.lower()} perfect for {good_for_str} seeking {vibe} experience."]))

# --- REALISTIC NAME GENERATOR ---
def generate_realistic_name(category):
    """Generate realistic attraction names based on category"""
    
    name_templates = {
        'Museum': [
            f"{random.choice(['National', 'Modern', 'Contemporary', 'Historic', 'Maritime', 'Science', 'Natural History', 'Art'])} Museum",
            f"{random.choice(['The', 'Le', 'La', 'El'])} {fake.last_name()} Museum",
            f"{fake.city()} {random.choice(['Art', 'History', 'Cultural', 'Heritage'])} Museum",
            f"Museum of {random.choice(['Modern Art', 'Natural History', 'Contemporary Culture', 'Ancient Civilizations', 'Science and Technology'])}",
        ],
        'Park': [
            f"{fake.last_name()} Park",
            f"{random.choice(['Central', 'Victoria', 'Hyde', 'Regent', 'Golden Gate', 'Millennium'])} Park",
            f"{fake.city()} {random.choice(['Botanical', 'City', 'Memorial', 'Community'])} Gardens",
            f"{random.choice(['Sunset', 'Riverside', 'Lakeside', 'Mountain View', 'Ocean'])} Park",
        ],
        'Restaurant': [
            f"{random.choice(['Chez', 'La', 'Le', 'Il', 'The'])} {fake.last_name()}",
            f"{fake.first_name()}'s {random.choice(['Kitchen', 'Bistro', 'Dining Room', 'Table'])}",
            f"The {random.choice(['Golden', 'Silver', 'Blue', 'Red', 'Green'])} {random.choice(['Fork', 'Spoon', 'Plate', 'Table', 'Kitchen'])}",
            f"{random.choice(['Bella', 'Casa', 'Osteria', 'Trattoria', 'Brasserie'])} {fake.last_name()}",
        ],
        'Cafe': [
            f"{fake.first_name()}'s Cafe",
            f"Cafe {fake.last_name()}",
            f"The {random.choice(['Corner', 'Garden', 'Urban', 'Cozy', 'Hidden'])} Cafe",
            f"{random.choice(['Espresso', 'Coffee', 'Java', 'Bean'])} {random.choice(['House', 'Bar', 'Corner', 'Lounge'])}",
        ],
        'Bar': [
            f"The {random.choice(['Irish', 'English', 'Scottish', 'Belgian'])} Pub",
            f"{fake.last_name()}'s Bar",
            f"The {random.choice(['Red', 'Blue', 'Black', 'White', 'Golden'])} {random.choice(['Lion', 'Eagle', 'Dragon', 'Rose', 'Crown'])}",
            f"{random.choice(['Whiskey', 'Wine', 'Cocktail', 'Beer'])} {random.choice(['Bar', 'Lounge', 'House', 'Room'])}",
        ],
        'Historical': [
            f"{fake.city()} {random.choice(['Castle', 'Palace', 'Fort', 'Cathedral', 'Abbey', 'Monument'])}",
            f"{fake.last_name()} {random.choice(['Memorial', 'Tower', 'House', 'Estate'])}",
            f"{random.choice(['Ancient', 'Old', 'Historic'])} {random.choice(['Ruins', 'Quarter', 'District', 'Site'])}",
            f"The {random.choice(['Royal', 'Imperial', 'Grand'])} {random.choice(['Palace', 'Theater', 'Opera House', 'Library'])}",
        ],
        'Shopping': [
            f"{fake.city()} {random.choice(['Mall', 'Market', 'Bazaar', 'Shopping Center'])}",
            f"{fake.last_name()} {random.choice(['Boutique', 'Gallery', 'Emporium'])}",
            f"The {random.choice(['Grand', 'Central', 'Main', 'Old'])} Market",
            f"{random.choice(['Fashion', 'Luxury', 'Artisan', 'Vintage'])} {random.choice(['District', 'Quarter', 'Row', 'Avenue'])}",
        ],
        'Hiking': [
            f"{random.choice(['Eagle', 'Bear', 'Wolf', 'Deer', 'Fox'])} Trail",
            f"{fake.city()} {random.choice(['Summit', 'Ridge', 'Peak', 'Valley'])} Trail",
            f"{random.choice(['Canyon', 'Mountain', 'Forest', 'Coastal', 'River'])} {random.choice(['Loop', 'Trail', 'Path', 'Route'])}",
            f"{fake.last_name()} {random.choice(['Peak', 'Pass', 'Trail'])}",
        ],
        'Cinema': [
            f"{fake.city()} {random.choice(['Cineplex', 'Cinema', 'Theater'])}",
            f"The {random.choice(['Grand', 'Royal', 'Palace', 'Regal'])} Cinema",
            f"{random.choice(['AMC', 'Odeon', 'Vue', 'Cineworld'])} {fake.last_name()}",
            f"{random.choice(['Art House', 'Independent', 'Classic'])} Cinema",
        ],
        'Theater': [
            f"{fake.city()} {random.choice(['Playhouse', 'Theater', 'Opera House'])}",
            f"The {fake.last_name()} Theater",
            f"{random.choice(['Royal', 'National', 'State', 'Municipal'])} Theater",
            f"{random.choice(['Comedy', 'Drama', 'Musical'])} Theater",
        ],
    }
    
    return random.choice(name_templates.get(category, [f"{fake.company()} {category}"]))

# --- 3. GENERATE ATTRACTIONS (FULL SCHEMA) ---
async def generate_attractions_dataset(n):
    print(f"Generating {n} attractions (Full Schema)...")
    data = []
    activity_texts = []
    categories_list = ['Museum', 'Park', 'Restaurant', 'Cafe', 'Bar', 'Historical', 'Shopping', 'Hiking', 'Cinema', 'Theater']
    tags_list = ['chill', 'romantic', 'kids', 'adventure', 'educational', 'social', 'quiet', 'lively']
    
    # First pass: collect all attraction data and texts for embedding
    for _ in range(n):
        cat = random.choice(categories_list)
        tags = random.sample(tags_list, random.randint(1, 3))
        vibe = random.choice(vibes)
        good_for = random.sample(good_for_options, random.randint(1, 2))
        
        # Generate unique, detailed descriptions based on category
        short_description = generate_unique_description(cat, tags, vibe, good_for)
        
        # Constraints Logic
        is_outdoor = cat in ['Park', 'Hiking', 'Historical']
        indoor_outdoor = 'outdoor' if is_outdoor else 'indoor'
        
        # Build embedding text from semantic fields only (exclude hard constraints like indoor/outdoor, effort, duration)
        activity_embedding_text = (
            f"{short_description} "
            f"Categories: {cat}. "
            f"Tags: {', '.join(tags)}. "
            f"Good for: {', '.join(good_for)}. "
            f"Vibe: {vibe}."
        )
        
        city_name = random.choice(cities)
        country_name = city_country_map.get(city_name, random.choice(countries))
        created = fake.date_time_this_year()
        
        record = {
            "activity_id": fake.uuid4(),
            "source": random.choice(sources),
            "source_ref": fake.url() if random.random() > 0.3 else f"place_{str(fake.uuid4()).replace('-', '')[:16]}",
            "created_at": created,
            "updated_at": created,
            "last_seen_at": fake.date_time_this_year(),
            "name": generate_realistic_name(cat),  # Use realistic name generator
            "short_description": short_description,
            "categories": cat,  # Single category for now, can be comma-separated if needed
            "tags": ', '.join(tags),
            "good_for": ', '.join(good_for),
            "indoor_outdoor": indoor_outdoor,
            "typical_duration_min": random.choice([30, 60, 90, 120]),
            "effort_level": random.choice(intensities),
            "lat": float(fake.latitude()),
            "lng": float(fake.longitude()),
            "city": city_name,
            "country": country_name,
            "opening_hours": f"Mon-Sun {random.randint(8,10)}:00-{random.randint(18,22)}:00",
            "is_open_now": True,
            "timezone": random.choice(['EST', 'GMT', 'IST', 'JST', 'CET']),
            "price_level": random.randint(0, 4),
            "estimated_cost_bucket": random.choice(['free', 'low', 'med', 'high']),
            "rating": round(random.uniform(3.0, 5.0), 1),
            "requires_booking": fake.boolean(),
            "age_min": random.choice([0, 0, 18, 21]) if random.random() > 0.3 else None,
            "accessibility_features": fake.boolean(),
            "embedding": None  # Will be filled after batch embedding
        }
        data.append(record)
        activity_texts.append(activity_embedding_text)
    
    # Batch generate all embeddings at once
    activity_vectors = await generate_embeddings_batch(activity_texts)
    
    # Assign embeddings back to records
    for i, vector in enumerate(activity_vectors):
        data[i]["embedding"] = vector
        
    return pd.DataFrame(data)

# --- 4. DATABASE SQL OPERATIONS ---

def create_tables(att_conn, users_conn):
    """Creates the tables in the respective databases"""
    
    # 1. ATTRACTIONS TABLE (Vector DB)
    cur_att = att_conn.cursor()
    cur_att.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    embedding_dim = get_embedding_dimension()
    
    # Check if table exists and has old schema (check for old 'id' column instead of 'activity_id')
    cur_att.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'attractions' AND column_name = 'id'
        );
    """)
    has_old_schema = cur_att.fetchone()[0]
    
    if has_old_schema:
        print("⚠ Found old schema, dropping and recreating attractions table...")
        cur_att.execute("DROP TABLE IF EXISTS attractions CASCADE;")
        att_conn.commit()
    
    sql_att = f"""
    CREATE TABLE IF NOT EXISTS attractions (
        activity_id UUID PRIMARY KEY,
        source VARCHAR(50),
        source_ref VARCHAR(255),
        created_at TIMESTAMP,
        updated_at TIMESTAMP,
        last_seen_at TIMESTAMP,
        name VARCHAR(255),
        short_description TEXT,
        categories VARCHAR(100),
        tags VARCHAR(255),
        good_for VARCHAR(100),
        indoor_outdoor VARCHAR(20),
        typical_duration_min INTEGER,
        effort_level VARCHAR(20),
        lat DOUBLE PRECISION,
        lng DOUBLE PRECISION,
        city VARCHAR(100),
        country VARCHAR(100),
        opening_hours VARCHAR(255),
        is_open_now BOOLEAN,
        timezone VARCHAR(50),
        price_level INTEGER,
        estimated_cost_bucket VARCHAR(20),
        rating DOUBLE PRECISION,
        requires_booking BOOLEAN,
        age_min INTEGER,
        accessibility_features BOOLEAN,
        embedding vector({embedding_dim})
    );
    CREATE INDEX IF NOT EXISTS attractions_embedding_idx ON attractions USING hnsw (embedding vector_cosine_ops);
    """
    cur_att.execute(sql_att)
    att_conn.commit()
    cur_att.close()
    print("✓ Attractions table created.")

    # 2. USERS & TRIPS TABLES (Metadata DB)
    cur_users = users_conn.cursor()
    cur_users.execute("CREATE EXTENSION IF NOT EXISTS vector;") # For user preference vector
    
    # Check if users table exists and has old schema (check for search_intent_text or username columns, or missing updated_at)
    cur_users.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name IN ('search_intent_text', 'username')
        );
    """)
    has_old_users_schema = cur_users.fetchone()[0]
    
    # Also check if updated_at is missing (new field)
    if not has_old_users_schema:
        cur_users.execute("""
            SELECT NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'updated_at'
            );
        """)
        missing_updated_at = cur_users.fetchone()[0]
        has_old_users_schema = missing_updated_at
    
    if has_old_users_schema:
        print("⚠ Found old users schema, dropping and recreating users and trips tables...")
        cur_users.execute("DROP TABLE IF EXISTS trips CASCADE;")
        cur_users.execute("DROP TABLE IF EXISTS users CASCADE;")
        users_conn.commit()
    
    sql_users = f"""
    CREATE TABLE IF NOT EXISTS users (
        user_id UUID PRIMARY KEY,
        created_at TIMESTAMP,
        updated_at TIMESTAMP,
        home_country VARCHAR(50),
        age_group VARCHAR(20),
        travel_style VARCHAR(20),
        pace_preference VARCHAR(20),
        crowd_tolerance VARCHAR(20),
        activity_intensity_preference VARCHAR(20),
        night_owl BOOLEAN,
        pref_movies DOUBLE PRECISION,
        pref_food DOUBLE PRECISION,
        pref_nature DOUBLE PRECISION,
        pref_museums DOUBLE PRECISION,
        pref_shopping DOUBLE PRECISION,
        pref_nightlife DOUBLE PRECISION,
        pref_adventure DOUBLE PRECISION,
        pref_relaxation DOUBLE PRECISION,
        pref_sports DOUBLE PRECISION,
        pref_music_events DOUBLE PRECISION,
        dietary_style VARCHAR(20),
        accessibility_needs BOOLEAN,
        with_kids BOOLEAN,
        tiredness_level DOUBLE PRECISION,
        hunger_level DOUBLE PRECISION,
        energy_level DOUBLE PRECISION,
        preference_vector vector({embedding_dim})
    );
    """
    
    sql_trips = """
    CREATE TABLE IF NOT EXISTS trips (
        trip_id UUID PRIMARY KEY,
        user_id UUID,  -- Logical FK to users table
        destination VARCHAR(100),
        dates DATE,
        budget INTEGER,
        current_lat DOUBLE PRECISION,
        current_lng DOUBLE PRECISION,
        current_city VARCHAR(100),
        timezone VARCHAR(50),
        local_hour_last_seen INTEGER,
        day_of_week_last_seen INTEGER,
        desired_vibe VARCHAR(50),
        desired_indoor BOOLEAN,
        max_travel_time_min INTEGER,
        avoid_category_1 VARCHAR(50),
        avoid_category_2 VARCHAR(50),
        avoid_category_3 VARCHAR(50)
    );
    """
    
    cur_users.execute(sql_users)
    cur_users.execute(sql_trips)
    users_conn.commit()
    cur_users.close()
    print("✓ Users and Trips tables created.")

def insert_data(att_conn, users_conn, df_att, df_users, df_trips):
    """Inserts the DataFrames into SQL"""
    
    # Helper to convert list to vector string
    def to_vec_str(lst):
        return '[' + ','.join(str(float(v)) for v in lst) + ']'

    # 1. INSERT ATTRACTIONS (skip if activity_id already exists)
    cur_att = att_conn.cursor()
    inserted = 0
    skipped = 0
    
    for idx, row in df_att.iterrows():
        try:
            cur_att.execute("""
                INSERT INTO attractions (
                    activity_id, source, source_ref, created_at, updated_at, last_seen_at,
                    name, short_description, categories, tags, good_for, indoor_outdoor, typical_duration_min,
                    effort_level, lat, lng, city, country, opening_hours, is_open_now, timezone,
                    price_level, estimated_cost_bucket, rating, requires_booking, age_min, accessibility_features, embedding
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector)
                ON CONFLICT (activity_id) DO NOTHING
            """, (
                str(row['activity_id']), row['source'], row['source_ref'], row['created_at'], row['updated_at'], row['last_seen_at'],
                row['name'], row['short_description'], row['categories'], row['tags'], row['good_for'], row['indoor_outdoor'], int(row['typical_duration_min']),
                row['effort_level'], float(row['lat']), float(row['lng']), row['city'], row['country'], row['opening_hours'], bool(row['is_open_now']), row['timezone'],
                int(row['price_level']), row['estimated_cost_bucket'], float(row['rating']), bool(row['requires_booking']), int(row['age_min']) if pd.notna(row['age_min']) else None, bool(row['accessibility_features']), to_vec_str(row['embedding'])
            ))
            
            if cur_att.rowcount > 0:
                inserted += 1
            else:
                skipped += 1
                
            if (inserted + skipped) % 100 == 0:
                att_conn.commit()
                print(f"  Processed {inserted + skipped}/{len(df_att)} attractions (inserted: {inserted}, skipped: {skipped})...")
        except Exception as e:
            print(f"Error inserting attraction {idx}: {e}")
            print(f"Row data: {dict(row)}")
            raise
    
    att_conn.commit()
    cur_att.close()
    print(f"✓ Processed {len(df_att)} attractions: {inserted} inserted, {skipped} skipped (already exist).")

    # 2. INSERT USERS (skip if user_id already exists)
    cur_users = users_conn.cursor()
    users_inserted = 0
    users_skipped = 0
    
    for idx, row in df_users.iterrows():
        try:
            cur_users.execute("""
                INSERT INTO users (
                    user_id, created_at, updated_at, home_country, age_group, travel_style, pace_preference,
                    crowd_tolerance, activity_intensity_preference, night_owl, pref_movies, pref_food,
                    pref_nature, pref_museums, pref_shopping, pref_nightlife, pref_adventure, pref_relaxation,
                    pref_sports, pref_music_events, dietary_style, accessibility_needs, with_kids,
                    tiredness_level, hunger_level, energy_level, preference_vector
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector)
                ON CONFLICT (user_id) DO NOTHING
            """, (
                str(row['user_id']), row['created_at'], row['updated_at'], row['home_country'], row['age_group'],
                row['travel_style'], row['pace_preference'], row['crowd_tolerance'], row['activity_intensity_preference'],
                bool(row['night_owl']), float(row['pref_movies']), float(row['pref_food']), float(row['pref_nature']), float(row['pref_museums']),
                float(row['pref_shopping']), float(row['pref_nightlife']), float(row['pref_adventure']), float(row['pref_relaxation']),
                float(row['pref_sports']), float(row['pref_music_events']), row['dietary_style'], bool(row['accessibility_needs']),
                bool(row['with_kids']), float(row['tiredness_level']), float(row['hunger_level']), float(row['energy_level']) if pd.notna(row['energy_level']) else None,
                to_vec_str(row['preference_vector'])
            ))
            
            if cur_users.rowcount > 0:
                users_inserted += 1
            else:
                users_skipped += 1
        except Exception as e:
            print(f"Error inserting user {idx}: {e}")
            print(f"Row data: {dict(row)}")
            raise
    
    # 3. INSERT TRIPS (skip if trip_id already exists)
    trips_inserted = 0
    trips_skipped = 0
    
    for idx, row in df_trips.iterrows():
        try:
            cur_users.execute("""
                INSERT INTO trips (
                    trip_id, user_id, destination, dates, budget, current_lat, current_lng,
                    current_city, timezone, local_hour_last_seen, day_of_week_last_seen,
                    desired_vibe, desired_indoor, max_travel_time_min, avoid_category_1, avoid_category_2, avoid_category_3
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (trip_id) DO NOTHING
            """, (
                str(row['trip_id']), str(row['user_id']), row['destination'], row['dates'], int(row['budget']),
                float(row['current_lat']), float(row['current_lng']), row['current_city'], row['timezone'],
                int(row['local_hour_last_seen']), int(row['day_of_week_last_seen']), row['desired_vibe'],
                row['desired_indoor'] if pd.notna(row['desired_indoor']) else None, int(row['max_travel_time_min']), 
                row['avoid_category_1'] if pd.notna(row['avoid_category_1']) else None, 
                row['avoid_category_2'] if pd.notna(row['avoid_category_2']) else None, 
                row['avoid_category_3'] if pd.notna(row['avoid_category_3']) else None
            ))
            
            if cur_users.rowcount > 0:
                trips_inserted += 1
            else:
                trips_skipped += 1
        except Exception as e:
            print(f"Error inserting trip {idx}: {e}")
            print(f"Row data: {dict(row)}")
            raise
    
    users_conn.commit()
    cur_users.close()
    print(f"✓ Processed users: {users_inserted} inserted, {users_skipped} skipped (already exist).")
    print(f"✓ Processed trips: {trips_inserted} inserted, {trips_skipped} skipped (already exist).")

# --- MAIN EXECUTION ---
async def main():
    print("=== SPONTANEOUS AI MOCK DATA GENERATOR ===")
    
    # 1. Generate Pandas DataFrames
    df_users = await generate_users_dataset(NUM_USERS)
    df_trips = generate_trips_dataset(df_users)
    df_att = await generate_attractions_dataset(NUM_ATTRACTIONS)
    
    # 2. Connect to DBs and Create Tables & Insert
    try:
        with get_attractions_connection() as att_conn, get_users_connection() as users_conn:
            print("✓ Connected to Databases.")
            create_tables(att_conn, users_conn)
            insert_data(att_conn, users_conn, df_att, df_users, df_trips)
    except Exception as e:
        print(f"❌ Error during SQL operations: {e}")
        import traceback
        traceback.print_exc()
        return

if __name__ == "__main__":
    asyncio.run(main())