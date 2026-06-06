---
name: Auto "Didn't Like" via Location Tracking
overview: "Replace the manual like/didn't-like prompt with automatic dissatisfaction detection: a GPS geofence measures how long a user actually stays at an attraction, and an LLM (Gemini) estimates how long they should stay. A short visit is inferred as 'didn't like'. The popup is kept but trimmed to Like / Skip / Next, where Next defers to the location-based inference."
branch: didn't-like-feature
todos:
  - id: schema
    content: "Add place_id, arrived_at, duration_minutes, recommended_stay_minutes to trip_activity_logs; recommended_stay_minutes to attractions (CREATE TABLE in init.sql)"
    status: completed
  - id: gemini-service
    content: "Create api/src/services/recommendedStay.js: Gemini call for recommended stay, cached per attraction (memory + DB)"
    status: completed
  - id: controller
    content: "Update completeTripActivity: compute dwell time, infer negative-only signal, persist new columns"
    status: completed
  - id: geofence
    content: "Add watchArrivalDeparture geofence (haversine + hysteresis) to web locationService"
    status: completed
  - id: popup
    content: "Trim FeedbackPopup to Like / Skip / Next and wire it into TripPage"
    status: completed
  - id: env
    content: "Single root .env loading for api + web; Gemini config"
    status: completed
isProject: false
---

# Auto "Didn't Like" via Location Tracking

## What This Delivers

The app no longer asks the user to manually rate an attraction as "didn't like". Instead it **infers dissatisfaction from behavior**: if a user leaves an attraction much sooner than a typical visitor would, that's treated as a negative signal. A small popup is still shown after a visit, but with only **Liked it / Skip / Next**:

| Choice | Meaning | Engine signal |
| ------ | ------- | ------------- |
| **Liked it** | Explicit positive | `liked` |
| **Skip** | Explicit negative ("show fewer like this") | `skipped` |
| **Next** | No opinion → defer to location inference | `liked` / `visited` (derived) |

**Core rule (negative-only inference):** the location feature can only ever produce a *negative* signal.
- Stayed **less than** `STAY_DISLIKE_RATIO` × recommended time → `liked: false` (auto-detected "didn't like").
- Stayed **long enough** → **no opinion** (`liked` left unset / neutral). Staying long does *not* imply they liked it.

---

## End-to-End Flow

```
User gets attraction (web → api → engine recommendation)
        │
        ├─ GPS geofence starts watching the attraction coords
        │      ├─ enters arrival radius  → record arrived_at
        │      └─ leaves departure radius → open the feedback popup
        │
User taps "Done" OR geofence departure → popup (Like / Skip / Next)
        │
        ▼
POST /api/trips/:id/activities/complete  { arrived_at, completed_at, feedback?, place_id, ... }
        │
   duration_minutes = completed_at − arrived_at
        │
   if no explicit Like/Skip (the "Next" path):
        ├─ recommendedStay.getRecommendedStayMinutes(place)   ── Gemini, cached per attraction
        └─ if duration < ratio × recommended → feedback.liked = false (autoDetected)
        │
   persist row in trip_activity_logs (+ new columns)
        └─ forward to engine /recommendations/feedback (liked | skipped | visited)
```

---

## Database Schema

**File:** `[database/init.sql](database/init.sql)`

New columns are defined directly in the `CREATE TABLE` statements (no `ALTER` — `init.sql` is meant to run on a clean database).

**`client_info.trip_activity_logs`** (the per-visit log):

| Column | Type | Purpose |
| ------ | ---- | ------- |
| `place_id` | TEXT | Attraction id (previously not stored on the log) |
| `arrived_at` | TIMESTAMPTZ | When the geofence detected arrival |
| `duration_minutes` | INTEGER | Measured dwell time (arrival → completion) |
| `recommended_stay_minutes` | INTEGER | The LLM's estimate at the time of the visit |

**`attractions.attractions`** (the LLM cache):

| Column | Type | Purpose |
| ------ | ---- | ------- |
| `recommended_stay_minutes` | INTEGER | Cached Gemini answer so we ask the LLM at most once per place |

---

## Backend

### Recommended-stay service (the LLM)

**File:** `[api/src/services/recommendedStay.js](api/src/services/recommendedStay.js)`

`getRecommendedStayMinutes({ placeId, name, category, description, address })` answers *"how long should a typical visitor stay here?"* with a 3-layer lookup so Gemini is called at most once per attraction:

1. **In-memory cache** (`Map`, per process) — fast path.
2. **`attractions.recommended_stay_minutes`** — persists across restarts; also used to fetch attraction details if the caller didn't pass them.
3. **Gemini call** — only on a full miss; result is written back to both caches.

Implementation notes:
- Calls the Gemini REST API with `axios` (no new SDK dependency).
- Model from `GEMINI_MODEL` (default `gemini-2.5-flash`).
- `generationConfig: { temperature: 0, maxOutputTokens: 256, thinkingConfig: { thinkingBudget: 0 } }` — `thinkingBudget: 0` disables "thinking" on Gemini 2.5 models; otherwise the output budget is consumed by hidden reasoning tokens and the answer comes back empty.
- Output is parsed to an integer and clamped to a sane range (5–480 min).
- On any failure (missing key, quota, bad response) it returns `null`, and the caller simply records dwell time without an inference.

### Completion logic

**File:** `[api/src/controllers/tripsController.js](api/src/controllers/tripsController.js)` → `completeTripActivity`

- Accepts `arrived_at` in the body and computes `durationMinutes = completed_at − arrived_at`.
- `hasExplicitLiked` is true when the popup sent `feedback.liked` (Like or Skip). In that case the LLM is **not** called.
- Otherwise (the "Next" path) it calls the recommended-stay service and applies the **negative-only** rule:

```js
// Location tracking only infers a NEGATIVE signal: a short stay means the user
// likely didn't enjoy it. Staying long enough does NOT imply they liked it.
if (recommendedStayMinutes != null && durationMinutes < recommendedStayMinutes * STAY_DISLIKE_RATIO) {
  derivedFeedback = { ...(derivedFeedback || {}), liked: false, autoDetected: true };
}
```

- Always records `duration_minutes` / `recommended_stay_minutes` (and `recommendedStayMinutes` inside the `feedback` JSONB) even when no opinion is derived.
- Forwards to the engine: `liked === true → liked`, `liked === false → skipped`, otherwise `visited`.

`STAY_DISLIKE_RATIO` (default `0.5`) is read from env at the top of the controller.

---

## Frontend

### Geofence (location tracking)

**File:** `[web/src/services/locationService.ts](web/src/services/locationService.ts)`

- `distanceMeters(a, b)` — haversine distance in meters.
- `watchArrivalDeparture(target, opts)` — subscribes to `navigator.geolocation.watchPosition` and runs a small state machine against the attraction:
  - **arrive** when distance ≤ `arriveRadiusM` (default **120 m**) → fires `onArrive`.
  - **depart** (only after arrival) when distance ≥ `departRadiusM` (default **180 m**) → fires `onDepart`.
  - Two radii (hysteresis) prevent GPS jitter from flapping enter/exit near the boundary.
  - Returns a cleanup function that clears the watch.

### Trip page wiring

**File:** `[web/src/pages/TripPage.tsx](web/src/pages/TripPage.tsx)`

- A geofence is started for the current attraction (when `VITE_GPS_ENABLED === 'on'`). `onArrive` records `arrivedAtRef`; `onDepart` opens the popup. The watcher is torn down / reset when the attraction changes.
- `handleActivityComplete` (the "Done" button) opens the popup; `handleFeedbackSubmit(choice)` maps the choice to feedback and calls `finishActivity`:
  - `liked` → `{ liked: true }`
  - `skipped` → `{ liked: false }`
  - `next` → `undefined` (lets the backend infer from dwell time)
- `finishActivity(feedback)` posts the completion (with `arrivedAt`), refreshes the completed list, resets arrival state, and fetches the next attraction.
- A small banner shows **only after arrival**: "You've arrived — we'll ask how it went when you leave."

### Popup

**File:** `[web/src/components/FeedbackPopup.tsx](web/src/components/FeedbackPopup.tsx)`

Trimmed to three actions — **Liked it / Skip / Next** — emitting a `FeedbackChoice` (`'liked' | 'skipped' | 'next'`). The old "didn't like / too long / too far / too expensive" options were removed.

### Service + types

- `[web/src/services/tripService.ts](web/src/services/tripService.ts)` — `completeActivity(tripId, activity, { arrivedAt, feedback })` now sends `arrived_at` and an optional `feedback`.
- `[web/src/types/trip.ts](web/src/types/trip.ts)` — `Activity.feedback` extended with `autoDetected`, `durationMinutes`, `recommendedStayMinutes`.

---

## Configuration & Local Run

### Single root `.env`

The project keeps **one** `.env` at the repo root.

- `[api/src/loadEnv.js](api/src/loadEnv.js)` loads `../../.env` and is the first import in `[api/src/index.js](api/src/index.js)` (so it runs before the DB pools read `process.env`).
- `[web/vite.config.js](web/vite.config.js)` sets `envDir` to the repo root so Vite reads the same file.

### Relevant env vars (`.env`)

| Var | Purpose |
| --- | ------- |
| `GEMINI_API_KEY` | Gemini key used by the recommended-stay service |
| `GEMINI_MODEL` | Default `gemini-2.5-flash` (`gemini-2.0-flash` had `limit: 0` quota on the test key) |
| `STAY_DISLIKE_RATIO` | Fraction of recommended time below which a visit is "didn't like" (default `0.5`) |
| `VITE_GPS_ENABLED` | `on` enables the arrival/departure geofence (and map GPS) |
| `PG_CONNECTION_TIMEOUT_MS` | DB pool connect timeout (default raised to `15000`; the remote DB handshake exceeds the old 2 s) |

DB pool timeout change applies to `[api/src/db/connection.js](api/src/db/connection.js)`, `[api/src/db/usersConnection.js](api/src/db/usersConnection.js)`, and `[api/src/db/attractionsConnection.js](api/src/db/attractionsConnection.js)`.

### Running locally (no Docker)

```bash
# engine (FastAPI) — needs shared/python on the path
cd engine && PYTHONPATH="$(pwd):$(pwd)/../shared/python" python3 -m uvicorn src.main:app --host 0.0.0.0 --port 8000

# api (Express)
cd api && npm run dev          # http://localhost:3000

# web (Vite)
cd web && npm run dev          # http://localhost:5173
```

---

## How to Test

**Browser (simulated GPS):** DevTools → Sensors → Location. Set coordinates on the attraction (triggers arrival), then move far away after a short time → the popup opens → choose **Next** → it's auto-marked "didn't like".

**Deterministic (curl, bypasses GPS):** send `arrived_at` directly with no `feedback` (the "Next" path):

```bash
# short stay -> liked:false (didn't like)
curl -s -X POST http://localhost:3000/api/trips/19/activities/complete -H "Content-Type: application/json" \
  -d "{\"title\":\"Little Island\",\"category\":\"park\",\"place_id\":\"5e6fb8a3caec930008ad10f6\",\"arrived_at\":\"$(date -u -v-5M +%Y-%m-%dT%H:%M:%SZ)\",\"lat\":40.742,\"lng\":-74.0105}"

# long stay -> no liked key (neutral)
curl -s -X POST http://localhost:3000/api/trips/19/activities/complete -H "Content-Type: application/json" \
  -d "{\"title\":\"Little Island\",\"category\":\"park\",\"place_id\":\"5e6fb8a3caec930008ad10f6\",\"arrived_at\":\"$(date -u -v-300M +%Y-%m-%dT%H:%M:%SZ)\",\"lat\":40.742,\"lng\":-74.0105}"
```

Verified behavior:
- Geofence replay: arrival at ~90 m, departure at ~300 m, correct dwell time.
- Short stay (5 m / rec 60 m) → `liked: false, autoDetected: true`.
- Long stay (300 m / rec 60 m) → neutral (no `liked`).
- Back-to-back loop (recommendation → short-stay completion → next) across 5 different attractions, each with its own cached recommended stay, no repeats.

---

## Files Changed

**Added**
- `[api/src/services/recommendedStay.js](api/src/services/recommendedStay.js)`
- `[api/src/loadEnv.js](api/src/loadEnv.js)`

**Modified**
- `[api/src/controllers/tripsController.js](api/src/controllers/tripsController.js)`
- `[api/src/index.js](api/src/index.js)`
- `[api/src/db/connection.js](api/src/db/connection.js)`, `[api/src/db/usersConnection.js](api/src/db/usersConnection.js)`, `[api/src/db/attractionsConnection.js](api/src/db/attractionsConnection.js)`
- `[database/init.sql](database/init.sql)`
- `[web/src/pages/TripPage.tsx](web/src/pages/TripPage.tsx)`
- `[web/src/components/FeedbackPopup.tsx](web/src/components/FeedbackPopup.tsx)`
- `[web/src/services/locationService.ts](web/src/services/locationService.ts)`
- `[web/src/services/tripService.ts](web/src/services/tripService.ts)`
- `[web/src/types/trip.ts](web/src/types/trip.ts)`
- `[web/vite.config.js](web/vite.config.js)`
- `.env.example`
