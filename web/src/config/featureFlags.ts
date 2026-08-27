export const featureFlags = {
  tripSuggestionCard: {
    showRating: false,
    showReviewCount: false,
    showEstimatedTime: false,
  },
  feedbackPopup: {
    showExtendedFeedbackOptions: false,
    showSpecificNeeds: true,
  },
  wizard: {
    showTripPace: false,
  },
  companionSuggestions: {
    // "Because you liked X, you might also like Y" prompt after a like.
    enabled: true,
  },
  walkFurther: {
    // When no attraction is left within the current walking radius, offer to
    // widen the radius instead of declaring the trip finished.
    enabled: true,
    // Kilometers added to max_walking_distance each time the user agrees.
    stepKm: 1,
  },
  transitSuggestions: {
    // Mix high-value public-transport places into the suggestion stream, and
    // offer a "go a bit further by transit?" prompt when walking options run out.
    enabled: true,
    // Display-only: the engine's hard search cap (km) for transit-reachable places.
    maxRadiusKm: 5,
  },
} as const;
