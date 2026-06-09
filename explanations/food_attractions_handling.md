# How Food Attractions Are Handled

Food is treated **differently from every other attraction**. Restaurants, cafés, bakeries etc. are **never** mixed into the normal recommendation stream. Instead they surface only through a dedicated **Food Intercept** layer that occasionally interrupts the regular flow to suggest a meal break.

---

## The Core Idea

| Normal attractions | Food |
| ------------------ | ---- |
| Returned by the recommendation engine, cycled through one-by-one. | **Excluded** from those recommendations entirely. |
| Always available. | Only shown when it's plausibly *meal time* and the user seems due for a break. |
| — | Decision is gated by cheap rules first, then confirmed by an LLM. |

---

## 1. Food is excluded from regular recommendations

**File:** `[engine/src/db/cluster_queries.py](engine/src/db/cluster_queries.py)` (~line 131)

Every recommendation query checks `category_filter`:

- **No `food` filter (normal recs):** the query adds `AND NOT (...)` to **strip out** anything in the food category list or with `"restaurant"` in its category name.
- **`category_filter == 'food'` (intercept):** the same condition is **inverted** to return *only* food.

The food category list lives in `[engine/src/services/utility_service.py](engine/src/services/utility_service.py)` as `UTILITY_CATEGORY_MAP['food']` (Restaurant, Cafe, Coffee Shop, Bakery, Pizza Place, …). Food sits in the `attraction` table (it is *not* a "utility"), but is matched by category.

---

## 2. The Food Intercept decision flow

**File:** `[api/src/services/foodInterceptService.js](api/src/services/foodInterceptService.js)`

Runs on every "get next activity" request (unless a `specific_need` like *pharmacy* is set). Steps, each of which can silently fall through to the normal flow:

```
enabled? → has position? → cooldowns clear? → gate (2-of-3) → LLM yes/no → fetch food batch → serve card
```

### The  conditions (cheap, run first)

`evaluateGateConditions(...)` — **2 of these 3** must be true to even consider asking the LLM:

| # | Condition | Default |
| - | --------- | ------- |
| 1 | **Meal window** — local time is 11:30–14:00 or 17:30–20:30 | hard-coded windows |
| 2 | **Activity count** — N+ activities done since last food | `FOOD_ACTIVITY_THRESHOLD = 2` |
| 3 | **Time elapsed** — N+ hours since last food | `FOOD_HOURS_THRESHOLD = 3` |

If there was no food yet today, "since last food" falls back to counting from the first activity of the day (or now).

### The LLM confirmation (Gemini)

If the gate passes, `callLlmValidation(...)` asks **Gemini 2.5 Flash** a strict yes/no: given today's activities and the current local time, *is a food break appropriate right now?* Any error → treated as "no".

This hybrid design avoids an LLM call on every request — the gate filters out the obvious "no"s cheaply.

---

## 3. Cooldowns & state (in-memory, per trip)

| State map | Set when | Effect |
| --------- | -------- | ------ |
| `foodDismissalCooldowns` | User dismisses a food card | Suppress intercept for `FOOD_COOLDOWN_MS` (default **1 h**) |
| `foodLlmDeclineCooldowns` | LLM says "no", **or** no food places found | Don't re-ask the LLM for the cooldown (gate barely changes between skips) |
| `foodBatchCache` | A batch is fetched | Holds the restaurants for cycling through |

**Key nuance:** completing a *real* activity calls `clearLlmDeclineCooldown(tripId)` — finishing something changes the context (one more activity, time passed), so the LLM is allowed to reconsider. A plain *skip* does **not** clear it (nothing meaningful changed).

All three maps are swept periodically so they don't grow unbounded.

---

## 4. Serving & cycling food cards

- On a triggered intercept, the engine returns a **batch** of food places (`fetchFoodBatch` → engine with `category_filter: 'food'`). The first is served; the rest are cached.
- The card is shaped by `buildFoodCard(...)` with `card_type: 'food_intercept'` and `intercept_metadata` (reason, dismissable, cooldown). This is how the frontend tells it apart.
- **"Get another suggestion"** (`/food-intercept/next`) → serves the next cached restaurant; when the batch runs out it refills from the engine (`refillAndGetFood`).
- **"Skip food break"** (`/food-intercept/dismiss`) → starts the dismissal cooldown and clears the cache.

**Routes:** `[api/src/routes/trips.js](api/src/routes/trips.js)`
```
POST /api/trips/:id/food-intercept/dismiss
GET  /api/trips/:id/food-intercept/next
```

---

## 5. Frontend

**File:** `[web/src/pages/TripPage.tsx](web/src/pages/TripPage.tsx)`

- `isFoodIntercept` is set from `card_type === 'food_intercept'`.
- Food cards show an orange **"Food Break"** badge and a refresh button.
- `foodBatchExhausted` toggles UI to refill (fetch a fresh batch) or return to normal activities (`handleReturnFromFood`).

---

## Configuration (env vars)

| Variable | Default | Controls |
| -------- | ------- | -------- |
| `FOOD_INTERCEPT_ENABLED` | `true` | Master on/off (`'false'` disables) |
| `FOOD_COOLDOWN_MS` | `3600000` (1 h) | Dismissal + LLM-decline cooldown length |
| `FOOD_ACTIVITY_THRESHOLD` | `2` | Activities since last food for gate #2 |
| `FOOD_HOURS_THRESHOLD` | `3` | Hours since last food for gate #3 |
| `GEMINI_API_KEY` | — | If unset, LLM validation always returns "no" |

---

> **Design principle:** food intercept is *fail-safe*. Any failure at any step — disabled, no LLM key, engine error, empty batch — silently falls through to the normal recommendation flow. It can only ever *add* a food suggestion, never block the trip.
