# Popular Trips + Companion Suggestions

"Because you liked X, you might also like Y." When a user likes an attraction that
belongs to a pre-generated popular trip whose persona matches the user, the app
offers another (unseen, reachable) stop from that same popular trip.

## Two parts

### 1. One-time offline pool generation (grounded + persona-tagged)
- Personas ("types of people in society") are data: `data-pipeline/scripts/personas.py`
  (8 personas). Each `description` is embedded (all-MiniLM-L6-v2, 384d) and stored in
  `personas.embedding` — this is the **match vector**.
- `data-pipeline/scripts/generate_popular_trips.py` asks Google Gemini, per city and
  per persona, to compose `POPULAR_TRIPS_PER_PERSONA` (default 5) ordered routes of
  4-6 stops using ONLY the city's real attractions. Returned `place_id`s are validated
  against the DB catalog (hallucinations dropped). Volume: ~8 x 5 = 40 trips per city.
- Persisted permanently in the `attractions` DB: `personas`, `popular_trips`,
  `popular_trip_attractions` (see `database/init.sql` and
  `database/migrations/002_popular_trips.sql`). Separate from the ephemeral Node
  recommendation cache. Re-run the script to rebuild (idempotent per location).

### 2. Runtime companion suggestion (on like)
Reuses the existing like path. When `POST /recommendations/feedback` receives a
`liked` action, after the EMA update `CompanionSuggestionService`
(`engine/src/services/companion_service.py`):
1. finds popular trips containing the liked `place_id` (index `idx_pta_place`);
2. keeps trips whose persona embedding has cosine >= `COMPANION_SIM_THRESHOLD` (0.45)
   with the user's current preference vector; picks the best;
3. selects the first **unseen** stop (excludes `trip_feedback` + the liked one) that is
   **within walking distance** — reachability is MANDATORY (measured from the trip's live
   position, falling back to the liked attraction's coords). If none qualify -> no suggestion.

The suggestion rides back in the feedback response as `companion_suggestion`. The Node
controller (`completeTripActivity`) maps it to the frontend `Activity` shape (shared
`api/src/utils/activityMapper.js`) and returns it as `companion_suggestion`. The web
`CompanionSuggestionPopup` offers Accept (show it next) / Dismiss (normal next activity).

## Data model (attractions DB)
- `personas(id, slug UNIQUE, name, description, embedding vector(384), ...)`
- `popular_trips(id, location_id FK, persona_id FK, name, description, embedding vector(384), model, created_at)`
- `popular_trip_attractions(id, popular_trip_id FK, place_id FK->attractions, position, UNIQUE(popular_trip_id, place_id))`

## Config
- Engine: `COMPANION_SIM_THRESHOLD=0.45`, `COMPANION_MAX_PER_TRIP=3`,
  `COMPANION_COOLDOWN_LIKES=1`, `COMPANION_DEFAULT_MAX_WALK_KM=2.0`.
- Generation: `POPULAR_TRIPS_PER_PERSONA=5`, `POPULAR_TRIP_MIN_STOPS=4`,
  `POPULAR_TRIP_MAX_STOPS=6`, `POPULAR_TRIPS_CATALOG_LIMIT=150`, `LOCATION_SLUG` (optional),
  reuse `GEMINI_API_KEY` / `GEMINI_MODEL`.
- Web: `featureFlags.companionSuggestions.enabled` toggles the prompt.

## Anti-nag & autonomy
- Suggestions are soft/dismissible; never force-replace the next activity.
- Per-trip cap + cooldown between suggestions (in-memory per engine process; resets on restart).

## Verification
- Engine unit tests: `engine/tests/test_companion.py`
  (`~/.pyenv/versions/3.11.8/bin/python -m pytest engine/tests/test_companion.py`).
- Node mapper tests: `node --test api/tests/activityMapper.test.js` (or `npm test` in `api/`).
- Web has no test harness; the popup is covered manually.

## Operational notes
- Run the generator once after loading a city's attractions (and after clustering), e.g.
  `LOCATION_SLUG=london python data-pipeline/scripts/generate_popular_trips.py`.
- Existing deployments: apply `database/migrations/002_popular_trips.sql` to the
  `attractions` DB before running the generator.
