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
} as const;
