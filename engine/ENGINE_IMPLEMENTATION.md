# SpontaneousAI — Recommendation Engine: Deep Implementation Guide

This document is a complete, teammate-facing deep-dive into how the SpontaneousAI Recommendation Engine works. It covers every layer — from the FastAPI application startup, through every service, every database query, and every mathematical operation — so a developer can understand the code without needing to read it.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Application Startup (`main.py`)](#2-application-startup-mainpy)
3. [API Layer — Routes (`recommendations.py`)](#3-api-layer--routes-recommendationspy)
4. [Phase 1: Preference Vector Construction (`preference_service.py`)](#4-phase-1-preference-vector-construction-preference_servicepy)
5. [Phase 2: Cluster-Diverse Retrieval (`cluster_retrieval.py` + `cluster_queries.py`)](#5-phase-2-cluster-diverse-retrieval)
6. [Phase 3: Ranking (`ranking_service.py`)](#6-phase-3-ranking-ranking_servicepy)
7. [Phase 4: Real-Time Feedback Loop (`feedback_service.py`)](#7-phase-4-real-time-feedback-loop-feedback_servicepy)
8. [Database Query Files — Full Reference](#8-database-query-files--full-reference)
9. [End-to-End Request Walkthrough](#9-end-to-end-request-walkthrough)
10. [Q&A: Design Decisions Explained](#10-qa-design-decisions-explained)

---

## 1. Architecture Overview

The engine is a **FastAPI microservice** that operates against two separate PostgreSQL databases:

| Database | Contains |
|---|---|
| `users DB` | `users`, `trips`, `trip_feedback`, `user_preference_embeddings` |
| `attractions DB` | `attractions` (with `pgvector` embeddings), `locations` |

It has **four logical phases** that execute every time a user requests recommendations:

```
[POST /recommendations/]
        │
        ▼
┌───────────────────────────────┐
│  Phase 1: Build Preference    │  preference_service.py
│  Vector (384-dim float32)     │  → user_queries.py
│                               │  → preference_queries.py
│  Historical (20%) +           │  → feedback_queries.py
│  Trip Setup (50%) +           │  → embedding_service.py
│  Real-time EMA (30%)          │
└──────────────┬────────────────┘
               │  preference_vector (np.ndarray)
               ▼
┌───────────────────────────────┐
│  Phase 2: Cluster Retrieval   │  cluster_retrieval.py
│  Top N per geographic cluster │  → cluster_queries.py (SQL)
│  Pre-filtered by:             │  → feedback_queries.py
│  • bounding box               │
│  • opening hours              │
│  • already-seen places        │
└──────────────┬────────────────┘
               │  candidates: List[Dict]  (~25 attractions)
               ▼
┌───────────────────────────────┐
│  Phase 3: Ranking             │  ranking_service.py
│  Multi-signal scoring:        │
│  • Semantic (35%)             │
│  • Distance (20%)             │
│  • Popularity (20%)           │
│  • Hours (10%)                │
│  • Budget (10%)               │
│  • Diversity bonus (5%)       │
└──────────────┬────────────────┘
               │  ranked_candidates: List[Dict]
               ▼
        [Response returned]

[POST /recommendations/feedback]
        │
        ▼
┌───────────────────────────────┐
│  Phase 4: Feedback Loop       │  feedback_service.py
│  Record action in DB          │  → feedback_queries.py
│  If 'liked': apply EMA update │  → preference_service.py
│  to stored preference vector  │  → preference_queries.py
└───────────────────────────────┘
```

---

## 2. Application Startup (`main.py`)

**File:** `engine/src/main.py`

The engine uses FastAPI. Because the router files are in a directory named `internal-routes` (a hyphenated name that Python can't import normally), they are loaded dynamically using `importlib`:

```python
recommendations_path = __file__.replace('main.py', 'internal-routes/recommendations.py')
spec_recs = importlib.util.spec_from_file_location("recommendations", recommendations_path)
recommendations = importlib.util.module_from_spec(spec_recs)
spec_recs.loader.exec_module(recommendations)

app.include_router(recommendations.router)
```

This pattern is repeated for the `attractions` and `utilities` routers. The `.env` file at the project root is loaded at startup using `load_dotenv`, meaning all DB credentials, `EMA_ALPHA`, and scoring weights are environment-driven — no hardcoded values.

**Health check endpoints:**
- `GET /status` — returns `{"service": "engine", "status": "running"}` immediately.
- `GET /health` — attempts a real database connection and returns `503` if the DB is unreachable.

---

## 3. API Layer — Routes (`recommendations.py`)

**File:** `engine/src/internal-routes/recommendations.py`

This file contains two endpoints.

### `POST /recommendations/`

This is the main recommendations endpoint. It **does not accept** `travel_style` or `max_walk_km` from the frontend payload. Both values are fetched directly from the database to prevent frontend clients from spoofing or overriding them. The route:

1. Calls `preference_composer.build(user_id, trip_id)` to obtain the user's 384-dim preference vector.
2. Fetches `user_data` and `trip_data` from the users DB to extract `travel_style` and `max_walking_distance`.
3. Resolves the `destination` city name to a `location_id` by querying the attractions DB's `locations` table with a case-insensitive `LOWER()` match.
4. Fetches `excluded_ids` from `trip_feedback` (places the user has already seen this trip).
5. Calls `cluster_retrieval.get_candidate_pool(...)` to retrieve up to 25 geographically diverse candidates.
6. Fetches `real_seen_categories` from the attractions DB for the diversity scorer.
7. Calls `ranking_engine.rank_candidates(...)` and returns a `List[RecommendationResponse]`.

### `POST /recommendations/feedback`

Accepts `{user_id, trip_id, place_id, action}` where `action` is `"liked"`, `"skipped"`, or `"visited"`. Delegates entirely to `FeedbackService.record_interaction(...)`.

---

## 4. Phase 1: Preference Vector Construction (`preference_service.py`)

**File:** `engine/src/services/preference_service.py`

This is the most mathematically complex part of the engine. The `PreferenceComposer` class builds a single **384-dimensional float32 vector** that represents what the user wants to do *right now* on this trip. The vector is built from three signal sources blended with fixed weights:

| Signal | Weight | Source |
|---|---|---|
| Trip Setup | 50% | User's category preferences + qualifier text |
| Historical | 20% | Averaged embeddings from past trips |
| Real-time | 30% | EMA over liked attractions this trip |

All vectors are **L2-normalized** (divided by their Euclidean magnitude) before blending, so they live on a unit hypersphere and cosine similarity comparisons are valid.

### `build(user_id, trip_id, force_rebuild=False)`

This is the entry point. It implements a **fast-path cache**: if a stored vector already exists for this `trip_id` and `force_rebuild=False`, it returns the stored vector immediately without any computation. This means repeated calls during a trip are essentially free.

If the vector doesn't exist (new trip) or `force_rebuild=True`, it:
1. Loads `user` and `trip` dicts from the users DB.
2. Calls `_build_trip_vector(user, trip)` → 50% signal.
3. Calls `_build_historical_vector(user_id, trip_id)` → 20% signal.
4. Calls `_build_realtime_vector(trip_id, trip_vector)` → 30% signal.
5. Calls `_blend(...)` to combine them.
6. Calls `upsert_preference_embedding(...)` to persist the result.

### `_build_trip_vector(user, trip)`

This creates the vector representing the user's *stated* trip preferences. It combines two sub-vectors:

- **Category Vector (80% of trip signal):** Reads `preference_breakdown` from the `trips` table, which is a JSONB dict like `{"art": 0.7, "food": 0.3}`. Each key maps to a descriptive phrase (e.g., `"art"` → `"art museums galleries exhibitions culture"`). All phrases are embedded in a single batch call via `generate_embeddings_batch`. The resulting embeddings are averaged weighted by their breakdown values. If no breakdown exists, it falls back to `generate_embedding("travel sightseeing exploring city")`.

- **Qualifier Vector (20% of trip signal):** Built by `_build_qualifier_text(user, trip)`, which assembles a short text string from user/trip metadata:
  - `travel_style` (`"budget"` → `"budget-friendly"`, `"premium"` → `"premium luxury"`)
  - `pace_preference` (`"slow"` → `"relaxed pace"`, `"fast"` → `"fast pace"`)
  - `with_kids` → `"with kids family-friendly"`
  - `dietary_style` (appended if not `"none"`)
  - `preferred_transportation` (`"walking"` → `"walkable"`, `"public"` → `"public transport"`)
  
  This text is embedded into a single vector.

The two sub-vectors are added with their weights and L2-normalized.

### `_build_historical_vector(user_id, trip_id)`

Calls `get_past_embeddings(conn, user_id, exclude_trip_id=trip_id)`, which queries the **`user_preference_embeddings`** table in the users DB and returns up to 5 rows ordered by `created_at DESC`.

**What is stored in `user_preference_embeddings`?** Each row is **not** a raw liked-place embedding. It is a fully-computed, fully-blended 384-dim preference vector that was the *final output* of a previous call to `build()` — i.e., the end-state of who the user was by the end of a past trip. Every time `build()` finishes computing for any trip, it writes the result to this table. So the 5 rows are like a diary: *"after trip #12, the user leaned this direction in 384-dim space; after trip #18, they leaned that direction."*

The function averages those past vectors using `np.mean(np.stack(past), axis=0)` and L2-normalizes the result. This average represents the user's *long-term travel identity* across multiple trips. Returns `None` for new users who have no past trips — in that case, `_blend()` redistributes the 20% historical weight to the other two signals.

### `_build_realtime_vector(trip_id, fallback)`

Calls `get_liked_place_ids(conn, trip_id)` from `feedback_queries.py` to get the chronologically ordered list of places liked *this* trip. If there are none, it returns `fallback` (the trip setup vector) unchanged.

For each liked place, it fetches its 384-dim embedding from the attractions DB and applies the EMA formula sequentially:

```
realtime = EMA_ALPHA * attraction_embedding + (1 - EMA_ALPHA) * realtime
```

`EMA_ALPHA` defaults to `0.3`. The result is L2-normalized.

**Important — when does this loop run?** This only executes inside `build()`, which only does a **full rebuild** when no stored vector exists yet for this trip (or when `force_rebuild=True`). The first time `build()` completes, it writes the result into `user_preference_embeddings`. Every subsequent call to `build()` within the same trip hits the fast-path cache — no loop, no DB reads.

So if the user liked 20 places on Day 1, the 20-step EMA replay **will not happen on reconnect**. Each like during Day 1 already called `apply_feedback()`, which persisted the updated vector back to `user_preference_embeddings` immediately after each step. By the time the user reconnects on Day 2, the stored vector already incorporates all 20 likes — the fast-path cache fires instantly and returns it.

The only scenario where the full replay would run is if the `user_preference_embeddings` row was explicitly deleted between sessions (e.g., a test environment purge via `DELETE FROM user_preference_embeddings`), which would force `build()` to reconstruct the vector from scratch using the `trip_feedback` history. Under normal operation this never happens.

### `_blend(trip_vector, historical_vector, realtime_vector)`

Combines the three signals:

```python
combined = WEIGHT_TRIP_SETUP * trip_vector
         + WEIGHT_HISTORICAL * historical_vector
         + WEIGHT_REALTIME * realtime_vector
```

If `historical_vector` is `None` (new user), the historical weight (0.2) is redistributed proportionally between trip setup and realtime:

```python
total = WEIGHT_TRIP_SETUP + WEIGHT_REALTIME  # 0.8
combined = (0.5 / 0.8) * trip_vector + (0.3 / 0.8) * realtime_vector
```

The result is L2-normalized and returned as the final preference vector.

---

## 5. Phase 2: Cluster-Diverse Retrieval

**Files:** `engine/src/services/cluster_retrieval.py`, `engine/src/db/cluster_queries.py`

### `ClusterRetrievalService.get_candidate_pool(...)`

**File:** `cluster_retrieval.py`

This service's job is to ask the `attractions` database: *"Give me up to 25 attractions that are geographically diverse and close to what this user wants."*

It does the following:
1. Formats the 384-dim preference vector as a pgvector string: `"[0.123, -0.456, ...]"`.
2. Loads `excluded_place_ids` from the users DB (all places the user has already interacted with this trip).
3. Calls `execute_cluster_similarity_query(...)` against the attractions DB.
4. For each returned row, strips the raw `embedding` column (large binary, not needed in the response) and normalizes the row into a clean dict via `normalize_attraction_row`.

The service is initialized with `top_per_cluster=5` and `max_clusters=5`, producing up to **25 candidates** from up to 5 different geographic neighborhoods.

### `execute_cluster_similarity_query(...)` — The SQL Deep-Dive

**File:** `cluster_queries.py`

This is a single, dynamically-constructed **CTE-based SQL query** that performs the entire retrieval in one database round-trip. Here is how it is assembled:

#### Step 1: `RankedAttractions` CTE — The Vector Search

```sql
WITH RankedAttractions AS (
    SELECT
        place_id, name, categories, latitude, longitude, hours, budget,
        popularity, description, embedding, location_cluster_id,
        (1 - (embedding <=> %s::vector) / 2) as similarity,
        (embedding <=> %s::vector) as distance,
        ROW_NUMBER() OVER(
            PARTITION BY location_cluster_id
            ORDER BY embedding <=> %s::vector
        ) as cluster_rank
    FROM attractions
    WHERE location_id = %s
      AND embedding IS NOT NULL
```

- **`embedding <=> %s::vector`** — This is pgvector's **cosine distance** operator. It computes the angular distance between the stored attraction embedding and the user's preference vector. Distance `0` = identical direction, distance `2` = opposite.
- **`similarity`** — Converts cosine distance to a similarity score in `[0, 1]` via `(1 - distance / 2)`.
- **`ROW_NUMBER() OVER(PARTITION BY location_cluster_id ORDER BY ...)`** — This is the key "cluster diversity" operation. PostgreSQL groups all attractions by their geographic cluster (e.g., "Soho cluster", "Hyde Park cluster") and assigns a sequential rank (1, 2, 3...) within each cluster from most to least similar. This means rank 1 within every cluster is that cluster's *best match* for this user.
- The `%s::vector` embedding is passed **three times** in `params` because it is referenced three separate times in the SQL (similarity, distance, ORDER BY).

#### Step 2: Geographic Bounding Box Pre-Filter (appended if location provided)

```sql
AND latitude BETWEEN %s AND %s
AND longitude BETWEEN %s AND %s
```

Before running expensive vector math globally, the query reduces the search space to a geographic square around the user:

- `lat_offset = max_walk_km / 111.045` (1 degree latitude ≈ 111.045 km)
- `lng_offset = max_walk_km / (111.045 * cos(lat_radians))` (longitude degrees shrink at higher latitudes)

This draws a square bounding box, not a circle. Attractions in the corners of the square survive at up to ~1.41× the radius. That is intentional — the Haversine check in Phase 3 (Ranking) acts as the precise circular cutoff. The SQL filter is a cheap, fast pre-elimination.

#### Step 3: Opening Hours Pre-Filter (appended if `current_hour` provided)

```sql
AND (
    hours IS NULL OR hours = '' OR hours = '00:00-23:59'
    OR (
        hours ~ '^\d{1,2}:\d{2}-\d{1,2}:\d{2}$'
        AND (
            -- Standard hours: e.g. 09:00-18:00
            (open_hour <= current_hour AND current_hour < close_hour)
            OR
            -- Overnight hours: e.g. 22:00-02:00
            (open_hour > close_hour AND (current_hour >= open_hour OR current_hour < close_hour))
        )
    )
    OR hours !~ '^\d{1,2}:\d{2}-\d{1,2}:\d{2}$' -- Unparseable strings pass through to Python
)
```

This filter uses PostgreSQL's `SPLIT_PART` function to mathematically slice the `"HH:MM-HH:MM"` string without loading it into Python:
- `SPLIT_PART(SPLIT_PART(hours, '-', 1), ':', 1)` extracts the opening hour integer.
- `SPLIT_PART(SPLIT_PART(hours, '-', 2), ':', 1)` extracts the closing hour integer.

If the hours string doesn't match the regex (e.g., `"12 PM: Open"`), the attraction is **allowed through** and the Python ranking layer handles it. This avoids blocking valid places just because their hours format is unusual.

#### Step 4: Exclusions and Hard Filters

```sql
AND place_id NOT IN (%s, %s, ...)   -- excluded_place_ids
AND some_column = %s                 -- custom hard filters (if any)
```

The `excluded_place_ids` (liked, skipped, or visited this trip) are injected as a `NOT IN` clause so they never appear again.

#### Step 5: `ClusterMins` CTE — Ranking Clusters Themselves

```sql
ClusterMins AS (
    SELECT location_cluster_id, distance as min_dist
    FROM RankedAttractions
    WHERE cluster_rank = 1
)
```

**What is `cluster_rank`?** It is not a column stored in the database. It is a **computed column** created on the fly by the `ROW_NUMBER()` window function in `RankedAttractions` (Step 1). The window function groups all filtered attractions by their `location_cluster_id` (geographic neighborhood) and assigns sequential integers — 1, 2, 3... — within each group, ordered by cosine distance from smallest to largest. So `cluster_rank = 1` is simply **the single attraction with the smallest cosine distance to the user inside that neighborhood** — the best possible match in that geographic area.

`ClusterMins` filters to only `cluster_rank = 1` rows (one per cluster) and stores that cluster's best `distance` as `min_dist`. This answers the question: *"What is the best possible match this neighborhood can offer this user?"* That answer is used in the next step to rank neighborhoods against each other.

#### Step 6: `FinalRanking` CTE — Stamp Cluster Quality onto Every Attraction

```sql
FinalRanking AS (
    SELECT r.*,
           DENSE_RANK() OVER(ORDER BY c.min_dist) as cluster_score_rank
    FROM RankedAttractions r
    JOIN ClusterMins c ON r.location_cluster_id = c.location_cluster_id
)
```

`DENSE_RANK() OVER(ORDER BY c.min_dist)` is a **second window function**, this time applied across all clusters (not within them). It ranks the *neighborhoods themselves* by their quality:
- The cluster whose `min_dist` is smallest (best overall match in city) → `cluster_score_rank = 1`
- Second-best cluster → `cluster_score_rank = 2`, etc.

The JOIN re-attaches every attraction to its cluster's `min_dist`. The `DENSE_RANK()` then stamps this `cluster_score_rank` value **onto every single attraction inside that cluster** — not just the rank-1 one. All 200 attractions in the best-matching Soho cluster all carry `cluster_score_rank = 1`. All 150 attractions in the third-best cluster all carry `cluster_score_rank = 3`. This makes the final filter possible.

#### Step 7: Final Selection — Full Example Walkthrough

```sql
SELECT * FROM FinalRanking
WHERE cluster_rank <= 5        -- top 5 attractions per cluster
  AND cluster_score_rank <= 5  -- only from the top 5 clusters
ORDER BY cluster_score_rank, cluster_rank;
```

Here is a complete concrete example with 3 London clusters after all filters:

```
── STEP 1: RankedAttractions — cluster_rank assigned within each cluster ─────

┌─────────────────────┬──────────┬───────────┬──────────────┐
│ name                │ cluster  │ distance  │ cluster_rank │
├─────────────────────┼──────────┼───────────┼──────────────┤
│ Tate Modern         │ South    │   0.09    │      1       │ ← best in "South"
│ Borough Market      │ South    │   0.20    │      2       │
│ Natural History Mu. │ West     │   0.12    │      1       │ ← best in "West"
│ V&A Museum          │ West     │   0.18    │      2       │
│ Hyde Park           │ West     │   0.25    │      3       │
│ The Shard           │ East     │   0.30    │      1       │ ← best in "East"
└─────────────────────┴──────────┴───────────┴──────────────┘

── STEP 2: ClusterMins — one row per cluster, its best distance ───────────────

┌──────────┬──────────┐
│ cluster  │ min_dist │  (quality score for the whole neighborhood)
├──────────┼──────────┤
│ South    │   0.09   │  ← best neighborhood overall
│ West     │   0.12   │
│ East     │   0.30   │  ← weakest neighborhood
└──────────┴──────────┘

── STEP 3: FinalRanking — cluster_score_rank stamped on every attraction ──────

┌─────────────────────┬──────────┬──────────────┬────────────────────┐
│ name                │ cluster  │ cluster_rank │ cluster_score_rank │
├─────────────────────┼──────────┼──────────────┼────────────────────┤
│ Tate Modern         │ South    │      1       │         1          │
│ Borough Market      │ South    │      2       │         1          │
│ Natural History Mu. │ West     │      1       │         2          │
│ V&A Museum          │ West     │      2       │         2          │
│ Hyde Park           │ West     │      3       │         2          │
│ The Shard           │ East     │      1       │         3          │
└─────────────────────┴──────────┴──────────────┴────────────────────┘

── STEP 4: Final SELECT — filter and order ────────────────────────────────────
  cluster_rank <= 5 AND cluster_score_rank <= 5
  ORDER BY cluster_score_rank ASC, cluster_rank ASC

  1. Tate Modern         (best cluster, best within it)
  2. Borough Market      (best cluster, 2nd within it)
  3. Natural History Mu. (2nd cluster, best within it)
  4. V&A Museum          (2nd cluster, 2nd within it)
  5. Hyde Park           (2nd cluster, 3rd within it)
  6. The Shard           (3rd cluster, best within it)
```

The result guarantees attractions span **multiple geographic neighborhoods** (diversity), prioritized by the **most semantically relevant neighborhoods first**, and within each neighborhood only the **top N most similar** attractions are included. Maximum output: `top_per_cluster × max_clusters = 5 × 5 = 25 candidates`.

---

## 6. Phase 3: Ranking (`ranking_service.py`)

**File:** `engine/src/services/ranking_service.py`

The `RankingEngine` takes the ~25 candidates and assigns each a final score between 0 and 1 using five independently computed sub-scores and one dynamic diversity bonus. All weights are configurable via `.env`.

| Score | Weight | How It's Computed |
|---|---|---|
| `semantic_score` | 35% | Direct cosine similarity from the vector search (column `similarity`) |
| `distance_score` | 20% | Haversine formula, clamped: `max(0, 1 - dist_km / max_walk_km)` |
| `popularity_score` | 20% | Foursquare popularity (0–1), defaults to `0.2` if missing/invalid |
| `hours_score` | 10% | `1.0` if open, `0.0` if closed, `0.5` if unknown |
| `budget_score` | 10% | Matches `travel_style` string to numeric budget thresholds |
| `diversity_bonus` | 5% | Dynamic, applied after initial sort |

### `calculate_haversine_distance(lat1, lon1, lat2, lon2)`

Implements the Haversine formula for spherical Earth distance:

```python
R = 6371.0  # Earth radius in km
dlat = radians(lat2 - lat1)
dlon = radians(lon2 - lon1)
a = sin(dlat/2)^2 + cos(lat1) * cos(lat2) * sin(dlon/2)^2
c = 2 * atan2(sqrt(a), sqrt(1-a))
return R * c
```

This is necessary because standard Euclidean distance is invalid on a sphere.

### `_score_hours(hours_str, current_hour)`

Mirrors the SQL hours logic in Python as a safety net. If the hours string couldn't be parsed by the SQL filter and slipped through, Python evaluates it here. A confirmed-closed attraction gets `hours_score = 0.0`, which is then used to **zero out the entire final score**, via a hard-override after scoring:

```python
if hours_score == 0.0:
    candidate['_base_score'] = 0.0
```

### `_score_budget(attr_budget_str, travel_style)`

Strips non-numeric characters from the budget string and converts it to a float. Then compares against `travel_style`:
- `"budget"` → full score if budget ≤ $15
- `"balanced"` → full score if $10 ≤ budget ≤ $50
- `"premium"` → full score if budget ≥ $40

### `_apply_diversity_bonus(candidate, seen_categories, cluster_counts)` — The Dynamic Re-Ranker

This is applied **after the initial sort by base score**, iterating through candidates in order:

- **+1.0 bonus** if the attraction introduces a category not yet seen in the result set.
- **−0.5 × count penalty** for each additional attraction from the same `location_cluster_id`. (e.g., the 3rd attraction from cluster 7 receives a `−1.0` penalty.)

The final score including diversity:

```python
final_score = base_score + WEIGHT_DIVERSITY * diversity_bonus
```

After applying diversity, the list is **re-sorted** by `final_score`. This means a slightly less semantically relevant attraction in a fresh neighborhood can legitimately overtake a highly similar one from a saturated cluster.

---

## 7. Phase 4: Real-Time Feedback Loop (`feedback_service.py`)

**File:** `engine/src/services/feedback_service.py`

`FeedbackService.record_interaction(user_id, trip_id, place_id, action)` is called whenever the user swipes or interacts with an attraction. It does two things in sequence:

### Step 1: Persist the Action

Calls `record_feedback(conn, trip_id, place_id, action)` from `feedback_queries.py`, which runs an upsert:

```sql
INSERT INTO trip_feedback (trip_id, place_id, action)
VALUES (%s, %s, %s)
ON CONFLICT (trip_id, place_id)
DO UPDATE SET action = EXCLUDED.action, created_at = NOW()
```

The `UNIQUE (trip_id, place_id)` constraint prevents duplicate rows. If a user previously skipped a place and then likes it, the action is gracefully updated rather than causing an insert error.

### Step 2: EMA Vector Update (only for `"liked"`)

If `action == "liked"`, calls `preference_composer.apply_feedback(user_id, trip_id, place_id)`, which:

1. Loads the currently stored preference vector for this trip via `get_current_embedding(conn, trip_id)`. If none exists, it calls `build()` to create one from scratch.
2. Fetches the new liked attraction's 384-dim embedding from the attractions DB.
3. Applies one step of the EMA:
   ```python
   updated = EMA_ALPHA * attraction_emb + (1 - EMA_ALPHA) * current
   updated = L2_normalize(updated)
   ```
4. Persists the updated vector back to `user_preference_embeddings` via `upsert_preference_embedding(...)`.

> **Note:** `"skipped"` and `"visited"` are only used as **exclusion filters**. They do not mathematically influence the preference vector. Shifting the vector *away* from a skipped place is avoided because the reason for the skip is ambiguous (e.g., user isn't hungry right now, not that they dislike food).

---

## 8. Database Query Files — Full Reference

### `user_queries.py`

| Function | Query | Purpose |
|---|---|---|
| `get_user(conn, user_id)` | `SELECT ... FROM users WHERE id = %s` | Fetch all user profile fields as a dict |
| `get_trip(conn, trip_id)` | `SELECT ... FROM trips WHERE trip_id = %s` | Fetch all trip fields including `preference_breakdown` JSONB |

### `preference_queries.py`

| Function | Query | Purpose |
|---|---|---|
| `get_past_embeddings(conn, user_id, exclude_trip_id, limit=5)` | `SELECT embedding FROM user_preference_embeddings WHERE user_id = %s AND trip_id != %s ORDER BY created_at DESC LIMIT %s` | Historical signal: up to 5 past trip vectors |
| `get_current_embedding(conn, trip_id)` | `SELECT embedding FROM user_preference_embeddings WHERE trip_id = %s` | Fast-path cache: retrieve stored vector for current trip |
| `upsert_preference_embedding(conn, user_id, trip_id, embedding, text)` | `INSERT ... ON CONFLICT (trip_id) DO UPDATE SET embedding = EXCLUDED.embedding` | Persist or update the preference vector for this trip |

### `feedback_queries.py`

| Function | Query | Purpose |
|---|---|---|
| `get_liked_place_ids(conn, trip_id)` | `SELECT place_id FROM trip_feedback WHERE trip_id = %s AND action = 'liked' ORDER BY created_at ASC` | Chronological list of likes for EMA replay in `_build_realtime_vector` |
| `get_excluded_place_ids(conn, trip_id)` | `SELECT place_id FROM trip_feedback WHERE trip_id = %s` | All interacted places (liked + skipped + visited) to block from recommendations |
| `record_feedback(conn, trip_id, place_id, action)` | `INSERT ... ON CONFLICT DO UPDATE` | Write or update a user interaction |
| `get_attraction_embeddings(attractions_conn, place_ids)` | `SELECT place_id, embedding FROM attractions WHERE place_id = ANY(%s)` | Fetch vectors for liked attractions (for EMA update) |
| `get_attraction_categories(attractions_conn, place_ids)` | `SELECT categories, type FROM attractions WHERE place_id = ANY(%s)` | Seed `real_seen_categories` for the diversity scorer |

---

## 9. End-to-End Request Walkthrough

Here is the complete lifecycle of a single `POST /recommendations/` call for a mid-trip user:

```
1. Request arrives: {user_id: 5, trip_id: 42, current_location: {lat: 51.5, lng: -0.12}, current_time: "14:30"}

2. preference_composer.build(user_id=5, trip_id=42, force_rebuild=False)
   └── get_current_embedding(conn, trip_id=42)
       → Row already exists (user has been using the app)
       → Returns stored 384-dim vector immediately (fast path, no computation)

3. Router fetches from users DB:
   └── get_user(conn, 5)        → {travel_style: "balanced", pace_preference: "fast", ...}
   └── get_trip(conn, 42)       → {max_walking_distance: 2.5, destination: "London", preference_breakdown: {...}}
   └── get_excluded_place_ids(conn, 42) → {"fs_abc123", "fs_def456"}  (2 already seen)

4. Router resolves location_id:
   └── SELECT id FROM locations WHERE LOWER(name) = LOWER('London') → location_id = 3

5. cluster_retrieval.get_candidate_pool(location_id=3, trip_id=42, preference_vector=..., ...)
   └── execute_cluster_similarity_query(...)
       → Bounding box: lat ±0.0225°, lng ±0.0324° around (51.5, -0.12)
       → Hours filter: current_hour=14, exclude closed venues
       → NOT IN excluded_ids
       → pgvector <=> cosine distance across ~8,000 London attractions
       → ROW_NUMBER() PARTITION BY location_cluster_id
       → ClusterMins: find best cluster per neighborhood
       → FinalRanking: top 5 clusters, top 5 per cluster
       → Returns 23 candidates (2 clusters had fewer than 5 matching open attractions)

6. get_attraction_categories(attr_conn, excluded_ids) → {"Cafe", "Bar"} (already seen categories)

7. ranking_engine.rank_candidates(candidates=23, user_lat=51.5, user_lng=-0.12, ...)
   └── For each of 23 candidates:
       • semantic_score:   0.82  (from pgvector <=> result)
       • distance_score:   0.68  (haversine 0.80 km → 1 - 0.80/2.5)
       • popularity_score: 0.91  (Foursquare data)
       • hours_score:      1.0   (confirmed open at 14:00)
       • budget_score:     1.0   (balanced user, $25 attraction)
       • _base_score = 0.35*0.82 + 0.20*0.68 + 0.20*0.91 + 0.10*1.0 + 0.10*1.0 = 0.845
   └── Sort by base_score descending
   └── Apply diversity bonus greedily:
       • First "Museum" candidate: +1.0 bonus (new category)
       • Second candidate from cluster 7: -0.0 (first from cluster, no penalty)
       • Third candidate from cluster 7: -0.5 (second from cluster 7)
   └── Re-sort by final_score
   └── Return sorted list

8. Format into List[RecommendationResponse] and return
```

---

## 10. Q&A: Design Decisions Explained

### Cluster-Diverse Retrieval

**Q: Why not just take the top 25 most similar attractions globally?**
Without cluster partitioning, the top 25 results are almost always clustered in one high-density neighborhood (e.g., 25 things in tourist-saturated central London). The `ROW_NUMBER() OVER(PARTITION BY location_cluster_id)` ensures every geographic neighborhood gets equal representation, so the user receives a spread across the entire city.

**Q: Why are there two separate hours filters (SQL + Python)?**
The SQL filter uses `SPLIT_PART` which only works on the `"HH:MM-HH:MM"` format. Any attraction with an unusual hours string (e.g., `"Open 24 Hrs"` or `"12 PM-10 PM"`) passes through the SQL filter untouched. Python then evaluates those edge cases. If the string is unequivocally indicating "closed," Python zeroes the final score. This **two-stage funnel** prevents blocking valid attractions just because their hours format is non-standard.

**Q: What is the `params` array in `execute_cluster_similarity_query`?**
The user's preference vector is embedded in the query three separate times (for `similarity`, `distance`, and the `ORDER BY`). That's why `params` starts as:
```python
params = [embedding_str, embedding_str, embedding_str, location_id]
```
Additional values for bounding box, hours, and exclusions are appended dynamically as the query is constructed.

### Ranking Layer

**Q: Why is the diversity bonus applied after the initial sort rather than included in the base score?**
Diversity is inherently **relative** — whether an attraction introduces a new category depends on what appears before it in the sorted list. It's a greedy sequential calculation: process candidates in order of base score, reward novelty, and penalize repetition. If it were part of the base score, we'd need to know the final ordering to compute it, which is circular.

**Q: How exactly does the cluster penalty stop the engine from recommending 5 things from the same block?**
`cluster_counts` is a dictionary tracking how many times each `location_cluster_id` has appeared in the final list so far. For each additional appearance: `diversity_bonus -= 0.5 * count`. The 2nd attraction from cluster 7 gets `-0.5`, the 3rd gets `-1.0`, etc. Once the penalty is large enough, a slightly less relevant attraction from a different cluster will surpass it in `final_score`.

### Real-Time Feedback

**Q: Why doesn't "skipped" or "visited" update the preference vector?**
Shifting the vector *away* from a skipped place is risky because the reason for skipping is unknown. A user might skip a highly-rated pizza restaurant simply because they just ate. If we move their vector away from `"food"`, the entire trip's food recommendations degrade. The engine only acts on confirmed positive signals (likes) and purely uses skips/visits as **negative filters** that prevent re-recommendation.

**Q: Why is EMA_ALPHA = 0.3? Doesn't liking one café shift the whole profile?**
EMA works multiplicatively against the remaining weight. With `α = 0.3`, one liked café contributes 30% to the new vector, while the existing cumulative profile owns 70%. After two likes, the second like contributes `0.3 × 0.3 = 9%` of the original profile. The effect decays rapidly — it's a strong nudge, not a replacement. The setting means the engine is responsive to real-time mood without inducing amnesia about the user's overall trip preferences.

**Q: What happens if a user loses connection and reconnects mid-trip?**
`get_current_embedding(conn, trip_id)` fetches the last persisted vector from `user_preference_embeddings`. Since every liked interaction writes the updated vector back to the database immediately, the engine resumes from exactly where it left off with no data loss.

---

*Last updated: April 2026 | Engine: SpontaneousAI Recommendation Microservice*
