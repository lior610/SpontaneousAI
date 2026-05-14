export interface TripPreferences {
  food: number;
  nature: number;
  culture: number;
  nightlife: number;
  budget: number;
  pace: number;
}

export interface TripConstraints {
  maxWalkingDistance: number;
  transportType: 'walking' | 'public' | 'taxi';
}

export interface ItineraryItem {
  id: string;
  title: string;
  description: string;
  image: string;
  estimatedTime: string;
  category: 'food' | 'nature' | 'culture' | 'nightlife' | 'general';
  order: number;
}

export interface TripSetup {
  startDate: Date | null;
  endDate: Date | null;
  destination: string;
  preferences: TripPreferences;
  constraints: TripConstraints;
}

export interface Activity {
  id: string;
  title: string;
  description: string;
  image: string;
  rating: number;
  reviewCount: number;
  estimatedTime: string;
  cost: string;
  category: 'food' | 'nature' | 'culture' | 'nightlife' | 'general';
  address: string;
  completed: boolean;
  lat?: number;
  lng?: number;
  feedback?: {
    liked?: boolean;
    tooLong?: boolean;
    tooFar?: boolean;
    tooExpensive?: boolean;
  };
}

export interface InterceptMetadata {
  reason: string;
  dismissable: boolean;
  cooldown_minutes: number;
}

export interface NextActivityResponse {
  activity: Activity | null;
  userLocation: { lat: number; lng: number } | null;
  card_type?: 'food_intercept' | 'regular';
  intercept_metadata?: InterceptMetadata;
}

export const defaultPreferences: TripPreferences = {
  food: 50,
  nature: 50,
  culture: 50,
  nightlife: 30,
  budget: 50,
  pace: 50,
};

export const defaultConstraints: TripConstraints = {
  maxWalkingDistance: 2,
  transportType: 'walking',
};

export const defaultTripSetup: TripSetup = {
  startDate: null,
  endDate: null,
  destination: '',
  preferences: defaultPreferences,
  constraints: defaultConstraints,
};
