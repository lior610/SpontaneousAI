---
name: Pre-Step - Popularity for Must-See Attractions
overview: Add OpenTripMap rate enrichment to attraction JSONs and DB so retrieval can boost iconic attractions (e.g. Central Park, Statue of Liberty).
todos:
  - id: p0-popularity-schema
    content: Add popularity column to attractions table in init.sql
    status: pending
  - id: p0-popularity-gather
    content: Add OpenTripMap rate enrichment to attraction JSONs before DB import
    status: pending
  - id: p0-popularity-retrieval
    content: Use popularity in Phase 2 retrieval to boost must-see attractions
    status: pending
isProject: false
---

# Pre-Step — Popularity for Must-See Attractions

## Goal

Ensure the app surfaces iconic attractions (e.g. Central Park, Statue of Liberty in NYC) so users visiting a new city get the essential experiences. A `popularity` field on attractions lets retrieval boost these in ranking.

## 1. Schema Change

Add to `attractions` table in `[database/init.sql](database/init.sql)`:

```sql
-- Normalized popularity for retrieval boost (from OpenTripMap rate 1–3)
popularity NUMERIC(4, 3) CHECK (popularity >= 0 AND popularity <= 1)
```

- `popularity`: Normalized score stored in DB. Mapping: rate 3 → 1.0, rate 2 → 0.7, rate 1 → 0.3.

## 2. Gathering Popularity Data — OpenTripMap Approach

**Source: OpenTripMap API (free, no rate limit documented)**

OpenTripMap aggregates OSM, Wikidata, and Wikipedia. Per the API docs, `rate` values are: **1** (minimum), **2**, **3** (maximum), or **1h**, **2h**, **3h** (same scale + cultural heritage). Higher = more notable (e.g. Statue of Liberty = `3h`, local cafe = `1`).

**Pipeline position:** Add an enrichment step that runs on `places_enriched.json` (after get-vibe, before load_places_to_db). Each attraction gets normalized `popularity` added to its JSON.

**Steps:**

1. **Create `data-pipeline/scripts/enrich_opentripmap_rates.py`**
  - Reads `places_enriched.json` (or path from `PLACES_JSON`)
  - For each place with `latitude` and `longitude`:
    - Call OpenTripMap radius API: `radius=100&lon={lng}&lat={lat}&limit=5` to find nearby OTM places
    - Pick best match (closest by distance, or by name similarity)
    - Fetch place details via `xid/{xid}` to get `rate`
    - Parse `rate`: extract numeric part — `"3h"` → 3, `"1"` → 1, etc. (valid values: 1, 2, 3, 1h, 2h, 3h)
  - Add to place dict: `popularity` using normalized mapping:

```python
RATE_TO_POPULARITY = {3: 1.0, 2: 0.7, 1: 0.3}
popularity = RATE_TO_POPULARITY.get(rate_num)  # rate_num from parsed "1", "2", "3", "1h", "2h", "3h"
```

- Write back to same JSON (or output path)
- Use `OPENTRIPMAP_API_KEY` from `.env`
- Add small delay between requests (e.g. 0.2s) to avoid throttling
- Cache results by `(lat, lng)` or `place_id` to avoid re-fetching on re-runs

1. **Run order:** `filter_places` → `get-vibe` → `enrich_opentripmap_rates` → `load_places_to_db`
2. **Update `load_places_to_db.py`** — Include `popularity` in the INSERT/upsert. Map from place dict: `p.get("popularity")`.
3. **Places without a match:** If radius search returns nothing, leave `popularity` as `None`; retrieval can treat missing as 0 or a default.
4. **Pipeline integration:** Update `load_all_locations.ps1` (or equivalent) to run `enrich_opentripmap_rates` after get-vibe and before load_places_to_db for each location.

## 3. Using Popularity in Trip Planning

In Phase 2 retrieval, combine vector similarity with a popularity boost:

```python
# In soft_filters or retrieval scoring
combined_score = similarity + (popularity_boost * attraction.get("popularity", 0))
# e.g. popularity_boost = 0.15 → 15% boost for popularity=1.0
```

This keeps semantic match primary while ensuring high-popularity attractions (must-sees) rank higher when similarity is comparable.

## 4. Files to Modify


| File                                                    | Change                                                                              |
| ------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| `database/init.sql`                                     | Add `popularity` column                                                             |
| `data-pipeline/scripts/enrich_opentripmap_rates.py`     | **New script** — fetch OpenTripMap rate, normalize (3→1, 2→0.7, 1→0.3), add to JSON |
| `data-pipeline/scripts/load_places_to_db.py`            | Persist `popularity` in upsert                                                      |
| `shared/python/models/attraction.py`                    | Add optional `popularity`                                                           |
| Phase 2 retrieval / `engine/src/search/soft_filters.py` | Add popularity boost to scoring                                                     |


