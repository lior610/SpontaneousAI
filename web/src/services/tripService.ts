/**
 * Trip Service Layer
 * 
 * Placeholder async functions that return local data for now.
 * Replace each function body with real API calls when your MVC backend is ready.
 * 
 * Example future usage:
 *   export async function fetchTripSetup(tripId: string): Promise<TripSetup> {
 *     const res = await fetch(`/api/trips/${tripId}`);
 *     return res.json();
 *   }
 */

import {
  TripSetup,
  TripPreferences,
  TripConstraints,
  ItineraryItem,
  Activity,
  defaultTripSetup,
} from '@/types/trip';

// ─── Trip Setup ───────────────────────────────────────────────

export async function fetchTripSetup(): Promise<TripSetup> {
  // TODO: GET /api/trips/:id
  return { ...defaultTripSetup };
}

export async function saveTripSetup(setup: TripSetup): Promise<TripSetup> {
  // TODO: PUT /api/trips/:id
  return setup;
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
  activity: Activity,
  feedback: Activity['feedback']
): Promise<void> {
  // TODO: POST /api/trips/:id/activities/:activityId/complete
  completedMock.push({ ...activity, completed: true, feedback });
  mockIndex++;
}

export async function fetchCompletedActivities(): Promise<Activity[]> {
  // TODO: GET /api/trips/:id/activities?completed=true
  return [...completedMock];
}

// ─── Trip Lifecycle ───────────────────────────────────────────

export async function startTrip(): Promise<void> {
  // TODO: POST /api/trips/:id/start
}

export async function restartTrip(): Promise<void> {
  // TODO: POST /api/trips/:id/restart
}
