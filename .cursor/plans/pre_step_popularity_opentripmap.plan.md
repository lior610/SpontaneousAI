---
name: Pre-Step - Popularity for Must-See Attractions
overview: Enrich attraction JSONs with OpenTripMap data — popularity (rate), image URL, and Wikipedia extract — then persist to DB.
todos:
  - id: p0-popularity-schema
    content: Add popularity, image_url, wikipedia_extract columns to attractions table in init.sql
    status: pending
  - id: p0-popularity-gather
    content: Add OpenTripMap enrichment script to fetch popularity, image, wikipedia text
    status: pending
isProject: false
---

# Pre-Step — Popularity for Must-See Attractions

## Goal

Enrich each attraction with **popularity** (normalized from OpenTripMap rate), **image_url**, and **wikipedia_extract** (plain-text summary). Focus is on retrieving and persisting this data; using it in retrieval/ranking is out of scope for now.

## 1. Schema Change

Add to `attractions` table in `[database/init.sql](database/init.sql)`:

```sql
-- OpenTripMap enrichment
popularity NUMERIC(4, 3) CHECK (popularity >= 0 AND popularity <= 1),  -- rate 3→1, 2→0.7, 1→0.4, no match→0.2
image_url TEXT,                    -- from OpenTripMap image field
wikipedia_extract TEXT             -- from OpenTripMap wikipedia_extracts.text (plain-text summary)
```

- `popularity`: Normalized score (3→1, 2→0.7, 1→0.4, no match→0.2).
- `image_url`: Image URL from OpenTripMap (e.g. Wikimedia Commons). Null if not found.
- `wikipedia_extract`: Plain-text Wikipedia summary. Null if not found.

## 2. Gathering Popularity Data — OpenTripMap Approach

**Source: OpenTripMap API** — Free tier: **5,000 requests per day**. Run the enrichment script once per day over several days to process large datasets.

OpenTripMap aggregates OSM, Wikidata, and Wikipedia. Per the API docs, `rate` values are: **1** (minimum), **2**, **3** (maximum), or **1h**, **2h**, **3h** (same scale + cultural heritage). Higher = more notable (e.g. Statue of Liberty = `3h`, local cafe = `1`).

**Pipeline position:** Add an enrichment step that runs on `places_enriched.json` (after get-vibe, before load_places_to_db). Each attraction gets `popularity`, `image_url`, and `wikipedia_extract` added to its JSON.

**Steps:**

1. **Create `data-pipeline/scripts/enrich_opentripmap_rates.py`**
   - Reads `places_enriched.json` (or path from `PLACES_JSON`)
   - **Rate limit:** 5,000 requests/day. Script must support `--max-requests` (default 5000) and `--skip-processed` so you can run once per day; each run processes up to 5000 new places, then stops. Re-run daily until all places are enriched.
   - For each place with `latitude` and `longitude` (skip if already has `popularity` when using `--skip-processed`):
     - Call OpenTripMap radius API: `radius=100&lon={lng}&lat={lat}&limit=5` to find nearby OTM places
     - Pick best match (closest by distance, or by name similarity)
     - Fetch place details via `xid/{xid}` to get `rate`, `image`, and `wikipedia_extracts`
     - Parse `rate`: extract numeric part — `"3h"` → 3, `"1"` → 1, etc. (valid values: 1, 2, 3, 1h, 2h, 3h)
   - Add to place dict:

```python
RATE_TO_POPULARITY = {3: 1.0, 2: 0.7, 1: 0.4}
POPULARITY_NO_MATCH = 0.2  # when place not found in OpenTripMap
place["popularity"] = RATE_TO_POPULARITY.get(rate_num, POPULARITY_NO_MATCH)
place["image_url"] = details.get("image")  # OpenTripMap image URL (e.g. Wikimedia Commons)
place["wikipedia_extract"] = (details.get("wikipedia_extracts") or {}).get("text")  # plain-text summary
```

   - **No match:** If radius search returns nothing, set `popularity = 0.2`, `image_url` and `wikipedia_extract` remain `None`.
   - Write back to same JSON (or output path)
   - Use `OPENTRIPMAP_API_KEY` from `.env`
   - Add small delay between requests (e.g. 0.2s) to avoid throttling
   - **Cache:** Persist results by `place_id` (e.g. JSON cache file) so re-runs skip already-enriched places and stay within daily limit.

2. **Run order:** `filter_places` → `get-vibe` → `enrich_opentripmap_rates` (run daily until complete) → `load_places_to_db`
3. **Update `load_places_to_db.py`** — Include `popularity`, `image_url`, `wikipedia_extract` in the INSERT/upsert. Map from place dict: `p.get("popularity")`, `p.get("image_url")`, `p.get("wikipedia_extract")`.
4. **Pipeline integration:** Update `load_all_locations.ps1` (or equivalent) to run `enrich_opentripmap_rates` after get-vibe and before load_places_to_db for each location.

## 3. Files to Modify

| File | Change |
| ---- | ------ |
| `database/init.sql` | Add `popularity`, `image_url`, `wikipedia_extract` columns |
| `data-pipeline/scripts/enrich_opentripmap_rates.py` | **New script** — fetch rate, image, wikipedia_extracts.text; normalize popularity; support `--max-requests 5000` and `--skip-processed` |
| `data-pipeline/scripts/load_places_to_db.py` | Persist `popularity`, `image_url`, `wikipedia_extract` in upsert |
| `shared/python/models/attraction.py` | Add optional `popularity`, `image_url`, `wikipedia_extract` |


