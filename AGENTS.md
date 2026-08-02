# AGENTS

Documentation index for durable, reusable context in this repo.
All durable docs live under [`docs/`](docs/) (features, plans, testing).

## Feature docs
- [Popular-Trip Algo Branch Overview](docs/features/popular-trip-algo-overview.md) —
  map of everything on `popular-trip-algo`: features, TripPage composition,
  deploy checklist, verification, and file index. Start here for that branch.
- [Popular Trips + Companion Suggestions](docs/features/popular-trips-companion-suggestions.md) —
  one-time LLM-generated, persona-tagged popular-trips pool and the runtime
  "because you liked X, you might also like Y" suggestion flow.
- [Walk Further — Walking-Range Expansion](docs/features/walk-further-range-expansion.md) —
  when nothing is reachable within the trip's walking radius, offer to widen it
  (persisted to the DB) instead of prematurely showing "Trip Complete".
- [Food Attractions Handling](docs/features/food-attractions-handling.md) —
  food is excluded from the normal recommendation stream and surfaces only via
  the Food Intercept layer (rules + LLM meal-break).

## Design plans
- [Attraction Engine Design](docs/plans/attraction-engine-design.md) —
  cluster-diverse recommendation engine with dynamic preference embeddings.
- [User Preference Embedding](docs/plans/user-preference-embedding.md) —
  how historical / trip / real-time preference vectors are composed.
- [App Notifications + DevTools](docs/plans/app-notifications-and-devtools.md) —
  geofence notifications and the DevTools simulator.
- [Auto-Dislike via Location Tracking](docs/plans/auto-dislike-location-tracking.md) —
  dwell-time inference when the user leaves an attraction early.

## Testing
- [DevTools Integration Test Cases](docs/testing/dev-tools-test-cases.md) —
  manual scenarios for dwell-time inference, geofence notifications, and DevTools.
