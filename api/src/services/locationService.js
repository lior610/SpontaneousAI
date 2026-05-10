// Centralized location management: validation, storage, and retrieval of user positions
import * as usersDb from '../db/usersConnection.js';

// Default fallback coordinates per destination city
const CITY_DEFAULTS = {
  'new york': { lat: 40.7580, lng: -73.9855 },
  'london': { lat: 51.5237, lng: -0.1585 },
};

export function validate(lat, lng) {
  const errors = [];
  if (lat == null || isNaN(lat) || lat < -90 || lat > 90) {
    errors.push('lat must be a number between -90 and 90');
  }
  if (lng == null || isNaN(lng) || lng < -180 || lng > 180) {
    errors.push('lng must be a number between -180 and 180');
  }
  return errors.length ? errors : null;
}

// Update the trip's current position in the database
export async function updatePosition(tripId, lat, lng) {
  const errors = validate(lat, lng);
  if (errors) throw new Error(errors.join('; '));
  await usersDb.query(
    `UPDATE trips SET current_lat = $1, current_lng = $2 WHERE trip_id = $3`,
    [lat, lng, tripId]
  );
}

// Get the trip's current position, falling back to city defaults if not set
export async function getPosition(tripId) {
  const result = await usersDb.query(
    `SELECT current_lat, current_lng, destination FROM trips WHERE trip_id = $1`,
    [tripId]
  );
  if (result.rows.length === 0) return null;

  const trip = result.rows[0];
  const lat = trip.current_lat ? parseFloat(trip.current_lat) : null;
  const lng = trip.current_lng ? parseFloat(trip.current_lng) : null;

  if (lat != null && lng != null) {
    return { lat, lng };
  }

  return getDefaultForDestination(trip.destination);
}

// Resolve default coordinates for a destination city
export function getDefaultForDestination(destination) {
  if (!destination) return CITY_DEFAULTS['new york'];
  const key = destination.toLowerCase();
  for (const [city, coords] of Object.entries(CITY_DEFAULTS)) {
    if (key.includes(city)) return coords;
  }
  return CITY_DEFAULTS['new york'];
}
