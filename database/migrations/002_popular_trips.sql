-- Migration 002: Popular trips pool (personas, popular_trips, popular_trip_attractions)
--
-- Adds the LLM-generated, grounded "popular trips" pool used by the companion
-- suggestion feature. Safe to run against an existing `attractions` database
-- (all statements are idempotent).
--
-- Run: psql "$POSTGRES_URL/attractions" -f database/migrations/002_popular_trips.sql
--   or: \c attractions  then execute this file.

\c attractions

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS personas (
    id SERIAL PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    embedding vector(384) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS popular_trips (
    id SERIAL PRIMARY KEY,
    location_id INTEGER NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    persona_id INTEGER NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    embedding vector(384),
    model TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_popular_trips_location ON popular_trips(location_id);
CREATE INDEX IF NOT EXISTS idx_popular_trips_persona ON popular_trips(persona_id);

CREATE TABLE IF NOT EXISTS popular_trip_attractions (
    id SERIAL PRIMARY KEY,
    popular_trip_id INTEGER NOT NULL REFERENCES popular_trips(id) ON DELETE CASCADE,
    place_id TEXT NOT NULL REFERENCES attractions(place_id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    UNIQUE(popular_trip_id, place_id)
);

CREATE INDEX IF NOT EXISTS idx_pta_trip ON popular_trip_attractions(popular_trip_id);
CREATE INDEX IF NOT EXISTS idx_pta_place ON popular_trip_attractions(place_id);
