-- Create the attractions database (for vectors, embeddings, attractions data)
CREATE DATABASE attractions;

-- Enable vector extension in attractions database
\c attractions
CREATE EXTENSION IF NOT EXISTS vector;


-- Create the users database (for users, trips, preferences)
CREATE DATABASE users;

-- Connect to users database and create users table
\c users

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    -- User preferences
    home_country VARCHAR(255),
    age_group VARCHAR(10) CHECK (age_group IN ('teen', '20s', '30s', '40+')),
    travel_style VARCHAR(20) CHECK (travel_style IN ('budget', 'balanced', 'premium')),
    pace_preference VARCHAR(10) CHECK (pace_preference IN ('slow', 'normal', 'fast')),
    crowd_tolerance VARCHAR(10) CHECK (crowd_tolerance IN ('low', 'medium', 'high')),
    activity_intensity_preference VARCHAR(10) CHECK (activity_intensity_preference IN ('low', 'medium', 'high')),
    night_owl BOOLEAN,
    preferred_start_hour INTEGER CHECK (preferred_start_hour >= 0 AND preferred_start_hour <= 23),
    -- Global constraints
    dietary_style VARCHAR(20) CHECK (dietary_style IN ('none', 'veg', 'vegan', 'kosher')),
    accessibility_needs BOOLEAN,
    with_kids BOOLEAN,
    -- Physical/mental state
    tiredness_level NUMERIC(3, 2) CHECK (tiredness_level >= 0 AND tiredness_level <= 5),
    hunger_level NUMERIC(3, 2) CHECK (hunger_level >= 0 AND hunger_level <= 5),
    energy_level NUMERIC(3, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- Create trips table
CREATE TABLE IF NOT EXISTS trips (
    trip_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    destination VARCHAR(255) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    budget NUMERIC(10, 2),
    -- Trip preferences (wizard categories with percentages, e.g. {"food":80,"nature":60,...})
    preference_breakdown JSONB,
    desired_vibe VARCHAR(20) CHECK (desired_vibe IN ('chill', 'social', 'adventure', 'romantic', 'quiet')),
    desired_indoor BOOLEAN,
    max_walking_distance NUMERIC(4, 2),
    preferred_transportation VARCHAR(20) CHECK (preferred_transportation IN ('walking', 'public', 'taxi')),
    max_travel_time_min INTEGER DEFAULT 30,
    avoid_category_1 VARCHAR(255),
    avoid_category_2 VARCHAR(255),
    avoid_category_3 VARCHAR(255),
    -- Location & time
    current_lat NUMERIC(10, 8),
    current_lng NUMERIC(11, 8),
    current_city VARCHAR(255),
    timezone VARCHAR(100),
    local_hour_last_seen INTEGER CHECK (local_hour_last_seen >= 0 AND local_hour_last_seen <= 23),
    day_of_week_last_seen INTEGER CHECK (day_of_week_last_seen >= 0 AND day_of_week_last_seen <= 6),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT trips_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT valid_date_range CHECK (end_date >= start_date)
);

CREATE INDEX IF NOT EXISTS idx_trips_user_id ON trips(user_id);
CREATE INDEX IF NOT EXISTS idx_trips_dates ON trips(start_date, end_date);
