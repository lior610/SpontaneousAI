// Maps an engine attraction (or companion suggestion) to the frontend Activity shape.
// Shared by getNextActivity and the companion-suggestion passthrough so both produce
// identical objects.
/**
 * @param {object} attr - engine attraction-like object (place_id, name, hours, budget, categories, ...)
 * @param {object} [rec] - optional parent RecommendationResponse (reachable_by, transit_minutes, ...)
 */
export function mapEngineAttractionToActivity(attr, rec = {}) {
  return {
    id: attr.place_id || attr.activity_id,
    title: attr.name,
    description: attr.description,
    image: '',
    rating: null,
    reviewCount: null,
    estimatedTime: attr.hours || '1-2 hours',
    cost: attr.budget && attr.budget !== '0' ? `$${attr.budget}` : 'Free',
    category: attr.categories && attr.categories.length > 0 ? attr.categories[0].toLowerCase() : 'general',
    address: attr.address,
    lat: attr.latitude,
    lng: attr.longitude,
    completed: false,
    reachableBy: rec.reachable_by || attr.reachable_by || null,
    transitMinutes: rec.transit_minutes ?? attr.transit_minutes ?? null,
    transitSummary: rec.transit_summary ?? attr.transit_summary ?? null,
  };
}

/** Map a full engine RecommendationResponse (attraction + transit metadata). */
export function mapEngineRecommendationToActivity(rec) {
  if (!rec) return null;
  const attr = rec.attraction || rec;
  return mapEngineAttractionToActivity(attr, rec);
}
