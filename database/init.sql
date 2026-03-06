-- Create the attractions database (for vectors, embeddings, attractions data)
CREATE DATABASE attractions;

-- Enable vector extension in attractions database
\c attractions
CREATE EXTENSION IF NOT EXISTS vector;

-- Attractions table (matches shared/python/models/attraction.py AttractionBase)
-- Embedding dimension 384 = all-MiniLM-L6-v2
CREATE TABLE IF NOT EXISTS attractions (
    place_id TEXT PRIMARY KEY,
    source TEXT,
    name TEXT NOT NULL,
    categories TEXT[],
    category_id TEXT[],
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    address TEXT,
    city TEXT,
    region TEXT,
    country TEXT,
    telephone TEXT,
    url TEXT,
    type TEXT,
    budget TEXT,
    hours TEXT,
    description TEXT,
    embedding vector(384),
    cluster_id INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_attractions_cluster_id ON attractions (cluster_id);

-- Create the users database (for users, trips, preferences)
CREATE DATABASE users;
