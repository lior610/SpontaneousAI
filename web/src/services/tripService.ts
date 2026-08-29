/** Trip service layer — calls the API to update user preferences (users table) and create trips (trips table). */

import { format } from 'date-fns';
import { API_BASE } from '@/config';
import { throwFetchError, throwApiError, readApiError } from '@/lib/utils';
import {
  TripSetup,
  TripPreferences,
  TripConstraints,
  Activity,
  defaultTripSetup,
} from '@/types/trip';

/** Result of saving trip setup: trip is created in DB and user preferences are updated. */
export interface SaveTripResult {
  setup: TripSetup;
  tripId: number;
}

function getCurrentUserId(): number {
  const rawUser = window.localStorage.getItem('currentUser');
  if (!rawUser) throw new Error('You must be logged in to save a trip');
  try {
    const parsed = JSON.parse(rawUser) as { id: number };
    if (typeof parsed.id !== 'number') throw new Error('Invalid user session');
    return parsed.id;
  } catch {
    throw new Error('Invalid user session. Please log in again.');
  }
}

/** Map wizard preference sliders to users table columns (for PUT /api/users/:id). */
function setupToUserPreferences(setup: TripSetup): {
  travel_style?: 'budget' | 'balanced' | 'premium';
  pace_preference?: 'slow' | 'normal' | 'fast';
} {
  const budgetPct = setup.preferences.budget;
  const pacePct = setup.preferences.pace;
  const travel_style: 'budget' | 'balanced' | 'premium' =
    budgetPct < 40 ? 'budget' : budgetPct < 70 ? 'balanced' : 'premium';
  const pace_preference: 'slow' | 'normal' | 'fast' =
    pacePct < 40 ? 'slow' : pacePct < 70 ? 'normal' : 'fast';
  return { travel_style, pace_preference };
}

/** Wizard preferences as-is, shaped for the trip's preference_breakdown column. */
function preferenceBreakdownFromSetup(setup: TripSetup): Record<string, number> {
  return { ...setup.preferences };
}

/** Update the current user's preferences in the users table (PUT /api/users/:id). Skips silently on 404 (user not in DB). */
export async function updateUserPreferences(setup: TripSetup): Promise<void> {
  const userId = getCurrentUserId();
  const body = setupToUserPreferences(setup);
  const res = await fetch(`${API_BASE}/api/users/${userId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (res.status === 404) {
    return; // User not in DB (e.g. different DB or recreated table); continue to create trip
  }
  if (!res.ok) {
    await throwFetchError(res, 'Failed to update preferences');
  }
}

// ─── Trip Setup ───────────────────────────────────────────────

export async function fetchTripSetup(): Promise<TripSetup> {
  // TODO: GET /api/trips/:id
  return { ...defaultTripSetup };
}

export async function saveTripSetup(setup: TripSetup, editTripId?: number | null): Promise<SaveTripResult> {
  const userId = getCurrentUserId();
  if (!setup.startDate || !setup.endDate || !setup.destination) {
    throw new Error('startDate, endDate, and destination are required to save a trip');
  }

  // 1) Persist user preferences to users table (skipped if user not found, e.g. 404)
  await updateUserPreferences(setup);

  // 2) Create or update trip
  const budget =
    setup.preferences.budget != null
      ? Math.round((setup.preferences.budget / 100) * 5000)
      : null;

  const tripBody = {
    user_id: userId,
    destination: setup.destination,
    start_date: format(setup.startDate, 'yyyy-MM-dd'),
    end_date: format(setup.endDate, 'yyyy-MM-dd'),
    budget,
    preference_breakdown: preferenceBreakdownFromSetup(setup),
    max_walking_distance: setup.constraints.maxWalkingDistance,
    preferred_transportation: setup.constraints.allowPublicTransit ? 'public' : 'walking',
    max_travel_time_min: setup.constraints.allowPublicTransit ? (setup.constraints.maxTravelTimeMin ?? 30) : 0,
  };

  const isEditing = typeof editTripId === 'number' && Number.isFinite(editTripId) && editTripId > 0;
  const endpoint = isEditing ? `${API_BASE}/api/trips/${editTripId}` : `${API_BASE}/api/trips`;
  const method = isEditing ? 'PUT' : 'POST';

  const res = await fetch(endpoint, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(tripBody),
  });

  if (!res.ok) {
    const { text: errorText, message: parsedError } = await readApiError(res);
    if (res.status === 404 && errorText.includes('User not found')) {
      throw new Error(
        'Your account was not found in the database. Please log out and log in again, or register if you haven’t yet.',
      );
    }
    if (res.status === 409 && parsedError) {
      throw new Error(parsedError);
    }
    throw new Error(`Failed to save trip (status ${res.status}): ${parsedError || errorText || res.statusText}`);
  }

  const data = await res.json();
  const tripId = data.trip?.trip_id ?? data.trip_id ?? (isEditing ? editTripId : null);
  if (typeof tripId !== 'number') {
    throw new Error('Server did not return a trip id');
  }

  return { setup, tripId };
}

export async function updateTripPreferences(
  preferences: Partial<TripPreferences>
): Promise<TripPreferences> {
  // TODO: PATCH /api/trips/:id/preferences
  return preferences as TripPreferences;
}

export async function updateTripConstraints(
  constraints: Partial<TripConstraints>
): Promise<TripConstraints> {
  // TODO: PATCH /api/trips/:id/constraints
  return constraints as TripConstraints;
}


// ─── Activities ───────────────────────────────────────────────

export async function fetchLocations(): Promise<{ id: string, name: string, region: string, country: string }[]> {
  try {
    const res = await fetch(`${API_BASE}/api/locations`);
    if (!res.ok) return [];
    const data = await res.json();
    return data.locations || [];
  } catch (err) {
    console.error('Failed to fetch locations', err);
    return [];
  }
}

export type { NextActivityResponse as NextActivityResult } from '@/types/trip';

import { devToolsState } from '../components/DevToolsPanel';

export async function fetchNextActivity(
  tripId?: number,
  specificNeed?: string,
  options?: { allowTransit?: boolean }
): Promise<NextActivityResult> {
  if (!tripId) return { activity: null, userLocation: null };
  
  const params = new URLSearchParams();
  if (specificNeed) params.append('specific_need', specificNeed);
  if (options?.allowTransit) params.append('allow_transit', '1');
  if (devToolsState.mockTimeEnabled) params.append('mock_time', devToolsState.mockTime);
  
  const queryString = params.toString();
  const url = queryString 
    ? `${API_BASE}/api/trips/${tripId}/next-activity?${queryString}`
    : `${API_BASE}/api/trips/${tripId}/next-activity`;

  const res = await fetch(url);
  if (!res.ok) {
    if (res.status === 404) return { activity: null, userLocation: null };
    await throwFetchError(res, 'Failed to fetch next activity');
  }
  const data = await res.json();
  return {
    activity: data.activity || null,
    userLocation: data.userLocation || null,
    card_type: data.card_type,
    intercept_metadata: data.intercept_metadata,
    outOfRange: data.out_of_range || false,
    transitAvailable: data.transit_available || false,
    maxWalkingDistance: data.max_walking_distance ?? null,
  };
}

/** Widens the trip's walking radius (persisted to DB); `changed: false` means we're already at the ceiling. */
export async function expandWalkingRange(
  tripId: number,
  stepKm?: number
): Promise<{ maxWalkingDistance: number; changed: boolean; atMax: boolean }> {
  const res = await fetch(`${API_BASE}/api/trips/${tripId}/expand-range`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(stepKm ? { step_km: stepKm } : {}),
  });
  if (!res.ok) {
    await throwFetchError(res, 'Failed to expand walking range');
  }
  const data = await res.json();
  return {
    maxWalkingDistance: Number(data.max_walking_distance),
    changed: !!data.changed,
    atMax: !!data.at_max,
  };
}

/** Enables public transit for the trip with a given max travel time cap (min). */
export async function enableTripTransit(
  tripId: number,
  maxTravelTimeMin: number = 30
): Promise<{ ok: boolean; trip_id: number; preferred_transportation: string; max_travel_time_min: number }> {
  const res = await fetch(`${API_BASE}/api/trips/${tripId}/enable-transit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ max_travel_time_min: maxTravelTimeMin }),
  });
  if (!res.ok) {
    await throwFetchError(res, 'Failed to enable public transit');
  }
  return res.json();
}

/** "Because you liked X, you might also like Y" suggestion from a matched popular trip. */
export interface CompanionSuggestion {
  activity: Activity;
  reason: string | null;
  distance_km: number | null;
}

export async function completeActivity(
  tripId: number,
  activity: Activity,
  options: { arrivedAt?: string | null; feedback?: Activity['feedback'] } = {}
): Promise<CompanionSuggestion | null> {
  if (!tripId || Number.isNaN(tripId)) {
    throw new Error('Missing trip id for activity completion');
  }
  const res = await fetch(`${API_BASE}/api/trips/${tripId}/activities/complete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title: activity.title,
      description: activity.description,
      category: activity.category,
      address: activity.address,
      estimated_time: activity.estimatedTime,
      cost: activity.cost,
      rating: activity.rating,
      review_count: activity.reviewCount,
      feedback: options.feedback ?? null,
      arrived_at: options.arrivedAt ?? null,
      completed_at: devToolsState.mockTimeEnabled ? devToolsState.mockTime : new Date().toISOString(),
      place_id: activity.id,
      lat: activity.lat,
      lng: activity.lng
    }),
  });
  if (!res.ok) {
    await throwFetchError(res, 'Failed to save completed activity');
  }
  const data = await res.json().catch(() => null);
  const cs = data?.companion_suggestion;
  return cs && cs.activity ? (cs as CompanionSuggestion) : null;
}

export async function skipActivity(tripId: number, placeId: string): Promise<void> {
  if (!tripId) return;
  const res = await fetch(`${API_BASE}/api/trips/${tripId}/activities/skip`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ place_id: placeId }),
  });
  if (!res.ok) {
    await throwFetchError(res, 'Failed to skip activity');
  }
}

export async function markTransitTooFar(tripId: number, placeId: string): Promise<{ maxTravelTimeMin: number; atFloor: boolean }> {
  const res = await fetch(`${API_BASE}/api/trips/${tripId}/activities/transit-too-far`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ place_id: placeId }),
  });
  if (!res.ok) {
    await throwFetchError(res, 'Failed to mark transit suggestion as too far');
  }
  const data = await res.json();
  return {
    maxTravelTimeMin: Number(data.max_travel_time_min),
    atFloor: !!data.at_floor,
  };
}

export async function preferWalk(tripId: number, placeId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/trips/${tripId}/activities/prefer-walk`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ place_id: placeId }),
  });
  if (!res.ok) {
    await throwFetchError(res, 'Failed to request a walking suggestion');
  }
}

export async function dismissFoodIntercept(tripId: number): Promise<void> {
  if (!tripId) return;
  const res = await fetch(`${API_BASE}/api/trips/${tripId}/food-intercept/dismiss`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) {
    await throwFetchError(res, 'Failed to dismiss food intercept');
  }
}

export async function fetchNextFoodSuggestion(tripId: number): Promise<NextActivityResult> {
  if (!tripId) return { activity: null, userLocation: null };
  const res = await fetch(`${API_BASE}/api/trips/${tripId}/food-intercept/next`);
  if (!res.ok) {
    if (res.status === 404) return { activity: null, userLocation: null };
    await throwFetchError(res, 'Failed to fetch next food suggestion');
  }
  const data = await res.json();
  return {
    activity: data.activity || null,
    userLocation: data.userLocation || null,
    card_type: data.card_type,
    intercept_metadata: data.intercept_metadata,
  };
}

export async function fetchNextUtilitySuggestion(tripId: number): Promise<NextActivityResult> {
  if (!tripId) return { activity: null, userLocation: null };
  const res = await fetch(`${API_BASE}/api/trips/${tripId}/utility/next`);
  if (!res.ok) {
    if (res.status === 404) return { activity: null, userLocation: null };
    const text = await res.text().catch(() => '');
    throw new Error(`Failed to fetch next utility suggestion (${res.status}): ${text || res.statusText}`);
  }
  const data = await res.json();
  return {
    activity: data.activity || null,
    userLocation: data.userLocation || null,
    card_type: data.card_type,
    exhausted: data.exhausted,
  };
}

export interface CompletedActivityLog {
  id: number;
  trip_id: number;
  title: string;
  description: string | null;
  category: Activity['category'] | null;
  address: string | null;
  estimated_time: string | null;
  cost: string | null;
  rating: number | null;
  review_count: number | null;
  feedback?: Activity['feedback'];
  completed_at: string;
}

export async function fetchCompletedActivities(tripId: number): Promise<CompletedActivityLog[]> {
  if (!tripId || Number.isNaN(tripId)) return [];
  const res = await fetch(`${API_BASE}/api/trips/${tripId}/activities?completed=true`);
  const text = await res.text();
  if (!res.ok) {
    throw new Error(`Failed to fetch completed activities (${res.status}): ${text || res.statusText}`);
  }
  const data = JSON.parse(text) as { activities?: CompletedActivityLog[] };
  return Array.isArray(data.activities) ? data.activities : [];
}

// ─── Trip Lifecycle ───────────────────────────────────────────

export async function startTrip(): Promise<void> {
  // TODO: POST /api/trips/:id/start
}

export async function restartTrip(): Promise<void> {
  // TODO: POST /api/trips/:id/restart
}
