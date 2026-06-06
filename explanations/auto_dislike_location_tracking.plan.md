---
name: New Feedback Popup & Logic
overview: "The post-visit prompt is trimmed to Like / Skip / Next. Like and Skip are explicit signals; Next defers to automatic, location-based inference that only ever marks an attraction as 'didn't like' (a short stay), never as liked."
branch: didn't-like-feature
isProject: false
---

# New Feedback Popup & Logic

## The Popup

After a visit, the user sees a small popup with **three** choices (the old "didn't like / too long / too far / too expensive" options were removed):

**File:** `[web/src/components/FeedbackPopup.tsx](web/src/components/FeedbackPopup.tsx)`

| Button | Meaning |
| ------ | ------- |
| **Liked it** | The user explicitly enjoyed the attraction. |
| **Skip** | Explicit negative — "show me fewer like this". |
| **Next** | No opinion given — let the app decide automatically from how long they stayed. |

The popup emits a single `FeedbackChoice` value: `'liked' | 'skipped' | 'next'`.

It opens when the user taps **Done** on the activity card, or (when GPS is enabled) automatically when the geofence detects they've left the attraction.

---

## The Feedback Logic

`[web/src/pages/TripPage.tsx](web/src/pages/TripPage.tsx)` maps the choice to a feedback object and submits it:

| Choice | Sent feedback | Result |
| ------ | ------------- | ------ |
| `liked` | `{ liked: true }` | Explicit like |
| `skipped` | `{ liked: false }` | Explicit dislike |
| `next` | *(none)* | Backend infers from dwell time |

The backend (`[api/src/controllers/tripsController.js](api/src/controllers/tripsController.js)` → `completeTripActivity`) then decides the final signal:

1. **Explicit choice (Like / Skip):** `feedback.liked` is already set, so it's used as-is. No inference runs.
2. **Next (no explicit choice):** the app measures the **dwell time** (how long the user actually stayed) and asks the LLM how long a visitor *should* stay, then applies the **negative-only rule**:

```js
// A short stay implies the user didn't enjoy it. Staying long enough does NOT
// imply they liked it — in that case we leave `liked` unset (neutral).
if (recommendedStayMinutes != null && durationMinutes < recommendedStayMinutes * STAY_DISLIKE_RATIO) {
  derivedFeedback = { ...(derivedFeedback || {}), liked: false, autoDetected: true };
}
```

### The negative-only rule

The automatic path can **only ever produce a negative signal**:

| Dwell time vs. recommended | Inferred feedback |
| -------------------------- | ----------------- |
| Stayed **less than** `STAY_DISLIKE_RATIO` × recommended (default 50%) | `liked: false` (auto-detected "didn't like") |
| Stayed **long enough** | **No opinion** — `liked` left unset (neutral) |

A long visit is intentionally *not* counted as a like — only an unusually short visit is meaningful.

### Resulting engine signal

The derived feedback is forwarded to the recommendation engine:

| `feedback.liked` | Engine action |
| ---------------- | ------------- |
| `true` | `liked` |
| `false` | `skipped` |
| unset | `visited` (neutral) |

---

## Dwell Time & GPS Mechanism

The "Next" inference needs two numbers: **how long the user actually stayed** (dwell time, measured by GPS) and **how long they should stay** (recommended time, from the LLM). Everything below is how those are produced and compared.

```
   GPS stream (watchPosition)                    LLM (Gemini, cached per attraction)
            │                                                  │
   ┌────────┴─────────┐                                        │
   │ distance ≤ 120 m │ → arrive → save arrived_at             │
   │ distance ≥ 180 m │ → depart → open popup                  │
   └────────┬─────────┘                                        │
            │  (1) dwell time                       (3) recommended time
            ▼                                                  ▼
   duration = completed_at − arrived_at        recommendedStayMinutes (5–480)
            │                                                  │
            └──────────────► (4) compare ◄─────────────────────┘
                                  │
              threshold = recommended × STAY_DISLIKE_RATIO (0.5)
                                  │
                duration < threshold ?  ── yes ─► liked = false ("didn't like")
                                         ── no  ─► neutral (no opinion)
```


### 1. GPS geofence — detecting arrival and departure

**File:** `[web/src/services/locationService.ts](web/src/services/locationService.ts)`

Each attraction is treated as a circular geofence around its coordinates. While an attraction is showing, the app subscribes to the browser's live position stream (`navigator.geolocation.watchPosition`) and, on every position update, measures the straight-line distance to the attraction.

**Distance** uses the haversine formula (great-circle distance on a sphere, Earth radius `R = 6 371 000 m`):

```
a = sin²(Δφ/2) + cos(φ₁)·cos(φ₂)·sin²(Δλ/2)
distance = 2R · asin(√a)          // result in meters
```

where `φ` is latitude and `λ` is longitude (in radians).

A small state machine then fires two events using **two radii** (hysteresis):

| Event | Condition | Default radius |
| ----- | --------- | -------------- |
| **arrive** | distance ≤ `arriveRadiusM` | **120 m** |
| **depart** | (only after arrival) distance ≥ `departRadiusM` | **180 m** |

Two different radii prevent GPS jitter from flapping enter/exit when the user is standing near the boundary: you must move clearly away (past 180 m) before "left" registers. Departure can only fire after arrival, so the window between the two events is a real visit.

On **arrive**, the app stores the current time as `arrived_at`. On **depart**, it opens the feedback popup. (The geofence runs only when `VITE_GPS_ENABLED=on`; otherwise the user just taps **Done** and no dwell time is measured.)

### 2. Dwell time — how long they stayed

When the visit is completed, the frontend sends `arrived_at` (set at the arrival event) and `completed_at` (now). The backend computes:

```
duration_minutes = round( (completed_at − arrived_at) / 60000 )
```

If there is no `arrived_at` (e.g. GPS off), `duration_minutes` is `null` and no inference is attempted.

### 3. Recommended time — how long they *should* stay (LLM)

**File:** `[api/src/services/recommendedStay.js](api/src/services/recommendedStay.js)`

`getRecommendedStayMinutes()` asks Gemini *"how many minutes should a typical visitor stay here?"* for the attraction (name, category, description, address). The answer is parsed to an integer and clamped to **5–480 minutes** to guard against bad output.

It is cached so the LLM is called **at most once per attraction**, via a 3-layer lookup:

1. In-memory cache (per process).
2. `attractions.recommended_stay_minutes` column (survives restarts).
3. Gemini call — only on a full miss; the result is written back to both caches.

If the LLM is unavailable (no key, quota, empty response) it returns `null`, and the backend records the dwell time without inferring anything.

### 4. The comparison — putting it together

With both numbers, the negative-only threshold is:

```
threshold       = recommendedStayMinutes × STAY_DISLIKE_RATIO   // default ratio = 0.5
didn't_like     = durationMinutes < threshold
```

- If `didn't_like` is true → `feedback.liked = false` (`autoDetected: true`).
- Otherwise → no opinion (neutral).

**Worked example** — a museum with `recommendedStayMinutes = 90` and `STAY_DISLIKE_RATIO = 0.5`:

| Actual stay | threshold (45 min) | Result |
| ----------- | ------------------ | ------ |
| 20 min | below | `liked: false` ("didn't like") |
| 30 min | below | `liked: false` |
| 60 min | above | neutral (no opinion) |
| 120 min | above | neutral (no opinion) |

`STAY_DISLIKE_RATIO` (env, default `0.5`) is the single knob controlling how short a visit must be to count as a dislike.
