---
name: Phase 1 - Preference Embedding
overview: "Build the user preference vector: data access and the PreferenceComposer service that blends historical, trip-setup, and real-time signals into a single 384d embedding."
todos:
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

**Schema:** The required tables (`user_preference_embeddings`, `trip_feedback`) already exist in `[database/init.sql](database/init.sql)` — no migration needed.

**Prerequisite:** See [Pre-Step: Popularity for Must-See Attractions](pre_step_popularity_opentripmap.plan.md) for adding OpenTripMap rate enrichment to attractions before DB import.

---

## Data Access

The data access layer is split into three query modules. Each module is a **pure SQL layer** — no business logic, only fetches and returns raw data. The `PreferenceComposer` service orchestrates these queries and performs the embedding logic.

---

### Step 1: Load User and Trip Context

**File:** `[engine/src/db/user_queries.py](engine/src/db/user_queries.py)`


| Function                  | Purpose                                                                                                                                                                                                                                              |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `get_user(conn, user_id)` | Fetches the user row as a dict. **Purpose:** Supplies demographic and lifestyle fields (`age_group`, `travel_style`, `pace_preference`, `dietary_style`, etc.) that are turned into qualifier text and embedded.                                     |
| `get_trip(conn, trip_id)` | Fetches the trip row as a dict. **Purpose:** Supplies the trip-specific setup: `preference_breakdown` (category weights like `{"food":80,"nature":60}`), `with_kids`, `preferred_transportation`, `max_walking_distance`, and location/time context. |


**Order of use:** Both are called first. The user dict is joined with the trip dict to build the trip-setup vector (categories + qualifiers).

---

### Step 2: Load Historical Preference Signal

**File:** `[engine/src/db/preference_queries.py](engine/src/db/preference_queries.py)`


| Function                                                                          | Purpose                                                                                                                                                                                                                                                |
| --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `get_past_embeddings(conn, user_id, exclude_trip_id, limit=5)`                    | Returns up to 5 past preference embeddings for the user, most recent first. **Purpose:** Provides the **historical signal** — what this user has liked in past trips. Excludes the current trip so we don’t double-count the trip-setup vector.        |
| `upsert_preference_embedding(conn, user_id, trip_id, embedding, preference_text)` | Inserts or updates the preference embedding row for the current trip. **Purpose:** Persists the computed vector so it survives reconnections and becomes historical data for future trips. Called once at trip start and again when EMA updates occur. |


**Order of use:** `get_past_embeddings` is called early to compute the historical vector. `upsert_preference_embedding` is called at the end after the final blend is computed.

---

### Step 3: Load Real-Time Feedback and Attraction Embeddings

**File:** `[engine/src/db/feedback_queries.py](engine/src/db/feedback_queries.py)`


| Function                                                 | Purpose                                                                                                                                                                                                                                                                                           |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `get_liked_place_ids(conn, trip_id)`                     | Returns `place_id` strings for attractions the user liked this trip, in chronological order. **Purpose:** These IDs are used to fetch attraction embeddings and build the **real-time EMA vector** — the more the user likes, the more the preference vector shifts toward those types of places. |
| `get_attraction_embeddings(attractions_conn, place_ids)` | Fetches embeddings from the **attractions DB** for the given `place_id`s. **Purpose:** Converts liked place IDs into 384d vectors so they can be blended via EMA into the preference vector. Requires a separate connection to the attractions DB.                                                |
| `get_excluded_place_ids(conn, trip_id)`                  | Returns a set of all `place_id`s the user has interacted with (liked, skipped, or visited). **Purpose:** Used in Phase 2 retrieval to exclude these from future recommendations — once interacted, don’t re-suggest.                                                                              |


**Order of use:** `get_liked_place_ids` → `get_attraction_embeddings` (with attractions DB connection) → EMA blend. `get_excluded_place_ids` is used by the retrieval layer, not by PreferenceComposer.

---

### Data Flow Summary

```
PreferenceComposer.compute(user_id, trip_id)
    │
    ├─► user_queries.get_user()        ──► user dict (qualifiers)
    ├─► user_queries.get_trip()        ──► trip dict (preference_breakdown, etc.)
    ├─► preference_queries.get_past_embeddings()  ──► historical vector (avg)
    ├─► feedback_queries.get_liked_place_ids()   ──► place_ids
    │       └─► feedback_queries.get_attraction_embeddings()  ──► liked vectors (EMA)
    │
    └─► Blend: 0.5 trip + 0.2 historical + 0.3 realtime
            └─► preference_queries.upsert_preference_embedding()  ──► persist
```

## PreferenceComposer

`**[engine/src/services/preference_service.py](engine/src/services/preference_service.py)**`

Three-source weighted blend:


| Source     | Weight | Input                                                     |
| ---------- | ------ | --------------------------------------------------------- |
| Historical | 0.2    | Average of up to 5 past `user_preference_embeddings` rows |
| Trip setup | 0.5    | Weighted avg of per-category embeddings + qualifier text  |
| Real-time  | 0.3    | EMA of liked attraction embeddings from `trip_feedback`   |


### Trip Setup Vector (the interesting part)

`preference_breakdown` JSONB (e.g. `{"food": 80, "nature": 60, "art": 30}`) is used to produce a **weighted average of category embeddings**, not a flat string.

**1. Weighted average of per-category embeddings**

Each category in `preference_breakdown` maps to a phrase (e.g. `"food"` → `"food dining restaurants cafes"`). Each phrase is embedded separately into a 384d vector. Those vectors are blended using the weights as proportions:

```
total = 80 + 60 + 30 = 170
category_vector = (80/170) * embed("food...") + (60/170) * embed("nature...") + (30/170) * embed("art...")
```

This preserves the semantic meaning of each category and respects the user's relative preferences, rather than embedding one long concatenated string.

**2. Qualifier text**

Other user/trip fields are turned into a short text string and embedded: e.g. `"budget relaxed pace with kids vegan walking"` → 384d vector (`qualifier_vector`).

**3. How they're combined**

The trip-setup vector is `0.80 * category_vector + 0.20 * qualifier_vector` — categories dominate (what types of places they like), qualifiers add nuance (how they like to travel, constraints).

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

- `[engine/src/db/user_queries.py](engine/src/db/user_queries.py)`
- `[engine/src/db/preference_queries.py](engine/src/db/preference_queries.py)`
- `[engine/src/db/feedback_queries.py](engine/src/db/feedback_queries.py)` — only the read side here; write side in Phase 2
- `[engine/src/services/preference_service.py](engine/src/services/preference_service.py)`

