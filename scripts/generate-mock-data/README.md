# Mock Data Generator

This directory contains a Docker setup for generating mock data for the SpontaneousAI application.

## Prerequisites

1. Make sure the main database is running:
   ```bash
   cd ../..
   docker-compose up -d db
   ```

## Usage

### Run the mock data generator:

```bash
cd scripts/generate-mock-data
docker-compose up --build
```

This will:
- Build a Python container with all required dependencies
- Connect to the main database
- Generate and insert mock data (500 attractions, 50 users, 50 trips)

### Run it again (without rebuilding):

```bash
docker-compose up
```

### Run it in the background:

```bash
docker-compose up -d
```

### View logs:

```bash
docker-compose logs -f
```

### Clean up:

```bash
docker-compose down
```

## Configuration

The script uses environment variables from the main `.env` file:
- `POSTGRES_HOST` - Database host (default: `spontaneousai-db-1`)
- `POSTGRES_PORT` - Database port (default: `5432`)
- `POSTGRES_ATTRACTIONS_DB` - Attractions database name (default: `attractions`)
- `POSTGRES_USERS_DB` - Users database name (default: `users`)
- `POSTGRES_USER` - Database user (default: `postgres`)
- `POSTGRES_PASSWORD` - Database password (default: `postgres`)

## What it generates

- **500 Attractions** with embeddings, categories, locations, and metadata
- **50 Users** with preference vectors and full user profiles
- **50 Trips** linked to users with destination and context data

All data is inserted directly into PostgreSQL with proper vector embeddings for semantic search.

## Database Schema: Users and Trips Relationship

In the schema we just built, the Users and Trips tables are connected by a **One-to-Many Relationship**.

This means **One User** can create **Many Trips** (e.g., a trip to London in March, a trip to Tokyo in July), but each Trip belongs to only **One User**.

### 1. The Key Link: `user_id`

The "bridge" between the two tables is the `user_id` column.

- In the **users** table: `user_id` is the **Primary Key** (the unique ID of the person).
- In the **trips** table: `user_id` is a **Foreign Key** (a reference pointing back to the owner).

### 2. How it looks in the Data

**Table: users** (The Travelers)

| user_id | username | travel_style |
| :--- | :--- | :--- |
| A101 | Alice | backpacker |
| B202 | Bob | luxury |

**Table: trips** (The Vacations)

| trip_id | user_id | destination | dates_start |
| :--- | :--- | :--- | :--- |
| T001 | A101 | Japan | 2026-05-01 |
| T002 | A101 | Peru | 2026-09-10 |
| T003 | B202 | Paris | 2026-06-15 |

- Alice (A101) is linked to two trips (Japan and Peru) because her ID appears twice in the trips table.
- Bob (B202) is linked to one trip (Paris).

