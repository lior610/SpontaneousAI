import { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Settings, MapPin, RefreshCw, LogOut, Home, Briefcase, Pill, HeartPulse, ShoppingCart, Store, ShieldAlert, Utensils } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ActivityCard } from '@/components/ActivityCard';
import { FeedbackPopup, FeedbackChoice } from '@/components/FeedbackPopup';
import { CompanionSuggestionPopup } from '@/components/CompanionSuggestionPopup';
import { WalkFurtherPrompt } from '@/components/WalkFurtherPrompt';
import { LoadingSpinner } from '@/components/LoadingSpinner';
import { EmptyState } from '@/components/EmptyState';
import { MapView } from '@/components/MapView';
import { Activity, TripSetup, defaultTripSetup, NextActivityResponse } from '@/types/trip';
import { fetchNextActivity, completeActivity, skipActivity, dismissFoodIntercept, fetchNextFoodSuggestion, fetchNextUtilitySuggestion, fetchCompletedActivities, CompletedActivityLog, CompanionSuggestion, expandWalkingRange } from '@/services/tripService';
import { clearCurrentUser } from '@/services/authService';
import { getCurrentPosition, reportPosition, startTracking, stopTracking, watchArrivalDeparture } from '@/services/locationService';
import { showAppNotification } from '@/services/notificationService';
import { featureFlags } from '@/config/featureFlags';

const COMPANION_ENABLED = featureFlags.companionSuggestions.enabled;
const WALK_FURTHER_ENABLED = featureFlags.walkFurther.enabled;
const WALK_FURTHER_STEP_KM = featureFlags.walkFurther.stepKm;

const ACTIVITY_CACHE_KEY = (id: number) => `trip_${id}_current_activity`;
const LOCATION_CACHE_KEY = (id: number) => `trip_${id}_user_location`;

const SPECIFIC_NEEDS = [
  { key: 'food', icon: Utensils, label: 'Food Break' },
  { key: 'pharmacy', icon: Pill, label: 'Pharmacy' },
  { key: 'medical', icon: HeartPulse, label: 'Medical' },
  { key: 'grocery', icon: ShoppingCart, label: 'Grocery' },
  { key: 'convenience', icon: Store, label: 'Convenience' },
  { key: 'police_emergency', icon: ShieldAlert, label: 'Police Emergency' },
] as const;

function toActivity(c: CompletedActivityLog): Activity {
  return {
    id: c.id.toString(),
    title: c.title,
    description: c.description ?? '',
    image: '',
    rating: c.rating ?? 0,
    reviewCount: c.review_count ?? 0,
    estimatedTime: c.estimated_time ?? '',
    cost: c.cost ?? '',
    category: c.category ?? 'general',
    address: c.address ?? '',
    completed: true,
    feedback: c.feedback,
  };
}

export function TripPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const state = (location.state as { tripSetup?: TripSetup; tripId?: number }) ?? {};
  const tripId = state.tripId;
  const tripSetup: TripSetup = state.tripSetup ?? defaultTripSetup;
  // state.tripId is the created trip id from the wizard (for future API calls e.g. next activity)

  const [currentActivity, setCurrentActivity] = useState<Activity | null>(null);
  const [completedActivities, setCompletedActivities] = useState<Activity[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasArrived, setHasArrived] = useState(false);
  const [showFeedback, setShowFeedback] = useState(false);
  const [companionSuggestion, setCompanionSuggestion] = useState<CompanionSuggestion | null>(null);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);
  const [userLocation, setUserLocation] = useState<{ lat: number; lng: number } | null>(null);
  const [isFoodIntercept, setIsFoodIntercept] = useState(false);
  const [isUtility, setIsUtility] = useState(false);
  const [foodBatchExhausted, setFoodBatchExhausted] = useState(false);
  // Set when the engine has nothing left within the current walking radius.
  const [rangePrompt, setRangePrompt] = useState<{ maxWalkingDistance: number | null } | null>(null);
  const [isExpandingRange, setIsExpandingRange] = useState(false);
  // Set only when the user explicitly chooses to finish (or we can't widen further).
  const [tripFinished, setTripFinished] = useState(false);
  const [showNeeds, setShowNeeds] = useState(false);
  const initialLoadDone = useRef(false);
  // ISO timestamp of when the geofence detected the user arrived at the current attraction.
  const arrivedAtRef = useRef<string | null>(null);

  // Fetch browser GPS once on load
  useEffect(() => {
    getCurrentPosition().then((coords) => {
      if (coords) setUserLocation(coords);
    });
  }, []);

  // Periodic background location sync to backend
  useEffect(() => {
    if (import.meta.env.VITE_BACKGROUND_TRACKING !== 'on' || !tripId) return;
    startTracking(tripId);
    return () => stopTracking();
  }, [tripId]);

  // Load first activity, completed history, and set user location from backend fallback
  useEffect(() => {
    if (!tripId || initialLoadDone.current) return;
    initialLoadDone.current = true;
    const load = async () => {
      setIsLoading(true);
      try {
        const cached = sessionStorage.getItem(ACTIVITY_CACHE_KEY(tripId));
        const cachedLocation = sessionStorage.getItem(LOCATION_CACHE_KEY(tripId));
        let activity: Activity | null = null;
        if (cached) {
          activity = JSON.parse(cached) as Activity;
          if (cachedLocation) {
            setUserLocation(prev => prev ?? JSON.parse(cachedLocation));
          }
        } else {
          if (navigator.geolocation) {
            const coords = await getCurrentPosition();
            if (coords) {
              await reportPosition(tripId, coords).catch(e =>
                console.error('[TripPage] Failed to report initial load position:', e)
              );
              setUserLocation(coords);
              sessionStorage.setItem(LOCATION_CACHE_KEY(tripId), JSON.stringify(coords));
            }
          }
          const result = await fetchNextActivity(tripId);
          activity = result.activity;
          setIsFoodIntercept(result.card_type === 'food_intercept');
          if (result.userLocation) {
            setUserLocation(prev => prev ?? result.userLocation);
            sessionStorage.setItem(LOCATION_CACHE_KEY(tripId), JSON.stringify(result.userLocation));
          }
          if (activity) {
            sessionStorage.setItem(ACTIVITY_CACHE_KEY(tripId), JSON.stringify(activity));
          } else if (result.outOfRange && WALK_FURTHER_ENABLED) {
            // Trip opened with nothing left in range: offer to walk further
            // instead of immediately showing the trip-complete summary.
            setRangePrompt({ maxWalkingDistance: result.maxWalkingDistance ?? null });
          }
        }
        setCurrentActivity(activity);

        const completed = await fetchCompletedActivities(tripId);
        if (completed.length > 0) {
          setCompletedActivities(completed.map(toActivity));
        }
      } catch (err) {
        console.error('[TripPage] Failed to load:', err);
      } finally {
        setIsLoading(false);
      }
    };
    load();
  }, [tripId]);

  const finishingRef = useRef(false);

  // The user tapped "Done" (or the geofence detected they left) — open the feedback popup.
  const handleActivityComplete = () => setShowFeedback(true);

  // Map the popup choice to feedback, then complete + advance.
  //   liked   -> explicit like
  //   skipped -> explicit negative signal
  //   next    -> no explicit feedback; backend infers from dwell time via the LLM
  const handleFeedbackSubmit = (choice: FeedbackChoice) => {
    setShowFeedback(false);
    let feedback: Activity['feedback'] | undefined;
    if (choice === 'liked') feedback = { liked: true };
    else feedback = undefined;
    finishActivity(feedback);
  };

  // Shared state update for any "next activity" response (regular or food intercept)
  const applyActivityResult = (result: NextActivityResponse) => {
    setCurrentActivity(result.activity);
    setIsFoodIntercept(result.card_type === 'food_intercept');
    setIsUtility(result.card_type === 'utility');
    if (result.userLocation) {
      setUserLocation(result.userLocation);
      if (tripId) sessionStorage.setItem(LOCATION_CACHE_KEY(tripId), JSON.stringify(result.userLocation));
    }
    if (result.activity && tripId) {
      sessionStorage.setItem(ACTIVITY_CACHE_KEY(tripId), JSON.stringify(result.activity));
      console.log(`[TripPage] Next Activity Generated: ${result.activity.title} at [${result.activity.lat}, ${result.activity.lng}]`);
    }
  };

  // Shared handler for any next-activity response. Returns true when the
  // walk-further prompt was shown (caller should not treat that as a normal activity).
  const handleNextActivityResult = (result: NextActivityResponse, notifyNext?: boolean): boolean => {
    if (!result.activity && result.outOfRange && WALK_FURTHER_ENABLED && !tripFinished) {
      setRangePrompt({ maxWalkingDistance: result.maxWalkingDistance ?? null });
      setCurrentActivity(null);
      return true;
    }

    setRangePrompt(null);
    applyActivityResult(result);
    if (result.activity && notifyNext) {
      showAppNotification('Next Destination Ready', `Head over to: ${result.activity.title}`);
    }
    return false;
  };

  // Fetch and display the next recommended activity from the engine.
  const advanceToNextActivity = async (notifyNext?: boolean) => {
    if (!tripId) return;
    sessionStorage.removeItem(ACTIVITY_CACHE_KEY(tripId));
    setIsLoading(true);
    try {
      const result = await fetchNextActivity(tripId);
      handleNextActivityResult(result, notifyNext);
    } catch (err) {
      console.error('[TripPage] Failed to fetch next activity:', err);
    } finally {
      setIsLoading(false);
    }
  };

  // User agreed to walk further: widen the radius (persisted to the DB) and retry.
  const handleWalkFurther = async () => {
    if (!tripId) return;
    setIsExpandingRange(true);
    try {
      const res = await expandWalkingRange(tripId, WALK_FURTHER_STEP_KM);
      setRangePrompt(null);
      if (!res.changed) {
        // Already at the maximum radius — treat as a genuine finish.
        setTripFinished(true);
        setCurrentActivity(null);
        return;
      }
      await advanceToNextActivity();
    } catch (err) {
      console.error('[TripPage] Failed to expand walking range:', err);
    } finally {
      setIsExpandingRange(false);
    }
  };

  // User declined to walk further: show the normal trip-complete summary.
  const handleFinishTrip = () => {
    setRangePrompt(null);
    setTripFinished(true);
    setCurrentActivity(null);
  };

  // Mark the current activity done and advance to the next one. The backend uses the
  // arrival timestamp (from the geofence) to measure dwell time; when no explicit
  // feedback is given it asks the LLM whether the user likely didn't enjoy it.
  //
  // If the like matches a popular trip, the backend returns a companion suggestion;
  // we offer it before fetching the next activity (accept -> show it, dismiss -> normal next).
  const finishActivity = async (feedback?: Activity['feedback'], notifyNext?: boolean) => {
    if (!tripId || finishingRef.current) return;
    finishingRef.current = true;

    try {
      const arrivedAt = arrivedAtRef.current;
      let suggestion: CompanionSuggestion | null = null;

      if (currentActivity) {
        try {
          suggestion = await completeActivity(tripId, currentActivity, { arrivedAt, feedback });
        } catch (err) {
          console.error('[TripPage] Failed to complete activity:', err);
        }
        // Use completed attraction's coords as new user position
        if (currentActivity.lat != null && currentActivity.lng != null) {
          setUserLocation({ lat: currentActivity.lat, lng: currentActivity.lng });
        }
        // Refresh history so the resulting feedback (explicit or auto-derived) is reflected.
        try {
          const completed = await fetchCompletedActivities(tripId);
          setCompletedActivities(completed.map(toActivity));
        } catch (err) {
          console.error('[TripPage] Failed to refresh completed activities:', err);
        }
      }

      // Reset arrival tracking for the next attraction.
      arrivedAtRef.current = null;
      setHasArrived(false);

      // Offer the companion suggestion (if any) before advancing.
      if (COMPANION_ENABLED && suggestion?.activity) {
        setCompanionSuggestion(suggestion);
        return;
      }

      await advanceToNextActivity(notifyNext);
    } finally {
      finishingRef.current = false;
    }
  };

  // User accepted the "you might also like" suggestion: show it as the next activity.
  const handleCompanionAccept = () => {
    const suggestion = companionSuggestion;
    setCompanionSuggestion(null);
    if (!suggestion?.activity || !tripId) return;
    setIsFoodIntercept(false);
    setIsUtility(false);
    setCurrentActivity(suggestion.activity);
    sessionStorage.setItem(ACTIVITY_CACHE_KEY(tripId), JSON.stringify(suggestion.activity));
  };

  // User dismissed the suggestion: continue with the normal recommendation flow.
  const handleCompanionDismiss = async () => {
    setCompanionSuggestion(null);
    await advanceToNextActivity();
  };

  // Cycles through the cached food batch (next restaurant from the same engine call)
  const handleRefreshFood = async () => {
    if (!tripId) return;
    setIsLoading(true);
    try {
      if (userLocation) {
        await reportPosition(tripId, userLocation).catch(e =>
          console.error('[TripPage] Failed to report refresh food position:', e)
        );
        sessionStorage.setItem(LOCATION_CACHE_KEY(tripId), JSON.stringify(userLocation));
      }
      const result = await fetchNextFoodSuggestion(tripId);
      if (result.activity) {
        applyActivityResult(result);
      } else {
        setFoodBatchExhausted(true);
      }
    } catch (e) {
      console.error('[TripPage] Failed to fetch different restaurant:', e);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRefreshUtility = async () => {
    if (!tripId) return;
    setIsLoading(true);
    try {
      if (userLocation) {
        await reportPosition(tripId, userLocation).catch(e =>
          console.error('[TripPage] Failed to report refresh utility position:', e)
        );
        sessionStorage.setItem(LOCATION_CACHE_KEY(tripId), JSON.stringify(userLocation));
      }
      const result = await fetchNextUtilitySuggestion(tripId);
      if (result.activity) {
        if (result.exhausted) {
          showAppNotification('You\'ve seen all options nearby', 'Showing all places from the beginning');
        }
        applyActivityResult(result);
      }
    } catch (e) {
      console.error('[TripPage] Failed to fetch different utility:', e);
    } finally {
      setIsLoading(false);
    }
  };

  // User chose "Look for more restaurants" after batch ran out
  const handleRefillFood = async () => {
    if (!tripId) return;
    setIsLoading(true);
    try {
      if (userLocation) {
        await reportPosition(tripId, userLocation).catch(e =>
          console.error('[TripPage] Failed to report refill food position:', e)
        );
        sessionStorage.setItem(LOCATION_CACHE_KEY(tripId), JSON.stringify(userLocation));
      }
      const result = await fetchNextFoodSuggestion(tripId);
      if (result.activity) {
        setFoodBatchExhausted(false);
        applyActivityResult(result);
      }
    } catch (e) {
      console.error('[TripPage] Failed to refill food batch:', e);
    } finally {
      setIsLoading(false);
    }
  };

  // User chose "Return" — go back to regular activities
  const handleReturnFromFood = async () => {
    if (!tripId) return;
    setFoodBatchExhausted(false);
    if (userLocation) {
      await reportPosition(tripId, userLocation).catch(e =>
        console.error('[TripPage] Failed to report return food position:', e)
      );
      sessionStorage.setItem(LOCATION_CACHE_KEY(tripId), JSON.stringify(userLocation));
    }
    await advanceToNextActivity();
  };

  // Dismiss food (starts cooldown) or skip regular activity, then fetch next
  const handleSkipOrDismiss = async () => {
    if (!tripId || !currentActivity) return;
    setIsLoading(true);
    try {
      if (userLocation) {
        await reportPosition(tripId, userLocation).catch(e =>
          console.error('[TripPage] Failed to report skip position:', e)
        );
        sessionStorage.setItem(LOCATION_CACHE_KEY(tripId), JSON.stringify(userLocation));
      }
      if (isFoodIntercept) {
        await dismissFoodIntercept(tripId);
      } else {
        await skipActivity(tripId, currentActivity.id).catch(e =>
          console.error('[TripPage] Failed to skip activity:', e)
        );
      }
      sessionStorage.removeItem(ACTIVITY_CACHE_KEY(tripId));
      const result = await fetchNextActivity(tripId);
      handleNextActivityResult(result);
    } catch (e) {
      console.error('[TripPage] Failed to fetch next activity:', e);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSpecificNeed = async (need: string) => {
    if (!tripId) return;
    setShowNeeds(false);
    setIsLoading(true);
    try {
      if (userLocation) {
        await reportPosition(tripId, userLocation).catch(e =>
          console.error('[TripPage] Failed to report specific-need position:', e)
        );
        sessionStorage.setItem(LOCATION_CACHE_KEY(tripId), JSON.stringify(userLocation));
      }
      sessionStorage.removeItem(ACTIVITY_CACHE_KEY(tripId));
      const result = await fetchNextActivity(tripId, need);
      applyActivityResult(result);
    } catch (e) {
      console.error('[TripPage] Failed to fetch specific need:', e);
    } finally {
      setIsLoading(false);
    }
  };

  // Geofence: detect arrival/departure at the current attraction to measure dwell time.
  // On arrival we record the timestamp; on departure we prompt the feedback popup.
  useEffect(() => {
    if (!currentActivity || currentActivity.lat == null || currentActivity.lng == null) {
      return;
    }
    arrivedAtRef.current = null;
    setHasArrived(false);

    const stop = watchArrivalDeparture(
      { lat: currentActivity.lat, lng: currentActivity.lng },
      {
        onPosition: (coords) => setUserLocation(coords),
        onArrive: (coords) => {
          arrivedAtRef.current = new Date().toISOString();
          setHasArrived(true);
          setUserLocation(coords);
        },
        onDepart: () => {
          finishActivity(undefined, true);
        },
      }
    );
    return stop;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentActivity?.id]);

  const handleLogout = () => {
    clearCurrentUser();
    setShowLogoutConfirm(false);
    navigate('/', { replace: true });
  };

  return (
    <div className="min-h-screen bg-background pb-20">
      {/* Header */}
      <header className="sticky top-0 z-20 bg-card/80 backdrop-blur-md border-b">
        <div className="px-4 py-3">
          <div className="flex items-center justify-between mb-2">
            <div className="min-w-0 mr-4">
              <h1 className="font-bold text-lg flex items-center gap-2">
                <MapPin className="w-5 h-5 text-primary flex-shrink-0" />
                <span className="truncate">{tripSetup.destination || 'Your Trip'}</span>
              </h1>
              <p className="text-xs text-muted-foreground truncate">
                {completedActivities.length} activities completed
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => navigate('/')}
                className="w-10 h-10 flex items-center justify-center rounded-lg text-foreground hover:bg-muted transition-all"
                title="Back to homepage"
              >
                <Home className="w-5 h-5" />
              </button>
              <button
                onClick={() => navigate('/trips')}
                className="w-10 h-10 flex items-center justify-center rounded-lg text-foreground hover:bg-muted transition-all"
                title="Manage trips"
              >
                <Briefcase className="w-5 h-5" />
              </button>
              <button
                onClick={() => navigate('/wizard', { state: { tripSetup, editTripId: tripId } })}
                className="w-10 h-10 flex items-center justify-center rounded-lg text-foreground hover:bg-muted transition-all"
                title="Trip settings"
              >
                <Settings className="w-5 h-5" />
              </button>
              <button
                onClick={() => setShowLogoutConfirm(true)}
                className="w-10 h-10 flex items-center justify-center rounded-lg text-foreground hover:bg-muted transition-all"
                title="Log out"
              >
                <LogOut className="w-5 h-5" />
              </button>
            </div>
          </div>
          {/* Progress bar */}
          <div className="h-2 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-primary rounded-full transition-all duration-500"
              style={{ width: `${completedActivities.length > 0 ? 100 : 0}%` }}
            />
          </div>
        </div>
      </header>

      <main className="p-4 max-w-6xl mx-auto">
        {isLoading ? (
          <LoadingSpinner />
        ) : foodBatchExhausted ? (
          <div className="max-w-md mx-auto text-center space-y-6 py-12">
            <p className="text-lg font-medium">No more restaurants in this batch</p>
            <p className="text-sm text-muted-foreground">We can search for more nearby options, or you can continue with regular activities.</p>
            <div className="flex flex-col gap-3">
              <button
                onClick={handleRefillFood}
                className="w-full h-11 rounded-lg bg-primary text-primary-foreground font-semibold hover:bg-primary/90 transition-all"
              >
                Look for more restaurants
              </button>
              <button
                onClick={handleReturnFromFood}
                className="w-full h-11 rounded-lg border font-semibold text-foreground hover:bg-muted transition-all"
              >
                Return to activities
              </button>
            </div>
          </div>
        ) : currentActivity ? (
          <div className="flex flex-col lg:flex-row lg:items-stretch gap-4">
            {/* Map */}
            {currentActivity.lat != null && currentActivity.lng != null && (
              <div className="w-full lg:w-1/2 h-[250px] lg:h-auto lg:min-h-[400px] rounded-xl overflow-hidden border">
                <MapView
                  attractionLat={currentActivity.lat}
                  attractionLng={currentActivity.lng}
                  attractionTitle={currentActivity.title}
                  userLat={userLocation?.lat}
                  userLng={userLocation?.lng}
                  showLocationWarning={!userLocation}
                />
              </div>
            )}

            {/* Card */}
            <div className="w-full lg:w-1/2 flex flex-col justify-center space-y-4">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                {isFoodIntercept ? (
                  <span className="px-2 py-1 rounded-full bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300 font-medium">Food Break</span>
                ) : (
                  <span className="px-2 py-1 rounded-full bg-accent/10 text-accent font-medium">Next Up</span>
                )}
                <span>Activity #{completedActivities.length + 1}</span>
              </div>
              {hasArrived && (
                <div className="flex items-center gap-2 text-sm rounded-lg px-3 py-2 border bg-secondary/10 text-secondary border-secondary/20">
                  <MapPin className="w-4 h-4" />
                  You've arrived — we'll ask how it went when you leave.
                </div>
              )}
              <ActivityCard activity={currentActivity} onComplete={handleActivityComplete} />

              {/* Refresh / Dismiss Buttons */}
              <div className="text-center space-y-2">
                {isFoodIntercept && (
                  <button
                    onClick={handleRefreshFood}
                    className="inline-flex items-center gap-2 h-9 px-4 rounded-md text-sm font-semibold text-foreground hover:bg-muted transition-all duration-300"
                  >
                    <RefreshCw className="w-4 h-4" />
                    Suggest a different restaurant
                  </button>
                )}
                {isUtility && (
                  <button
                    onClick={handleRefreshUtility}
                    className="inline-flex items-center gap-2 h-9 px-4 rounded-md text-sm font-semibold text-foreground hover:bg-muted transition-all duration-300"
                  >
                    <RefreshCw className="w-4 h-4" />
                    I want a different one
                  </button>
                )}
                <button
                  onClick={handleSkipOrDismiss}
                  className="inline-flex items-center gap-2 h-9 px-4 rounded-md text-sm font-semibold text-foreground hover:bg-muted transition-all duration-300"
                >
                  <RefreshCw className="w-4 h-4" />
                  {isFoodIntercept ? 'Not hungry? Skip food break' : 'Not feeling it? Get another suggestion'}
                </button>

                {featureFlags.feedbackPopup.showSpecificNeeds && (
                  <button
                    onClick={() => setShowNeeds(true)}
                    className="inline-flex items-center gap-2 h-9 px-4 rounded-md text-sm font-semibold text-foreground hover:bg-muted transition-all duration-300"
                  >
                    <RefreshCw className="w-4 h-4" />
                    I need something specific right now
                  </button>
                )}
              </div>
            </div>
          </div>
        ) : rangePrompt && !tripFinished ? (
          <WalkFurtherPrompt
            maxWalkingDistance={rangePrompt.maxWalkingDistance}
            stepKm={WALK_FURTHER_STEP_KM}
            isExpanding={isExpandingRange}
            onExpand={handleWalkFurther}
            onFinish={handleFinishTrip}
          />
        ) : (
          <div className="max-w-lg mx-auto space-y-6">
            <EmptyState
              title={completedActivities.length > 0 ? "Trip Complete! 🎉" : "No Activities Yet"}
              description={completedActivities.length > 0
                ? "You've explored all the activities we had for you."
                : "Activities will appear here once your trip is planned."}
            />

            {/* Trip Summary */}
            <div className="rounded-xl border border-accent/20 bg-gradient-to-br from-card to-accent/5">
              <div className="p-5">
                <h3 className="text-base font-bold mb-4">Trip Summary</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div className="text-center p-3 bg-card rounded-lg">
                    <p className="text-2xl font-bold text-primary">{completedActivities.length}</p>
                    <p className="text-xs text-muted-foreground">Activities</p>
                  </div>
                  <div className="text-center p-3 bg-card rounded-lg">
                    <p className="text-2xl font-bold text-secondary">
                      {completedActivities.filter(a => a.feedback?.liked).length}
                    </p>
                    <p className="text-xs text-muted-foreground">Liked</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Feedback Popup */}
      {showFeedback && currentActivity && (
        <FeedbackPopup
          activity={currentActivity}
          onSubmit={handleFeedbackSubmit}
          onClose={() => setShowFeedback(false)}
        />
      )}

      {/* Companion Suggestion Popup ("because you liked X...") */}
      {companionSuggestion && (
        <CompanionSuggestionPopup
          suggestion={companionSuggestion}
          onAccept={handleCompanionAccept}
          onDismiss={handleCompanionDismiss}
        />
      )}

      {/* Specific Needs Popup */}
      {showNeeds && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-foreground/45 backdrop-blur-sm animate-fade-in"
          onClick={() => setShowNeeds(false)}
        >
          <div
            className="w-full max-w-md rounded-2xl border bg-card shadow-2xl animate-scale-in"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-6">
              <h3 className="text-lg font-bold">What do you need right now?</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                We'll point you to the nearest option.
              </p>

              <div className="mt-5 grid grid-cols-2 gap-3">
                {SPECIFIC_NEEDS.map(({ key, icon: Icon, label }) => (
                  <button
                    key={key}
                    onClick={() => handleSpecificNeed(key)}
                    className="flex flex-col items-center gap-2 p-4 rounded-xl border-2 border-border hover:border-accent hover:bg-accent/10 transition-all duration-200"
                  >
                    <Icon className="w-6 h-6 text-accent" />
                    <span className="font-medium text-sm">{label}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {showLogoutConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-foreground/45 backdrop-blur-sm animate-fade-in">
          <div className="w-full max-w-md rounded-2xl border bg-card shadow-2xl animate-scale-in">
            <div className="p-5">
              <h3 className="text-lg font-semibold">Log out?</h3>
              <p className="mt-2 text-sm text-muted-foreground">
                You will need to log in again to continue.
              </p>
            </div>
            <div className="px-5 pb-5 flex justify-end gap-2">
              <Button variant="ghost" size="sm" onClick={() => setShowLogoutConfirm(false)}>
                Cancel
              </Button>
              <Button variant="destructive" size="sm" onClick={handleLogout}>
                Log Out
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
