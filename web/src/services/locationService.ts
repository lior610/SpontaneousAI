// Frontend location service: GPS acquisition and periodic background sync to backend
import { API_BASE } from '@/config';

export interface Coords {
  lat: number;
  lng: number;
}

// Request browser GPS position (one-shot)
export function getCurrentPosition(): Promise<Coords | null> {
  return new Promise((resolve) => {
    if (!navigator.geolocation) {
      resolve(null);
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
      (err) => {
        console.warn('[LocationService] GPS failed:', err.message);
        resolve(null);
      },
      { enableHighAccuracy: false, timeout: 10000 }
    );
  });
}

// Send current position to backend (includes user_id for ownership check)
export async function reportPosition(tripId: number, coords: Coords): Promise<void> {
  const rawUser = window.localStorage.getItem('currentUser');
  const userId = rawUser ? JSON.parse(rawUser).id : undefined;
  const res = await fetch(`${API_BASE}/api/trips/${tripId}/location`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...coords, user_id: userId }),
  });
  if (!res.ok) {
    console.warn(`[LocationService] Position update failed: ${res.status}`);
  }
}

// Background tracking: periodically fetches GPS and reports to backend
let trackingInterval: ReturnType<typeof setInterval> | null = null;

export function startTracking(tripId: number, intervalMs = 5 * 60 * 1000): void {
  stopTracking();
  _trackingTripId = tripId;
  _trackingIntervalMs = intervalMs;
  const sync = async () => {
    const coords = await getCurrentPosition();
    if (coords) {
      reportPosition(tripId, coords).catch(() => {});
    }
  };
  sync();
  trackingInterval = setInterval(sync, intervalMs);

  document.addEventListener('visibilitychange', handleVisibility);
}

export function stopTracking(): void {
  if (trackingInterval) {
    clearInterval(trackingInterval);
    trackingInterval = null;
  }
  _trackingTripId = null;
  document.removeEventListener('visibilitychange', handleVisibility);
}

let _trackingTripId: number | null = null;
let _trackingIntervalMs = 5 * 60 * 1000;

// Pause GPS polling when tab is hidden, resume when visible again
function handleVisibility() {
  if (document.hidden && trackingInterval) {
    clearInterval(trackingInterval);
    trackingInterval = null;
  } else if (!document.hidden && !trackingInterval && _trackingTripId) {
    const tripId = _trackingTripId;
    const sync = async () => {
      const coords = await getCurrentPosition();
      if (coords) {
        reportPosition(tripId, coords).catch(() => {});
      }
    };
    sync();
    trackingInterval = setInterval(sync, _trackingIntervalMs);
  }
}
