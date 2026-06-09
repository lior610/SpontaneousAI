# DevTools Integration Test Cases

This document outlines scenarios to test the combination of the newly merged **"Dwell Time Inference"** (didn't like according to time) feature, the **Geofence Notifications**, and the **DevTools Simulator**.

## Context: How Dwell Time is Calculated
When you arrive at an attraction, the frontend records your exact `arrivedAt` time using real system time. 
When you depart, the frontend calls the backend with a `completedAt` time. **Crucially, the `completedAt` time is overridden by the DevTools `mockTime` if it is set.** 
By setting the mock time into the future *before* you depart, you can artificially manipulate the exact dwell time (in minutes) that the backend evaluates!

---

### Test Case 1: Short Dwell Time (Implicit Dislike & Next Notification)
**Objective:** Verify that leaving an attraction too quickly automatically infers negative feedback (`liked: false`), and seamlessly triggers the next destination notification.

1. **Start Trip:** Have a trip active and DevTools open.
2. **Arrive:** Use DevTools to set GPS coordinates exactly at the current attraction's location. The UI should show you have arrived (the backend `arrived_at` timestamp is set using real time).
3. **Simulate Short Stay:** In DevTools, set the Mock Time to **just 5 minutes into the future**. (e.g., if it's 14:00 now, set it to 14:05).
4. **Depart:** Change the GPS coordinates to somewhere far away (e.g., Lat: 32.0, Lng: 34.0) and click **Set GPS Location**.
5. **Expected Results:**
   - The geofence detects departure and auto-submits the activity.
   - **Notification:** A native/toast notification pops up saying *"Next Destination Ready"*.
   - **Backend Inference:** The backend calculates `durationMinutes = ~5`. Since 5 minutes is likely less than `RecommendedStay * 0.5`, it infers you didn't enjoy the activity and logs it with `liked: false`.
   - **Recommendation Engine:** The engine receives a `skipped` feedback signal and adjusts the next recommendations accordingly.

---

### Test Case 2: Long Dwell Time (Neutral Feedback & Next Notification)
**Objective:** Verify that staying long enough registers as a successful visit (neutral/unset feedback, not a dislike), while still triggering the geofence notification.

1. **Arrive:** Use DevTools GPS to arrive at the newly recommended attraction.
2. **Simulate Long Stay:** In DevTools, set the Mock Time to **2 hours (120 minutes) into the future**.
3. **Depart:** Change the GPS coordinates to somewhere far away and click **Set GPS Location**.
4. **Expected Results:**
   - The activity auto-completes.
   - **Notification:** A notification pops up with the next destination.
   - **Backend Inference:** The backend calculates `durationMinutes = ~120`. Since you stayed long enough, it does NOT flag it as disliked. `liked` remains `null`/neutral.

---

### Test Case 3: Time-of-Day Context Shift
**Objective:** Verify that the mock time not only manipulates the dwell time but also directly influences the *type* of attraction recommended next.

1. **Arrive:** Use DevTools GPS to arrive at an attraction.
2. **Simulate Late Night:** Set the Mock Time to **23:30 (11:30 PM)**.
3. **Depart:** Change the GPS coordinates to somewhere far away and click **Set GPS Location**.
4. **Expected Results:**
   - **Notification:** A notification pops up with the next destination.
   - **Engine Behavior:** Because the mock time was sent to the Python engine as `current_time`, the new attraction presented in the notification should strictly be a nightlife venue, a late-night diner, or a 24/7 location (e.g., no daytime parks or museums).
