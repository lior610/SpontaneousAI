/**
 * Map an engine attraction (or companion suggestion) to the frontend Activity shape.
 *
 * Shared by getNextActivity and the companion-suggestion passthrough so both
 * produce identical activity objects. Kept dependency-free so it is unit-testable
 * in isolation.
 *
 * @param {object} attr - engine attraction-like object (place_id, name, hours, budget, categories, ...)
 * @returns {object} activity object consumed by the web client
 */
export function mapEngineAttractionToActivity(attr) {
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
  };
}
