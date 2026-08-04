import axios from 'axios';

const ENGINE_HOST = (() => { const h = process.env.ENGINE_HOST || '127.0.0.1'; return h === 'localhost' ? '127.0.0.1' : h; })();

const UTILITY_BATCH_SIZE = 10;

const utilityBatchCache = new Map();

const UTILITY_CACHE_TTL_MS = 30 * 60 * 1000;
setInterval(() => {
  const now = Date.now();
  for (const [tripId, entry] of utilityBatchCache) {
    if (now - entry.storedAt > UTILITY_CACHE_TTL_MS) {
      utilityBatchCache.delete(tripId);
    }
  }
}, UTILITY_CACHE_TTL_MS).unref();

export function buildUtilityCard(util, position, category) {
  return {
    activity: {
      id: util.place_id || util.activity_id || 'util-1',
      title: util.name,
      description: util.description || `A nearby location matching your immediate need for ${category}.`,
      image: '',
      rating: null,
      reviewCount: null,
      estimatedTime: util.hours || '1 hour',
      cost: util.budget ? `$${util.budget}` : '$$',
      category: util.categories && util.categories.length > 0 ? util.categories[0].toLowerCase() : 'general',
      address: util.address,
      lat: util.latitude,
      lng: util.longitude,
      completed: false
    },
    card_type: 'utility',
    userLocation: position ? { lat: position.lat, lng: position.lng } : null
  };
}

async function fetchUtilityBatch(category, lat, lng, locationId, currentHour) {
  const res = await axios.post(`http://${ENGINE_HOST}:8000/utilities/closest`, {
    parent_category: category,
    lat,
    lng,
    location_id: locationId,
    current_hour: currentHour,
    limit: UTILITY_BATCH_SIZE
  });
  return res.data || [];
}

export async function refillAndGetUtility(tripId, category, coords, position, locationId, currentHour) {
  const batch = await fetchUtilityBatch(category, coords?.lat ?? null, coords?.lng ?? null, locationId, currentHour);
  if (batch.length === 0) return null;

  const first = batch[0];
  utilityBatchCache.set(tripId, {
    category,
    results: batch,
    currentIndex: 1,
    currentPlaceId: first.place_id || null,
    storedAt: Date.now(),
  });
  return buildUtilityCard(first, position, category);
}

export function getNextUtilitySuggestion(tripId, position) {
  const cached = utilityBatchCache.get(tripId);
  if (!cached || !cached.results || cached.results.length === 0) return null;

  let exhausted = false;
  if (cached.currentIndex >= cached.results.length) {
    cached.currentIndex = 0;
    exhausted = true;
  }

  const util = cached.results[cached.currentIndex];
  cached.currentIndex++;
  cached.currentPlaceId = util.place_id || null;

  return { ...buildUtilityCard(util, position, cached.category), exhausted };
}
