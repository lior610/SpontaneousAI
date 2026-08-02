# Popular-Trip Algo Branch — What Changed

Overview of everything delivered on `popular-trip-algo`. Deep dives live in the
linked feature docs; this page is the map: what shipped, how the pieces fit
together, how to deploy, and how to verify.

## Features shipped

### 1. Popular Trips + Companion Suggestions
**Doc:** [popular-trips-companion-suggestions.md](./popular-trips-companion-suggestions.md)

Offline, Gemini-composed popular routes tagged by traveler persona. At runtime,
when a user likes an attraction that belongs to a matching popular trip, the app
offers another unseen, reachable stop from that trip
("because you liked X, you might also like Y"). Soft / dismissible; capped per trip.

### 2. Walk Further — Walking-Range Expansion
**Doc:** [walk-further-range-expansion.md](./walk-further-range-expansion.md)

When the engine has nothing left inside the trip's hard walking radius, the API
returns `out_of_range` instead of a 404. The UI offers to widen
`trips.max_walking_distance` (persisted) rather than declaring the trip finished.

## How they compose in the trip loop

`web/src/pages/TripPage.tsx` orchestrates both features (and the pre-existing
food intercept) without colliding:

| Situation | What the user sees |
|---|---|
| Food break (auto or "I need food") | Food-intercept card / batch UI |
| Like that matches a popular trip | `CompanionSuggestionPopup` (Accept → show that stop; Dismiss → normal next) |
| Next-activity batch empty / out of range | `WalkFurtherPrompt` (widen radius or finish) |
| User declines walk-further, or radius already at max | Trip-complete summary |

Shared helpers on the page: `applyActivityResult`, `handleNextActivityResult`,
`advanceToNextActivity`, `finishActivity` (complete → optional companion → next).

Feature toggles (web): `featureFlags.companionSuggestions.enabled` and
`featureFlags.walkFurther` in `web/src/config/featureFlags.ts`.

## Supporting infra (not separate product features)

### Shared activity mapper
`api/src/utils/activityMapper.js` — `mapEngineAttractionToActivity` maps an
engine attraction (or companion suggestion) to the frontend `Activity` shape.
Used by both `getNextActivity` and the companion passthrough in
`completeTripActivity`, so both paths stay identical. Covered by
`api/tests/activityMapper.test.js`.

### Walking-range math
`api/src/utils/walkingRange.js` — pure `computeExpandedRange(current, step, max)`
(step, ceiling, float-safe). Controller owns persistence + cache invalidation.
Covered by `api/tests/walkingRange.test.js`.

### Offline pool + schema
- Personas catalog: `data-pipeline/scripts/personas.py` (8 personas).
- Generator: `data-pipeline/scripts/generate_popular_trips.py` (Gemini, grounded
  on real `place_id`s; supports `LOCATION_SLUG` and `POPULAR_TRIPS_FILL_MISSING`).
- Schema: `database/migrations/002_popular_trips.sql` (+ same tables in
  `database/init.sql`) — `personas`, `popular_trips`, `popular_trip_attractions`
  in the **attractions** DB.

### Engine companion stack
- `engine/src/services/companion_service.py` — persona match, reachability,
  anti-nag.
- `engine/src/db/popular_trip_queries.py` — pool lookups.
- Wired from `feedback_service` on `liked`; model field on
  `shared/python/models/recommendation.py`.
- Debug: `GET /recommendations/companion-debug/{trip_id}` (optional `?place_id=`).

### API surface added / changed
- `POST /api/trips/:id/expand-range` — widen walking radius.
- `GET /api/trips/:id/next-activity` — empty radius → `200` + `out_of_range`
  (not 404).
- `POST /api/trips/:id/activities/complete` — may include `companion_suggestion`.

### Config (see `.env.example`)
| Area | Keys |
|---|---|
| Companion runtime | `COMPANION_SIM_THRESHOLD`, `COMPANION_MAX_PER_TRIP`, `COMPANION_COOLDOWN_LIKES`, `COMPANION_DEFAULT_MAX_WALK_KM` |
| Pool generation | `POPULAR_TRIPS_PER_PERSONA`, `POPULAR_TRIP_MIN_STOPS`, `POPULAR_TRIP_MAX_STOPS`, `POPULAR_TRIPS_CATALOG_LIMIT`, `POPULAR_TRIPS_FILL_MISSING`, `LOCATION_SLUG` (+ `GEMINI_*`) |
| Walk further | `WALK_EXPAND_STEP_KM`, `WALK_MAX_KM` |

## Deploy checklist

1. **Migrate** the attractions DB: apply `database/migrations/002_popular_trips.sql`
   (fresh installs already get the tables from `database/init.sql`).
2. **Generate the pool** after attractions (and clustering) are loaded, e.g.
   `LOCATION_SLUG=london python data-pipeline/scripts/generate_popular_trips.py`.
   Use `POPULAR_TRIPS_FILL_MISSING=1` to top up after a partial run.
3. **Env** — copy the new keys from `.env.example` into the engine / API / root
   env as appropriate.
4. **Web flags** — confirm `companionSuggestions` / `walkFurther` in
   `featureFlags.ts` match the desired rollout.
5. **Restart** engine + API so in-memory companion anti-nag state and the
   recommendation cache start clean.

## Verification

```bash
# Companion (mocked boundaries)
python -m pytest engine/tests/test_companion.py

# Companion (real DBs + real pool; auto-skips if unavailable)
python -m pytest engine/tests/test_companion_integration.py

# Node helpers (mapper + walking-range math)
cd api && npm test
# or: node --test api/tests/activityMapper.test.js api/tests/walkingRange.test.js
```

Manual smoke:
- Like a stop that sits in a persona-matching popular trip → companion popup;
  Accept shows that stop, Dismiss continues normally.
- Start with a small walking radius, exhaust it → Walk Further prompt; accept
  grows `trips.max_walking_distance` and more activities appear; decline →
  trip-complete summary.
- Engine debug: `GET http://127.0.0.1:8000/recommendations/companion-debug/{trip_id}`.

## Out of scope for this branch

Food-break intercept and the "I need something specific right now" UI come from
main (merged in), not from this branch's feature work. See
[food-attractions-handling.md](./food-attractions-handling.md).

## Key file index

| Layer | Paths |
|---|---|
| Docs | this file; `popular-trips-companion-suggestions.md`; `walk-further-range-expansion.md`; `AGENTS.md` |
| Data pipeline | `data-pipeline/scripts/personas.py`, `generate_popular_trips.py` |
| DB | `database/migrations/002_popular_trips.sql`, `database/init.sql` |
| Engine | `companion_service.py`, `popular_trip_queries.py`, `feedback_service.py`, `recommendations` routes, `engine/tests/test_companion*.py` |
| API | `tripsController.js`, `routes/trips.js`, `utils/activityMapper.js`, `utils/walkingRange.js`, `api/tests/*.test.js` |
| Web | `TripPage.tsx`, `CompanionSuggestionPopup.tsx`, `WalkFurtherPrompt.tsx`, `tripService.ts`, `featureFlags.ts`, `types/trip.ts` |
| Shared | `shared/python/models/recommendation.py` |
| Config | `.env.example` |
