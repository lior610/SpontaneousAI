# AGENTS

Documentation index for durable, reusable context in this repo.

## Feature docs
- [Popular Trips + Companion Suggestions](docs/features/popular-trips-companion-suggestions.md) —
  one-time LLM-generated, persona-tagged popular-trips pool and the runtime
  "because you liked X, you might also like Y" suggestion flow.
- [Walk Further — Walking-Range Expansion](docs/features/walk-further-range-expansion.md) —
  when nothing is reachable within the trip's walking radius, offer to widen it
  (persisted to the DB) instead of prematurely showing "Trip Complete".
