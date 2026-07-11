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
} as const;
