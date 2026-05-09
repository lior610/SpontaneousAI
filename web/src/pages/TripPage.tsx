import { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Settings, MapPin, RefreshCw, LogOut, Home, Briefcase } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ActivityCard } from '@/components/ActivityCard';
import { FeedbackPopup } from '@/components/FeedbackPopup';
import { LoadingSpinner } from '@/components/LoadingSpinner';
import { EmptyState } from '@/components/EmptyState';
import { MapView } from '@/components/MapView';
import { Activity, TripSetup, defaultTripSetup } from '@/types/trip';
import { fetchNextActivity, completeActivity, skipActivity, fetchCompletedActivities } from '@/services/tripService';
import { clearCurrentUser } from '@/services/authService';
import { getCurrentPosition, startTracking, stopTracking } from '@/services/locationService';

const ACTIVITY_CACHE_KEY = (id: number) => `trip_${id}_current_activity`;

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
  const [showFeedback, setShowFeedback] = useState(false);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);
  const [userLocation, setUserLocation] = useState<{ lat: number; lng: number } | null>(null);
  const initialLoadDone = useRef(false);

  // Fetch browser GPS once on load and start background tracking
  useEffect(() => {
    if (import.meta.env.VITE_GPS_ENABLED !== 'on') return;
    getCurrentPosition().then((coords) => {
      if (coords) setUserLocation(coords);
    });
    if (tripId) {
      startTracking(tripId);
      return () => stopTracking();
    }
  }, [tripId]);

  // Load first activity, completed history, and set user location from backend fallback
  useEffect(() => {
    if (!tripId || initialLoadDone.current) return;
    initialLoadDone.current = true;
    const load = async () => {
      setIsLoading(true);
      try {
        const cached = sessionStorage.getItem(ACTIVITY_CACHE_KEY(tripId));
        let activity: Activity | null = null;
        if (cached) {
          activity = JSON.parse(cached) as Activity;
        } else {
          const result = await fetchNextActivity(tripId);
          activity = result.activity;
          if (result.userLocation) {
            setUserLocation(prev => prev ?? result.userLocation);
          }
          if (activity) {
            sessionStorage.setItem(ACTIVITY_CACHE_KEY(tripId), JSON.stringify(activity));
          }
        }
        setCurrentActivity(activity);

        const completed = await fetchCompletedActivities(tripId);
        if (completed.length > 0) {
          setCompletedActivities(completed.map(c => ({
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
          })));
        }
      } catch (err) {
        console.error('[TripPage] Failed to load:', err);
      } finally {
        setIsLoading(false);
      }
    };
    load();
  }, [tripId]);

  const handleActivityComplete = () => {
    setShowFeedback(true);
  };

  // Submit feedback, mark activity done, update user location to completed attraction
  const handleFeedbackSubmit = async (feedback: Activity['feedback'], needSpecific?: string) => {
    if (!tripId) {
      setShowFeedback(false);
      return;
    }

    if (currentActivity) {
      try {
        await completeActivity(tripId, currentActivity, feedback);
      } catch (err) {
        console.error('[TripPage] Failed to complete activity:', err);
      }
      setCompletedActivities(prev => [...prev, { ...currentActivity, completed: true, feedback }]);
      // Use completed attraction's coords as new user position
      if (currentActivity.lat != null && currentActivity.lng != null) {
        setUserLocation({ lat: currentActivity.lat, lng: currentActivity.lng });
      }
    }
    setShowFeedback(false);

    // Activity done: clear cache and fetch next activity from backend
    sessionStorage.removeItem(ACTIVITY_CACHE_KEY(tripId));
    setIsLoading(true);
    try {
      const result = await fetchNextActivity(tripId, needSpecific);
      setCurrentActivity(result.activity);
      if (result.userLocation) {
        setUserLocation(result.userLocation);
      }
      if (result.activity) {
        sessionStorage.setItem(ACTIVITY_CACHE_KEY(tripId), JSON.stringify(result.activity));
      }
    } catch (err) {
      console.error('[TripPage] Failed to fetch next activity:', err);
    } finally {
      setIsLoading(false);
    }
  };

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
            <div>
              <h1 className="font-bold text-lg flex items-center gap-2">
                <MapPin className="w-5 h-5 text-primary" />
                {tripSetup.destination || 'Your Trip'}
              </h1>
              <p className="text-xs text-muted-foreground">
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
                />
              </div>
            )}

            {/* Card */}
            <div className="w-full lg:w-1/2 flex flex-col justify-center space-y-4">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <span className="px-2 py-1 rounded-full bg-accent/10 text-accent font-medium">Next Up</span>
                <span>Activity #{completedActivities.length + 1}</span>
              </div>
              <ActivityCard activity={currentActivity} onComplete={handleActivityComplete} />

              {/* Refresh Button */}
              <div className="text-center">
                <button
                  onClick={async () => {
                    if (tripId && currentActivity) {
                      setIsLoading(true);
                      try {
                        try {
                          await skipActivity(tripId, currentActivity.id);
                        } catch (e) {
                          console.error('[TripPage] Failed to skip activity:', e);
                        }
                        sessionStorage.removeItem(ACTIVITY_CACHE_KEY(tripId));
                        const result = await fetchNextActivity(tripId);
                        setCurrentActivity(result.activity);
                        if (result.userLocation) setUserLocation(result.userLocation);
                        if (result.activity) {
                          sessionStorage.setItem(ACTIVITY_CACHE_KEY(tripId), JSON.stringify(result.activity));
                        }
                      } catch (e) {
                        console.error('[TripPage] Failed to fetch next activity:', e);
                      } finally {
                        setIsLoading(false);
                      }
                    }
                  }}
                  className="inline-flex items-center gap-2 h-9 px-4 rounded-md text-sm font-semibold text-foreground hover:bg-muted transition-all duration-300"
                >
                  <RefreshCw className="w-4 h-4" />
                  Not feeling it? Get another suggestion
                </button>
              </div>
            </div>
          </div>
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
