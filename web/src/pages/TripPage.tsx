import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Settings, MapPin, RefreshCw, LogOut } from 'lucide-react';
import { ActivityCard } from '@/components/ActivityCard';
import { FeedbackPopup } from '@/components/FeedbackPopup';
import { LoadingSpinner } from '@/components/LoadingSpinner';
import { EmptyState } from '@/components/EmptyState';
import { Activity, TripSetup, defaultTripSetup } from '@/types/trip';
import { fetchNextActivity, completeActivity } from '@/services/tripService';
import { clearCurrentUser } from '@/services/authService';

export function TripPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const state = (location.state as { tripSetup?: TripSetup; tripId?: number }) ?? {};
  const tripSetup: TripSetup = state.tripSetup ?? defaultTripSetup;
  // state.tripId is the created trip id from the wizard (for future API calls e.g. next activity)

  const [currentActivity, setCurrentActivity] = useState<Activity | null>(null);
  const [completedActivities, setCompletedActivities] = useState<Activity[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [showFeedback, setShowFeedback] = useState(false);

  useEffect(() => {
    const load = async () => {
      setIsLoading(true);
      const activity = await fetchNextActivity();
      setCurrentActivity(activity);
      setIsLoading(false);
    };
    load();
  }, []);

  const handleActivityComplete = () => {
    setShowFeedback(true);
  };

  const handleFeedbackSubmit = async (feedback: Activity['feedback'], needSpecific?: string) => {
    if (currentActivity) {
      await completeActivity(currentActivity, feedback);
      setCompletedActivities(prev => [...prev, { ...currentActivity, completed: true, feedback }]);
    }
    setShowFeedback(false);
    setCurrentActivity(null);

    if (needSpecific) {
      // TODO: handle finding nearby specific need
    }
  };

  const handleLogout = () => {
    clearCurrentUser();
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
                onClick={() => navigate('/wizard', { state: { tripSetup } })}
                className="w-10 h-10 flex items-center justify-center rounded-lg text-foreground hover:bg-muted transition-all"
                title="Trip settings"
              >
                <Settings className="w-5 h-5" />
              </button>
              <button
                onClick={handleLogout}
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

      <main className="p-4 max-w-lg mx-auto">
        {/* Current Activity */}
        {isLoading ? (
          <LoadingSpinner />
        ) : currentActivity ? (
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <span className="px-2 py-1 rounded-full bg-accent/10 text-accent font-medium">Next Up</span>
              <span>Activity #{completedActivities.length + 1}</span>
            </div>
            <ActivityCard activity={currentActivity} onComplete={handleActivityComplete} />
          </div>
        ) : (
          <div className="space-y-6">
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

        {/* Refresh Button */}
        {!isLoading && currentActivity && (
          <div className="mt-6 text-center">
            <button
              onClick={async () => {
                setIsLoading(true);
                const activity = await fetchNextActivity();
                setCurrentActivity(activity);
                setIsLoading(false);
              }}
              className="inline-flex items-center gap-2 h-9 px-4 rounded-md text-sm font-semibold text-foreground hover:bg-muted transition-all duration-300"
            >
              <RefreshCw className="w-4 h-4" />
              Not feeling it? Get another suggestion
            </button>
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
    </div>
  );
}
