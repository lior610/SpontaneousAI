# "I want a different one" for utility suggestions

**Date:** 2026-08-04

## Problem

When a user opens "I need something specific right now" and picks a utility need
(Pharmacy, Medical, Grocery, Convenience, Police Emergency), the backend fetches
only the single closest matching place (`/utilities/closest` with `limit: 1`) and
returns a plain activity card. There is no way to see a different nearby location
of that same utility.

Food already solves this: it fetches a batch, caches it per trip, and the
"Suggest a different restaurant" button cycles through it. Utilities have no
equivalent.

## Goal

Add an "I want a different one" button to utility suggestion cards that cycles to
the next-closest location of the same utility category, looping back to the
closest option when the batch is exhausted.

## Approach

Mirror the existing food-intercept batch/cache pattern in the API. The engine
already returns options sorted by true distance and already accepts a `limit`, so
no engine change is required.

## Components

### Engine — no change

`POST /utilities/closest` already accepts `limit` and returns results sorted by
haversine distance (`utility_service.get_closest_utilities`). We simply request a
batch instead of a single result.

### API — utility batch cache

A per-trip utility batch cache, keyed by `tripId`, storing the requested category
so a category switch invalidates it:

```
{ category, results, currentIndex, storedAt }
```

- **On a utility `specific_need` request** (`getNextActivity`, the existing
  `specificNeed && specificNeed !== 'food'` branch in `tripsController.js`): fetch
  a batch (`limit: 10`) from the engine, cache it, serve `results[0]`, set
  `currentIndex = 1`. The returned card gains `card_type: 'utility'` so the
  frontend knows to show the button.
- **New endpoint `GET /:id/utility/next`**: serve `results[currentIndex]`, then
  increment. When `currentIndex >= results.length`, **loop back to index 0**
  (silent wrap-around — the button always works). If the cache is missing/stale,
  return 404 so the client falls back gracefully.
- Building the utility activity payload (id, title, description, coords, etc.) is
  shared between the initial request and `/utility/next` so both cards are
  identical in shape.

### Frontend (`TripPage.tsx` + `tripService.ts`)

- `applyActivityResult` sets a new `isUtility` flag from
  `result.card_type === 'utility'`.
- New service fn `fetchNextUtilitySuggestion(tripId)` → `GET /utility/next`,
  returning the same `NextActivityResult` shape as `fetchNextFoodSuggestion`.
- New handler `handleRefreshUtility` — reports position (consistent with the
  other handlers), calls `fetchNextUtilitySuggestion`, then `applyActivityResult`.
- **New button "I want a different one"**, shown when `isUtility`, placed directly
  **above** the "Not feeling it? Get another suggestion" skip button, styled
  identically to the sibling buttons (`RefreshCw` icon, same classes).

The existing food "Suggest a different restaurant" button and the skip/dismiss
logic are untouched. Utility skip continues to fall through to normal activities.

## Data flow

1. User picks e.g. "Pharmacy" → `fetchNextActivity(tripId, 'pharmacy')`.
2. API fetches batch of 10, caches it, returns closest as a `utility` card.
3. Card renders with the "I want a different one" button.
4. Tap → `fetchNextUtilitySuggestion` → `GET /utility/next` → next-closest card.
5. After the last option, the next tap wraps back to the closest.

## Error handling

- Engine/API failure on the initial request: log and fall through to current
  behavior (no card / normal flow), unchanged from today.
- Missing or stale cache on `/utility/next`: API returns 404; the client keeps the
  current card (no crash). A future refinement could re-fetch a fresh batch, but
  looping over the existing batch covers the common case.
- Category mismatch in cache: treated as a fresh batch on the next utility request.

## Testing

- API unit tests for the utility cache, following the food-service test style:
  serve-first, increment, loop-back at the end, and category-switch invalidation.
- Manual check: pick each utility category, confirm the button appears and cycles.
