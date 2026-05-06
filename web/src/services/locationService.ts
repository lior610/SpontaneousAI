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

// Send current position to backend
export async function reportPosition(tripId: number, coords: Coords): Promise<void> {
  await fetch(`${API_BASE}/api/trips/${tripId}/location`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(coords),
  });
}

// Background tracking: periodically fetches GPS and reports to backend
let trackingInterval: ReturnType<typeof setInterval> | null = null;

export function startTracking(tripId: number, intervalMs = 5 * 60 * 1000): void {
  stopTracking();
  const sync = async () => {
    const coords = await getCurrentPosition();
    if (coords) {
      reportPosition(tripId, coords).catch(() => {});
    }
  };
  sync();
  trackingInterval = setInterval(sync, intervalMs);

  // Pause when tab is hidden, resume when visible
  document.addEventListener('visibilitychange', handleVisibility);
}

export function stopTracking(): void {
  if (trackingInterval) {
    clearInterval(trackingInterval);
    trackingInterval = null;
  }
  document.removeEventListener('visibilitychange', handleVisibility);
}

function handleVisibility() {
  if (document.hidden && trackingInterval) {
    clearInterval(trackingInterval);
    trackingInterval = null;
  }
}
