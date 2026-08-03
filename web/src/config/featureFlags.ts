export const featureFlags = {
  tripSuggestionCard: {
    showRating: false,
    showReviewCount: false,
    showEstimatedTime: false,
  },
  feedbackPopup: {
    showSpecificNeeds: true,
  },
  wizard: {
    showTripPace: false,
  },
} as const;
