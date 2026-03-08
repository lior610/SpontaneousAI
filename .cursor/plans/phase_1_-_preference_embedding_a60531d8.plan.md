---
name: Phase 1 - Preference Embedding
overview: "Build the user preference vector: DB schema, data access, and the PreferenceComposer service that blends historical, trip-setup, and real-time signals into a single 384d embedding."
todos:
  - id: p1-migration
    content: Create database/migrations/003_preference_and_feedback.sql
    status: completed
  - id: p1-user-queries
    content: "Create engine/src/db/user_queries.py: get_user, get_trip"
    status: completed
  - id: p1-pref-queries
    content: "Create engine/src/db/preference_queries.py: get_past_embeddings, upsert_preference_embedding"
    status: completed
  - id: p1-feedback-queries
    content: "Create engine/src/db/feedback_queries.py: get_liked_place_ids, get_excluded_place_ids"
    status: completed
  - id: p1-preference-service
    content: "Create engine/src/services/preference_service.py: PreferenceComposer with 3-source weighted blend"
    status: completed
isProject: false
---

# Phase 1 — Preference Embedding

## What This Phase Delivers

A `preference_vector: np.ndarray (384d)` ready to be consumed by the retrieval layer in Phase 2. Nothing is wired to a route yet — this phase is purely the data + logic to build the vector.

## DB Migration (`003`)

New tables in the `users` DB:

```sql
-- Persist per-trip preference embeddings (historical signal + live session)
CREATE TABLE user_preference_embeddings (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    trip_id INTEGER REFERENCES trips(trip_id) ON DELETE SET NULL,
    preference_text TEXT,          -- human-readable debug string
    embedding vector(384) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX ON user_preference_embeddings(user_id);
CREATE INDEX ON user_preference_embeddings(trip_id);

-- Real-time trip feedback (liked / skipped / visited)
CREATE TABLE trip_feedback (
    id SERIAL PRIMARY KEY,
    trip_id INTEGER NOT NULL REFERENCES trips(trip_id) ON DELETE CASCADE,
    place_id TEXT NOT NULL,
    action VARCHAR(10) CHECK (action IN ('liked', 'skipped', 'visited')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX ON trip_feedback(trip_id);
```

File: `[database/migrations/003_preference_and_feedback.sql](database/migrations/003_preference_and_feedback.sql)`

## Data Access

`**[engine/src/db/user_queries.py](engine/src/db/user_queries.py)**`

- `get_user(conn, user_id)` → user row dict
- `get_trip(conn, trip_id)` → trip row dict (includes `preference_breakdown` JSONB, `travel_style`, `pace_preference`, etc.)

`**[engine/src/db/preference_queries.py](engine/src/db/preference_queries.py)**`

- `get_past_embeddings(conn, user_id, exclude_trip_id)` → list of embedding arrays (most recent first, limit 5)
- `upsert_preference_embedding(conn, user_id, trip_id, embedding, preference_text)` → upsert row for current trip

`**[engine/src/db/feedback_queries.py](engine/src/db/feedback_queries.py)**`

- `get_liked_place_ids(conn, trip_id)` → list of `place_id` strings (for EMA signal)
- `get_excluded_place_ids(conn, trip_id)` → set of `place_id` strings (visited + skipped, for NOT IN filter in Phase 2)

## PreferenceComposer

`**[engine/src/services/preference_service.py](engine/src/services/preference_service.py)**`

Three-source weighted blend:


| Source     | Weight | Input                                                     |
| ---------- | ------ | --------------------------------------------------------- |
| Historical | 0.2    | Average of up to 5 past `user_preference_embeddings` rows |
| Trip setup | 0.5    | Weighted avg of per-category embeddings + qualifier text  |
| Real-time  | 0.3    | EMA of liked attraction embeddings from `trip_feedback`   |


### Trip Setup Vector (the interesting part)

`preference_breakdown` JSONB (e.g. `{"food": 80, "nature": 60, "art": 30}`) is used to produce a **weighted average of category embeddings**, not a flat string:

```python
CATEGORY_PHRASES = {
    "food":        "food dining restaurants cafes",
    "nature":      "nature parks outdoors greenery",
    "art":         "art museums galleries culture",
    "history":     "history monuments heritage sightseeing",
    "nightlife":   "nightlife bars clubs evening entertainment",
    "shopping":    "shopping markets boutiques retail",
    "sports":      "sports activities fitness outdoor recreation",
    "entertainment": "entertainment shows theater cinema",
}

# Weighted average of category embeddings (respects preference_breakdown weights)
total = sum(weights.values())
category_vector = sum((w / total) * embed(CATEGORY_PHRASES[cat])
                      for cat, w in weights.items())

# Qualifier text from other fields (travel_style, pace, with_kids, etc.)
qualifier_vector = embed(build_qualifier_text(user, trip))

# Blend: categories dominate
trip_vector = 0.80 * category_vector + 0.20 * qualifier_vector
```

`build_qualifier_text` maps DB fields to words:

- `travel_style` → `"budget"` / `"balanced"` / `"premium"`
- `pace_preference` → `"relaxed pace"` / `"normal pace"` / `"fast pace"`
- `with_kids = True` → `"with kids"`
- `dietary_style` → `"vegan"` / `"kosher"` / etc.
- `preferred_transportation` → `"walking"` / `"public transport"` / `"taxi"`

### Real-Time EMA

When liked attractions exist in `trip_feedback`, their embeddings are fetched from the attractions DB and blended:

```python
alpha = 0.3  # configurable
for attraction_embedding in liked_embeddings:
    realtime_vector = alpha * attraction_embedding + (1 - alpha) * realtime_vector
```

### Final Blend

```python
preference_vector = (
    0.5 * trip_vector
  + 0.2 * historical_vector   # None → falls back to trip_vector only
  + 0.3 * realtime_vector     # None → falls back to trip_vector only
)
preference_vector /= np.linalg.norm(preference_vector)  # L2 normalize
```

The resulting vector is **upserted** into `user_preference_embeddings` for the current `trip_id` (persists across reconnections, becomes historical signal for future trips).

## Files Summary

- `[database/migrations/003_preference_and_feedback.sql](database/migrations/003_preference_and_feedback.sql)`
- `[engine/src/db/user_queries.py](engine/src/db/user_queries.py)`
- `[engine/src/db/preference_queries.py](engine/src/db/preference_queries.py)`
- `[engine/src/db/feedback_queries.py](engine/src/db/feedback_queries.py)` — only the read side here; write side in Phase 2
- `[engine/src/services/preference_service.py](engine/src/services/preference_service.py)`

