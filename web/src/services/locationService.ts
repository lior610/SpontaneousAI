// Frontend location service: GPS acquisition and periodic background sync to backend
import { Capacitor } from '@capacitor/core';
import { Geolocation } from '@capacitor/geolocation';
import { API_BASE } from '@/config';
import { sendArrivalNotification, sendDepartureNotification } from './nativeNotificationService';

export interface Coords {
  lat: number;
  lng: number;
}

// Distance between two coordinates in meters (haversine).
export function distanceMeters(a: Coords, b: Coords): number {
  const R = 6371000;
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const lat1 = toRad(a.lat);
  const lat2 = toRad(b.lat);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

export interface GeofenceOptions {
  arriveRadiusM?: number;
  departRadiusM?: number;
  attractionName?: string;
  onArrive?: (coords: Coords) => void;
  onDepart?: (coords: Coords) => void;
  onPosition?: (coords: Coords) => void;
}

/**
 * Watches the user's GPS position relative to a target attraction and fires
 * onArrive when they enter the arrival radius, then onDepart once they leave
 * the (larger) departure radius. Departure only fires after an arrival, so the
 * time between the two callbacks is the actual dwell time at the attraction.
 *
 * Returns a cleanup function that stops watching.
 */
export function watchArrivalDeparture(target: Coords, opts: GeofenceOptions = {}): () => void {
  const arriveRadiusM = opts.arriveRadiusM ?? 120;
  const departRadiusM = opts.departRadiusM ?? Math.max(arriveRadiusM + 60, 180);
  const name = opts.attractionName || 'your destination';

  let hasArrived = false;
  let departed = false;

  // Handler callback for position updates
  const handlePosition = (coords: Coords) => {
    opts.onPosition?.(coords);
    const d = distanceMeters(coords, target);

    if (!hasArrived && d <= arriveRadiusM) {
      hasArrived = true;
      opts.onArrive?.(coords);
      sendArrivalNotification(
        `Arrived at ${name}`,
        `You are within ${Math.round(d)}m of ${name}. Enjoy your visit!`
      );
    } else if (hasArrived && !departed && d >= departRadiusM) {
      departed = true;
      opts.onDepart?.(coords);
      sendDepartureNotification(
        `Departed ${name}`,
        `You have left ${name}. Ready for your next stop?`
      );
    }
  };

  // Capacitor Native continuous background location watch
  if (Capacitor.isNativePlatform()) {
    let watchIdPromise: Promise<string> = Geolocation.watchPosition(
      { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 },
      (position, err) => {
        if (err || !position) {
          console.warn('[LocationService] Native Geolocation watch failed:', err);
          return;
        }
        handlePosition({ lat: position.coords.latitude, lng: position.coords.longitude });
      }
    );

    return () => {
      watchIdPromise.then((id) => Geolocation.clearWatch({ id }));
    };
  }

  // Web Browser fallback
  if (typeof navigator === 'undefined' || !navigator.geolocation) {
    return () => {};
  }

  const watchId = navigator.geolocation.watchPosition(
    (pos) => {
      handlePosition({ lat: pos.coords.latitude, lng: pos.coords.longitude });
    },
    (err) => {
      console.warn('[LocationService] Web Geofence watch failed:', err.message);
    },
    { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 }
  );

  return () => navigator.geolocation.clearWatch(watchId);
}

// Request browser/native GPS position (one-shot)
export async function getCurrentPosition(): Promise<Coords | null> {
  if (Capacitor.isNativePlatform()) {
    try {
      const pos = await Geolocation.getCurrentPosition({ enableHighAccuracy: true, timeout: 10000 });
      return { lat: pos.coords.latitude, lng: pos.coords.longitude };
    } catch (err) {
      console.warn('[LocationService] Native GPS failed:', err);
      return null;
    }
  }

  return new Promise((resolve) => {
    if (typeof navigator === 'undefined' || !navigator.geolocation) {
      resolve(null);
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
      (err) => {
        console.warn('[LocationService] GPS failed:', err.message);
        resolve(null);
      },
      { enableHighAccuracy: false, timeout: 3000 }
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
let _trackingTripId: number | null = null;
let _trackingIntervalMs = 5 * 60 * 1000;

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

  if (typeof document !== 'undefined') {
    document.addEventListener('visibilitychange', handleVisibility);
  }
}

export function stopTracking(): void {
  if (trackingInterval) {
    clearInterval(trackingInterval);
    trackingInterval = null;
  }
  _trackingTripId = null;
  if (typeof document !== 'undefined') {
    document.removeEventListener('visibilitychange', handleVisibility);
  }
}

// Pause GPS polling when tab is hidden (browser only), resume when visible again
function handleVisibility() {
  if (Capacitor.isNativePlatform()) return; // Native handles background independently

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
