-- Create the attractions database (for vectors, embeddings, attractions data)
CREATE DATABASE attractions;

-- Enable vector extension in attractions database
\c attractions
CREATE EXTENSION IF NOT EXISTS vector;


-- Create the users database (for users, trips, preferences)
CREATE DATABASE users;
