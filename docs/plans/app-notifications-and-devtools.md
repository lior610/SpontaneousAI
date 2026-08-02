# App Notifications & DevTools Walkthrough

This document provides a comprehensive overview of the newly implemented Notification System and the developer testing interface.

## 1. Feature Overview & Purpose

The goal of this feature was to keep users engaged and informed without requiring them to stare at the app constantly. Specifically:
1. **Trip Generation:** Notifying the user when their trip's background embedding process is fully complete and ready.
2. **Location Deviation (Next Attraction):** Automatically detecting when a user walks away from their current attraction, submitting their current progress, and notifying them of their *next* destination seamlessly.
3. **Robust Fallbacks:** Providing a fallback in-app "Toast" notification just in case the operating system (like Windows Focus Assist) blocks native push notifications.
4. **Developer Tooling:** Creating an intuitive on-screen panel to simulate GPS movement and time-of-day changes, allowing developers to test complex logic (like geofencing and LLM dwell-time inference) directly from their desk.

---

## 2. Files Edited and Added

### Frontend (`web/`)
- **[NEW]** `web/src/services/notificationService.ts`: The core service that wraps the browser's `Notification` API. It handles permission requests, manages the `/logo.svg` icon, and implements an event emitter so the UI can listen for fallback notifications.
- **[NEW]** `web/src/components/NotificationProvider.tsx`: A wrapper component that does two things:
  1. Establishes a Server-Sent Events (SSE) connection to the backend to listen for real-time events.
  2. Renders the custom "Toast" overlay UI whenever a notification is triggered.
- **[NEW]** `web/src/components/DevToolsPanel.tsx`: A floating control panel (visible only in development mode) that allows developers to trigger test notifications, spoof GPS coordinates, and mock the current hour.
- **[MODIFIED]** `web/src/App.tsx`: Updated to wrap the entire application in the `<NotificationProvider>` and to mount the `<DevToolsPanel>`.
- **[MODIFIED]** `web/src/pages/TripPage.tsx`: Hooked into the existing `watchArrivalDeparture` logic. When the `onDepart` geofence event fires, it automatically completes the current activity in the background and triggers the new notification: *"Next Destination Ready"*.
- **[MODIFIED]** `web/src/services/tripService.ts`: Updated `fetchNextActivity` and `completeActivity` to intercept the `mockTime` from the DevTools state. If a mock time is set, it passes it to the backend to simulate recommendations for that specific hour.

### Backend (`api/`)
- **[NEW]** `api/src/services/notificationService.js`: A lightweight registry that keeps track of active SSE HTTP connections mapped by `user_id`, allowing the server to push events to specific users.
- **[NEW]** `api/src/routes/notifications.js`: Exposes the `GET /api/notifications/stream` endpoint, which keeps an open HTTP connection using `text/event-stream`.
- **[MODIFIED]** `api/src/routes/index.js`: Registered the new `/notifications` router.
- **[MODIFIED]** `api/src/services/preferenceEmbedding.js`: Modified the background promise. Once the engine successfully finishes building the embeddings, it calls the `notificationService` to push a `TRIP_GENERATED` event to the client.
- **[MODIFIED]** `api/src/controllers/tripsController.js`: Updated the recommendation endpoints to accept the `mock_time` query parameter from the frontend, forwarding it to the Python engine as the `current_time` and `current_hour`.

---

## 3. How to Use the DevTools Panel

When running the app in development mode (`npm run dev`), you will see a small `🛠️` icon floating in the bottom-left corner of the screen. Clicking it opens the DevTools Panel.

### Testing Notifications
> [!TIP]
> **Test Base Notification**: Clicking this button will instantly trigger `showAppNotification()`. 
> - If your OS permits it, a native desktop notification will slide in.
> - Regardless of OS settings, the custom in-app Toast will slide in from the top right.

### Simulating GPS (Location Deviation)
The GPS simulation monkey-patches the browser's native `navigator.geolocation` API, meaning the app *thinks* you are physically moving.
1. Start a trip and arrive at an attraction.
2. In the DevTools panel, enter new `Lat` and `Lng` coordinates that are far away from your current location (e.g., beyond the 180m departure radius).
3. Click **Set GPS Location**.
4. The geofence's `onDepart` listener will instantly trigger, auto-completing your current activity and popping a notification with your next generated destination!

### Simulating Time
The Python engine recommends different places depending on the time of day (e.g., no parks at 2 AM).
1. In the DevTools panel, select a specific time (HH:MM).
2. Click **Set Time**.
3. Now, whenever the app fetches the next activity (either manually or via the GPS simulator), it will send this mock time to the backend. The engine will generate recommendations as if it is currently that exact time!
4. To turn off time simulation, clear the input box and click **Set Time** again.
