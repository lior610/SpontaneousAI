/**
 * Trip Service Layer
 * 
 * Calls API to update user preferences (users table) and create trips (trips table).
 */

import { format } from 'date-fns';
import { API_BASE } from '@/config';
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

/** Wizard categories with percentages for trip preference_breakdown (list of categories + %). */
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
    const text = await res.text().catch(() => '');
    throw new Error(`Failed to update preferences (${res.status}): ${text || res.statusText}`);
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
    preferred_transportation: setup.constraints.transportType,
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
    const errorText = await res.text().catch(() => '');
    let parsedError = '';
    try {
      const parsed = JSON.parse(errorText) as { error?: string };
      parsedError = parsed.error ?? '';
    } catch {
      parsedError = '';
    }
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

export interface NextActivityResult {
  activity: Activity | null;
  userLocation: { lat: number; lng: number } | null;
}

export async function fetchNextActivity(tripId?: number, specificNeed?: string): Promise<NextActivityResult> {
  if (!tripId) return { activity: null, userLocation: null };
  const url = specificNeed
    ? `${API_BASE}/api/trips/${tripId}/next-activity?specific_need=${encodeURIComponent(specificNeed)}`
    : `${API_BASE}/api/trips/${tripId}/next-activity`;

  const res = await fetch(url);
  if (!res.ok) {
    if (res.status === 404) return { activity: null, userLocation: null };
    const text = await res.text().catch(() => '');
    throw new Error(`Failed to fetch next activity (${res.status}): ${text || res.statusText}`);
  }
  const data = await res.json();
  return {
    activity: data.activity || null,
    userLocation: data.userLocation || null,
  };
}

export async function completeActivity(
  tripId: number,
  activity: Activity,
  feedback: Activity['feedback']
): Promise<void> {
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
      feedback,
      completed_at: new Date().toISOString(),
      place_id: activity.id,
      lat: activity.lat,
      lng: activity.lng
    }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`Failed to save completed activity (${res.status}): ${text || res.statusText}`);
  }
}

export async function skipActivity(tripId: number, placeId: string): Promise<void> {
  if (!tripId) return;
  const res = await fetch(`${API_BASE}/api/trips/${tripId}/activities/skip`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ place_id: placeId }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`Failed to skip activity (${res.status}): ${text || res.statusText}`);
  }
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
