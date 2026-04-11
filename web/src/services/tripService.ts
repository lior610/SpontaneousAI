/**
 * Trip Service Layer
 * 
 * Calls API to update user preferences (users table) and create trips (trips table).
 */

import { API_BASE } from '@/config';
import {
  TripSetup,
  TripPreferences,
  TripConstraints,
  ItineraryItem,
  Activity,
  defaultTripSetup,
} from '@/types/trip';

/** Result of saving trip setup: trip is created in DB and user preferences are updated. */
export interface SaveTripResult {
  setup: TripSetup;
  tripId: number;
}

/** Pass `editTripId` to update an existing trip instead of creating a new one. */
export interface SaveTripOptions {
  editTripId?: number;
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

function parseTripSaveError(res: Response, errorText: string): Error {
  let parsedError = '';
  try {
    const parsed = JSON.parse(errorText) as { error?: string };
    parsedError = parsed.error ?? '';
  } catch {
    parsedError = '';
  }
  if (res.status === 404 && errorText.includes('User not found')) {
    return new Error(
      'Your account was not found in the database. Please log out and log in again, or register if you haven’t yet.',
    );
  }
  if (res.status === 409 && parsedError) {
    return new Error(parsedError);
  }
  return new Error(
    `Failed to save trip (status ${res.status}): ${parsedError || errorText || res.statusText}`,
  );
}

export async function saveTripSetup(
  setup: TripSetup,
  options?: SaveTripOptions,
): Promise<SaveTripResult> {
  const userId = getCurrentUserId();
  if (!setup.startDate || !setup.endDate || !setup.destination) {
    throw new Error('startDate, endDate, and destination are required to save a trip');
  }

  // 1) Persist user preferences to users table (skipped if user not found, e.g. 404)
  await updateUserPreferences(setup);

  const budget =
    setup.preferences.budget != null
      ? Math.round((setup.preferences.budget / 100) * 5000)
      : null;

  const startDate = setup.startDate.toISOString().split('T')[0];
  const endDate = setup.endDate.toISOString().split('T')[0];
  const preference_breakdown = preferenceBreakdownFromSetup(setup);
  const { maxWalkingDistance, transportType } = setup.constraints;

  const editTripId = options?.editTripId;

  if (editTripId != null) {
    const res = await fetch(`${API_BASE}/api/trips/${editTripId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        destination: setup.destination,
        start_date: startDate,
        end_date: endDate,
        budget,
        preference_breakdown,
        max_walking_distance: maxWalkingDistance,
        preferred_transportation: transportType,
      }),
    });
    const errorText = await res.text().catch(() => '');
    if (!res.ok) {
      throw parseTripSaveError(res, errorText);
    }
    return { setup, tripId: editTripId };
  }

  const tripBody = {
    user_id: userId,
    destination: setup.destination,
    start_date: startDate,
    end_date: endDate,
    budget,
    preference_breakdown,
    max_walking_distance: maxWalkingDistance,
    preferred_transportation: transportType,
  };

  const res = await fetch(`${API_BASE}/api/trips`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(tripBody),
  });

  if (!res.ok) {
    const errorText = await res.text().catch(() => '');
    throw parseTripSaveError(res, errorText);
  }

  const data = (await res.json()) as { trip?: { trip_id?: number }; trip_id?: number };
  const tripId = data.trip?.trip_id ?? data.trip_id;
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

// ─── Itinerary ────────────────────────────────────────────────

export async function generateItinerary(setup: TripSetup): Promise<ItineraryItem[]> {
  // TODO: POST /api/trips/:id/generate-itinerary
  // For now, returns mock data based on preferences
  const items: ItineraryItem[] = [];

  const categoryMap: Record<string, string[]> = {
    food: [`Local Market in ${setup.destination}`, 'Famous Restaurant District', 'Street Food Tour'],
    nature: [`Central Park of ${setup.destination}`, 'Scenic Viewpoint', 'Botanical Gardens'],
    culture: ['Historical Museum', 'Art Gallery', 'Ancient Temple'],
    nightlife: ['Rooftop Bar', 'Live Music Venue', 'Night Market'],
  };

  const entries: [string, number][] = [
    ['food', setup.preferences.food],
    ['nature', setup.preferences.nature],
    ['culture', setup.preferences.culture],
    ['nightlife', setup.preferences.nightlife],
  ];
  const sorted = entries.sort((a, b) => b[1] - a[1]);

  let order = 0;
  sorted.forEach(([category, value]) => {
    if (value >= 40) {
      const places = categoryMap[category];
      const count = value >= 70 ? 2 : 1;
      places.slice(0, count).forEach((name) => {
        items.push({
          id: `suggested-${category}-${order}`,
          title: name,
          description: `A popular ${category} spot recommended based on your preferences`,
          image: '',
          estimatedTime: category === 'food' ? '1-2 hours' : '2-3 hours',
          category: category as ItineraryItem['category'],
          order: order++,
        });
      });
    }
  });

  return items;
}

export async function saveItinerary(itinerary: ItineraryItem[]): Promise<void> {
  // TODO: PUT /api/trips/:id/itinerary
}

// ─── Activities ───────────────────────────────────────────────

const mockActivities: Activity[] = [
  {
    id: 'mock-1',
    title: 'Local Street Food Market',
    description: 'Explore a vibrant street food market with dozens of stalls offering authentic local cuisine. Try the famous dumplings and fresh fruit shakes.',
    image: '',
    rating: 4.6,
    reviewCount: 1240,
    estimatedTime: '1-2 hours',
    cost: '$',
    category: 'food',
    address: '23 Market Lane, Old Town',
    completed: false,
  },
  {
    id: 'mock-2',
    title: 'Sunset Viewpoint Hike',
    description: 'A short but rewarding trail leading to a panoramic viewpoint. Best visited in the late afternoon for stunning golden-hour views.',
    image: '',
    rating: 4.8,
    reviewCount: 870,
    estimatedTime: '2-3 hours',
    cost: 'Free',
    category: 'nature',
    address: 'Hillside Trail, North District',
    completed: false,
  },
  {
    id: 'mock-3',
    title: 'Historical Old Town Walking Tour',
    description: 'Wander through centuries-old streets, admire colonial architecture, and learn about the city\'s rich history from informative plaques along the route.',
    image: '',
    rating: 4.4,
    reviewCount: 560,
    estimatedTime: '1.5-2 hours',
    cost: '$$',
    category: 'culture',
    address: 'Heritage Square, City Center',
    completed: false,
  },
  {
    id: 'mock-4',
    title: 'Rooftop Jazz Bar',
    description: 'Enjoy craft cocktails and live jazz music with a skyline backdrop. A popular spot for locals and travelers alike.',
    image: '',
    rating: 4.5,
    reviewCount: 320,
    estimatedTime: '2-3 hours',
    cost: '$$',
    category: 'nightlife',
    address: '8th Floor, Tower Building, Main Street',
    completed: false,
  },
  {
    id: 'mock-5',
    title: 'Botanical Gardens',
    description: 'A peaceful escape featuring tropical plants, koi ponds, and shaded walking paths. Perfect for a relaxing morning stroll.',
    image: '',
    rating: 4.3,
    reviewCount: 710,
    estimatedTime: '1-2 hours',
    cost: '$',
    category: 'nature',
    address: '45 Garden Road, East Side',
    completed: false,
  },
];

let mockIndex = 0;
const completedMock: Activity[] = [];

export async function fetchNextActivity(): Promise<Activity | null> {
  // TODO: GET /api/trips/:id/next-activity
  if (mockIndex >= mockActivities.length) return null;
  return { ...mockActivities[mockIndex] };
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
    }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`Failed to save completed activity (${res.status}): ${text || res.statusText}`);
  }

  completedMock.push({ ...activity, completed: true, feedback });
  mockIndex++;
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
