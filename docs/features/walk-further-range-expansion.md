# Walk Further — Walking-Range Expansion

"We couldn't find anything within this distance — want to walk a bit further?"

## Problem
The engine's retrieval (`engine/src/db/cluster_queries.py`) applies a **hard
bounding-box filter** around the user's current position sized by the trip's
`max_walking_distance`, on top of open-now, not-utility/food, and not-already-seen
filters. With a small radius (e.g. 0.5 km) the reachable, open, unseen set empties
quickly. Previously an empty batch returned HTTP 404, which the web mapped to
`activity: null` and rendered as **"Trip Complete! 🎉"** — a *local* reachability
limit was indistinguishable from a *finished* trip. (A 2 km radius in New York can
exhaust after ~16 stops even though ~16,800 attractions exist city-wide.)

## Behavior
When `GET /api/trips/:id/next-activity` finds nothing in the current radius it now
returns `200 { activity: null, out_of_range: true, max_walking_distance }` instead
of a 404. The web (`web/src/pages/TripPage.tsx`) shows `WalkFurtherPrompt` offering:
- **Walk a bit further (+step km)** → `POST /api/trips/:id/expand-range`, which adds
  `WALK_EXPAND_STEP_KM` to `trips.max_walking_distance` (**persisted to the DB**),
  clears the cached recommendation batch, and returns the new radius. The client
  then refetches the next activity with the wider radius.
- **No thanks, finish my trip** → falls back to the normal trip-complete summary.

If the radius is already at `WALK_MAX_KM`, `expand-range` reports `changed: false`
and the UI shows the finish summary (genuine exhaustion).

## Key pieces
- API: `expandWalkingRange` + out-of-range branch in
  `api/src/controllers/tripsController.js`; route in `api/src/routes/trips.js`
  (`POST /:id/expand-range`). Pure math extracted to `api/src/utils/walkingRange.js`.
- Web: `web/src/components/WalkFurtherPrompt.tsx`, wiring + handlers in
  `web/src/pages/TripPage.tsx`, service `expandWalkingRange` and `outOfRange`/
  `maxWalkingDistance` fields in `web/src/services/tripService.ts`.
- Flag: `featureFlags.walkFurther { enabled, stepKm }` (`web/src/config/featureFlags.ts`).

## Config
- `WALK_EXPAND_STEP_KM` (default `1.0`) — km added per expansion.
- `WALK_MAX_KM` (default `20`) — hard ceiling (DB column caps at 99.99).
- Client step: `featureFlags.walkFurther.stepKm` (sent as `step_km`; server clamps).

## Verification
- Unit: `node --test api/tests/walkingRange.test.js` (radius math: step, ceiling,
  custom step, float drift, bad-input fallbacks).
- Manual: start a trip with a small radius (e.g. 0.5 km), exhaust it → the prompt
  appears; accepting widens the radius (verify `trips.max_walking_distance` grew in
  the DB) and more activities appear; declining shows the trip-complete summary.

## Note / follow-up
This addresses the *symptom* (false finish) and gives the user control. The deeper
lever is that the bounding box is a **hard** filter even though distance is already
scored in `engine/src/services/ranking_service.py`; a future change could make the
box a soft/last-resort filter (auto-widen when the in-box pool is small) so the
prompt is needed less often.
