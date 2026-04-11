import { useState, useRef, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { format } from 'date-fns';
import { getCurrentUser } from '@/services/authService';
import { API_BASE } from '@/config';
import { 
  Calendar, MapPin, ArrowRight, ArrowLeft, Check,
  UtensilsCrossed, TreePine, Theater, PartyPopper, 
  DollarSign, Gauge, Footprints, Car, Train
} from 'lucide-react';
import { StepIndicator } from '@/components/StepIndicator';
import { TripSetup, TripPreferences, TripConstraints, defaultTripSetup } from '@/types/trip';
import { saveTripSetup } from '@/services/tripService';
import { featureFlags } from '@/config/featureFlags';

const stepLabels = ['Dates', 'Preferences', 'Constraints', 'Confirm'];

const preferenceItems = [
  { key: 'food', icon: UtensilsCrossed, label: 'Food & Dining', emoji: '🍜' },
  { key: 'nature', icon: TreePine, label: 'Nature & Outdoors', emoji: '🌲' },
  { key: 'culture', icon: Theater, label: 'Culture & History', emoji: '🎭' },
  { key: 'nightlife', icon: PartyPopper, label: 'Nightlife', emoji: '🎉' },
  { key: 'budget', icon: DollarSign, label: 'Budget Level', emoji: '💰' },
  { key: 'pace', icon: Gauge, label: 'Trip Pace', emoji: '⚡' },
];

const transportOptions = [
  { value: 'walking', icon: Footprints, label: 'Walking' },
  { value: 'public', icon: Train, label: 'Public Transit' },
  { value: 'taxi', icon: Car, label: 'Taxi/Ride-share' },
] as const;

function mergeTripSetupFromNavigation(ts?: TripSetup): TripSetup {
  if (!ts) return { ...defaultTripSetup };
  return {
    ...defaultTripSetup,
    ...ts,
    preferences: { ...defaultTripSetup.preferences, ...ts.preferences },
    constraints: { ...defaultTripSetup.constraints, ...ts.constraints },
  };
}

export default function WizardPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const flowState =
    (location.state as { editTripId?: number; tripSetup?: TripSetup } | null) ?? {};
  const editTripId = flowState.editTripId;
  const [tripSetup, setTripSetup] = useState<TripSetup>(() =>
    mergeTripSetupFromNavigation(flowState.tripSetup),
  );
  const [wizardStep, setWizardStep] = useState(1);
  const [localDestination, setLocalDestination] = useState(
    () => flowState.tripSetup?.destination ?? '',
  );
  const [saveError, setSaveError] = useState<string | null>(null);
  const [dateConflictError, setDateConflictError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isCheckingDates, setIsCheckingDates] = useState(false);

  // Require login: redirect to login if not authenticated
  const user = getCurrentUser();
  useEffect(() => {
    if (!user) {
      navigate('/login', { replace: true });
    }
  }, [navigate, user]);

  const startDateRef = useRef<HTMLInputElement>(null);
  const endDateRef = useRef<HTMLInputElement>(null);

  // Don't render wizard content until we know user is logged in (avoids flash before redirect)
  if (!user) {
    return null;
  }

  const updatePreferences = (update: Partial<TripPreferences>) => {
    setTripSetup(prev => ({
      ...prev,
      preferences: { ...prev.preferences, ...update },
    }));
  };

  const updateConstraints = (update: Partial<TripConstraints>) => {
    setTripSetup(prev => ({
      ...prev,
      constraints: { ...prev.constraints, ...update },
    }));
  };

  const checkDateOverlap = async (startDate: Date, endDate: Date): Promise<string | null> => {
    if (!user) return null;
    const res = await fetch(`${API_BASE}/api/trips?user_id=${user.id}`);
    const text = await res.text();
    if (!res.ok) return null;
    const data = JSON.parse(text) as {
      trips?: Array<{ trip_id: number; destination: string; start_date: string; end_date: string }>;
    };
    const trips = Array.isArray(data.trips) ? data.trips : [];

    for (const trip of trips) {
      if (editTripId && trip.trip_id === editTripId) continue;
      const existingStart = new Date(`${String(trip.start_date).slice(0, 10)}T00:00:00`);
      const existingEnd = new Date(`${String(trip.end_date).slice(0, 10)}T00:00:00`);
      const overlaps = existingStart <= endDate && existingEnd >= startDate;
      if (overlaps) {
        return `Trip dates overlap with an existing trip (${trip.destination}: ${String(trip.start_date).slice(0, 10)} to ${String(trip.end_date).slice(0, 10)}). You can only have one trip at a time.`;
      }
    }
    return null;
  };

  const handleNext = async () => {
    if (wizardStep === 1) {
      setDateConflictError(null);
      setTripSetup(prev => ({ ...prev, destination: localDestination }));

      if (tripSetup.startDate && tripSetup.endDate) {
        setIsCheckingDates(true);
        try {
          const overlapMessage = await checkDateOverlap(tripSetup.startDate, tripSetup.endDate);
          if (overlapMessage) {
            setDateConflictError(overlapMessage);
            return;
          }
        } finally {
          setIsCheckingDates(false);
        }
      }
    }
    if (wizardStep < 4) {
      setWizardStep(wizardStep + 1);
    } else {
      const finalSetup = { ...tripSetup, destination: localDestination };
      setSaveError(null);
      setIsSaving(true);
      try {
        const { tripId } = await saveTripSetup(
          finalSetup,
          editTripId != null ? { editTripId } : undefined,
        );
        navigate('/trip', { state: { tripSetup: finalSetup, tripId } });
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to save trip';
        setSaveError(message);
        console.error('Failed to save trip to server:', err);
      } finally {
        setIsSaving(false);
      }
    }
  };

  const handleBack = () => {
    if (wizardStep > 1) setWizardStep(wizardStep - 1);
  };

  const canProceed = () => {
    if (wizardStep === 1) {
      if (!tripSetup.startDate || !tripSetup.endDate || !localDestination) return false;
      // Start date must be on or before end date
      return tripSetup.startDate.getTime() <= tripSetup.endDate.getTime();
    }
    return true;
  };

  const visiblePreferenceItems = preferenceItems.filter(
    (item) => item.key !== 'pace' || featureFlags.wizard.showTripPace,
  );

  const hasInvalidDateRange =
    wizardStep === 1 &&
    tripSetup.startDate &&
    tripSetup.endDate &&
    tripSetup.endDate.getTime() < tripSetup.startDate.getTime();

  const handleDateChange = (field: 'startDate' | 'endDate', value: string) => {
    const date = value ? new Date(value + 'T00:00:00') : null;
    setDateConflictError(null);
    setTripSetup(prev => ({ ...prev, [field]: date }));
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-20 bg-card/80 backdrop-blur-md border-b px-4 py-3">
        <div className="max-w-2xl mx-auto flex items-center justify-between">
          <button onClick={() => navigate('/')} className="inline-flex items-center gap-2 h-9 px-4 rounded-md text-sm font-semibold text-foreground hover:bg-muted transition-all">
            <ArrowLeft className="w-4 h-4" /> Back
          </button>
          <h1 className="font-bold text-lg">Trip Setup</h1>
          <div className="w-20" />
        </div>
      </header>

      <div className="max-w-2xl mx-auto">
        <StepIndicator currentStep={wizardStep} totalSteps={4} labels={stepLabels} />
      </div>

      <main className="max-w-2xl mx-auto px-4 pb-32">
        {/* Step 1: Dates & Destination */}
        {wizardStep === 1 && (
          <div className="space-y-6 animate-slide-up">
            <div className="text-center mb-8">
              <h2 className="text-2xl font-bold mb-2">When & Where? 🗺️</h2>
              <p className="text-muted-foreground">Let's start with the basics</p>
            </div>

            {/* Destination */}
            <div className="rounded-xl border bg-card shadow-card hover:shadow-lg hover:-translate-y-1 transition-all duration-300">
              <div className="p-5 pb-2">
                <h3 className="text-base font-bold flex items-center gap-2">
                  <MapPin className="w-4 h-4 text-primary" /> Destination
                </h3>
              </div>
              <div className="p-5 pt-0">
                <input
                  type="text"
                  placeholder="e.g., Tokyo, Japan"
                  value={localDestination}
                  onChange={(e) => setLocalDestination(e.target.value)}
                  className="flex h-12 w-full rounded-xl border-2 border-input bg-card px-4 py-2 text-base placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:border-primary transition-all duration-200"
                />
              </div>
            </div>

            {/* Dates */}
            <div className="rounded-xl border bg-card shadow-card hover:shadow-lg hover:-translate-y-1 transition-all duration-300">
              <div className="p-5 pb-2">
                <h3 className="text-base font-bold flex items-center gap-2">
                  <Calendar className="w-4 h-4 text-primary" /> Travel Dates
                </h3>
              </div>
              <div className="p-5 pt-0 flex flex-col sm:flex-row gap-4">
                <div className="flex-1">
                  <label className="text-sm text-muted-foreground mb-1 block">Start Date</label>
                  <input
                    ref={startDateRef}
                    type="date"
                    value={tripSetup.startDate ? format(tripSetup.startDate, 'yyyy-MM-dd') : ''}
                    onChange={(e) => handleDateChange('startDate', e.target.value)}
                    className="flex h-12 w-full rounded-xl border-2 border-input bg-card px-4 py-2 text-base focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:border-primary transition-all duration-200"
                  />
                </div>
                <div className="flex-1">
                  <label className="text-sm text-muted-foreground mb-1 block">End Date</label>
                  <input
                    ref={endDateRef}
                    type="date"
                    value={tripSetup.endDate ? format(tripSetup.endDate, 'yyyy-MM-dd') : ''}
                    onChange={(e) => handleDateChange('endDate', e.target.value)}
                    className="flex h-12 w-full rounded-xl border-2 border-input bg-card px-4 py-2 text-base focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:border-primary transition-all duration-200"
                  />
                </div>
              </div>
              {hasInvalidDateRange && (
                <p className="mt-3 px-5 text-sm text-destructive font-medium">
                  End date must be on or after the start date.
                </p>
              )}
              {dateConflictError && (
                <p className="mt-3 px-5 text-sm text-destructive font-medium">
                  {dateConflictError}
                </p>
              )}
            </div>
          </div>
        )}

        {/* Step 2: Preferences */}
        {wizardStep === 2 && (
          <div className="space-y-6 animate-slide-up">
            <div className="text-center mb-8">
              <h2 className="text-2xl font-bold mb-2">What do you love? 💕</h2>
              <p className="text-muted-foreground">Adjust sliders to match your travel style</p>
            </div>

            {visiblePreferenceItems.map(({ key, label, emoji }) => (
              <div key={key} className="rounded-xl border bg-card shadow-card hover:shadow-lg hover:-translate-y-1 transition-all duration-300">
                <div className="p-5">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                        <span className="text-xl">{emoji}</span>
                      </div>
                      <span className="font-medium">{label}</span>
                    </div>
                    <span className="text-sm font-semibold text-primary">
                      {tripSetup.preferences[key as keyof TripPreferences]}%
                    </span>
                  </div>
                  <input
                    type="range"
                    min={0}
                    max={100}
                    step={5}
                    value={tripSetup.preferences[key as keyof TripPreferences]}
                    onChange={(e) => updatePreferences({ [key]: Number(e.target.value) })}
                    className="w-full h-2 bg-muted rounded-full appearance-none cursor-pointer accent-primary"
                  />
                  <div className="flex justify-between text-xs text-muted-foreground mt-2">
                    <span>{key === 'budget' ? 'Budget' : key === 'pace' ? 'Relaxed' : 'Less'}</span>
                    <span>{key === 'budget' ? 'Luxury' : key === 'pace' ? 'Packed' : 'More'}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Step 3: Constraints */}
        {wizardStep === 3 && (
          <div className="space-y-6 animate-slide-up">
            <div className="text-center mb-8">
              <h2 className="text-2xl font-bold mb-2">Any constraints? 🎯</h2>
              <p className="text-muted-foreground">Help us plan around your needs</p>
            </div>

            {/* Walking Distance */}
            <div className="rounded-xl border bg-card shadow-card hover:shadow-lg hover:-translate-y-1 transition-all duration-300">
              <div className="p-5">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-secondary/10 flex items-center justify-center">
                      <Footprints className="w-5 h-5 text-secondary" />
                    </div>
                    <span className="font-medium">Max Walking Distance</span>
                  </div>
                  <span className="text-sm font-semibold text-secondary">
                    {tripSetup.constraints.maxWalkingDistance} km
                  </span>
                </div>
                <input
                  type="range"
                  min={0.5}
                  max={10}
                  step={0.5}
                  value={tripSetup.constraints.maxWalkingDistance}
                  onChange={(e) => updateConstraints({ maxWalkingDistance: Number(e.target.value) })}
                  className="w-full h-2 bg-muted rounded-full appearance-none cursor-pointer accent-secondary"
                />
              </div>
            </div>

            {/* Transport Type */}
            <div className="rounded-xl border bg-card shadow-card hover:shadow-lg hover:-translate-y-1 transition-all duration-300">
              <div className="p-5 pb-2">
                <h3 className="text-base font-bold">Preferred Transportation</h3>
              </div>
              <div className="p-5 pt-0">
                <div className="grid grid-cols-3 gap-3">
                  {transportOptions.map(({ value, icon: Icon, label }) => (
                    <button
                      key={value}
                      onClick={() => updateConstraints({ transportType: value })}
                      className={`flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all duration-200 ${
                        tripSetup.constraints.transportType === value
                          ? 'border-primary bg-primary/10 text-primary'
                          : 'border-border hover:border-primary/30'
                      }`}
                    >
                      <Icon className="w-6 h-6" />
                      <span className="text-xs font-medium">{label}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Step 4: Confirmation */}
        {wizardStep === 4 && (
          <div className="space-y-6 animate-slide-up">
            <div className="text-center mb-8">
              <h2 className="text-2xl font-bold mb-2">All Set! 🎉</h2>
              <p className="text-muted-foreground">Review your trip settings</p>
            </div>

            <div className="rounded-xl border border-accent/20 bg-gradient-to-br from-card to-accent/5">
              <div className="p-5 space-y-4">
                <div className="flex items-center gap-3 p-3 bg-card rounded-lg">
                  <MapPin className="w-5 h-5 text-primary" />
                  <div>
                    <p className="text-xs text-muted-foreground">Destination</p>
                    <p className="font-semibold">{localDestination || 'Not set'}</p>
                  </div>
                </div>

                <div className="flex items-center gap-3 p-3 bg-card rounded-lg">
                  <Calendar className="w-5 h-5 text-secondary" />
                  <div>
                    <p className="text-xs text-muted-foreground">Dates</p>
                    <p className="font-semibold">
                      {tripSetup.startDate && tripSetup.endDate
                        ? `${format(tripSetup.startDate, 'MMM d')} - ${format(tripSetup.endDate, 'MMM d, yyyy')}`
                        : 'Not set'}
                    </p>
                  </div>
                </div>

                <div className="p-3 bg-card rounded-lg">
                  <p className="text-xs text-muted-foreground mb-2">Top Interests</p>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(tripSetup.preferences)
                      .filter(([key]) => !['budget', 'pace'].includes(key))
                      .sort((a, b) => b[1] - a[1])
                      .slice(0, 3)
                      .map(([key, value]) => (
                        <span key={key} className="px-3 py-1 rounded-full bg-primary/10 text-primary text-sm font-medium">
                          {key.charAt(0).toUpperCase() + key.slice(1)} ({value}%)
                        </span>
                      ))}
                  </div>
                </div>

                <div className="flex items-center gap-3 p-3 bg-card rounded-lg">
                  {tripSetup.constraints.transportType === 'walking' && <Footprints className="w-5 h-5 text-accent" />}
                  {tripSetup.constraints.transportType === 'public' && <Train className="w-5 h-5 text-accent" />}
                  {tripSetup.constraints.transportType === 'taxi' && <Car className="w-5 h-5 text-accent" />}
                  <div>
                    <p className="text-xs text-muted-foreground">Transportation</p>
                    <p className="font-semibold capitalize">{tripSetup.constraints.transportType}</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-secondary/10 rounded-xl p-4 text-center">
              <p className="text-sm text-muted-foreground">
                🤖 Our AI will create a personalized itinerary based on your preferences, real-time data, and local recommendations.
              </p>
            </div>

            {saveError && (
              <div className="rounded-xl border border-destructive/50 bg-destructive/10 p-4">
                <p className="text-sm font-medium text-destructive">Could not save trip</p>
                <p className="mt-1 text-sm text-muted-foreground">{saveError}</p>
                {!saveError.toLowerCase().includes('overlap') && (
                  <p className="mt-2 text-xs text-muted-foreground">
                    Check that the API is running (e.g. npm run dev in api/) and the database is set up (see database/README.md).
                  </p>
                )}
              </div>
            )}
          </div>
        )}
      </main>

      {/* Bottom Navigation */}
      <div className="fixed bottom-0 left-0 right-0 bg-card/80 backdrop-blur-md border-t p-4">
        <div className="max-w-2xl mx-auto flex gap-4">
          {wizardStep > 1 && (
            <button
              onClick={handleBack}
              className="flex-1 inline-flex items-center justify-center gap-2 h-12 rounded-xl text-base font-semibold border-2 border-primary text-primary bg-transparent hover:bg-primary hover:text-primary-foreground transition-all duration-300"
            >
              <ArrowLeft className="w-4 h-4" /> Back
            </button>
          )}
          <button
            onClick={handleNext}
            disabled={!canProceed() || isSaving || isCheckingDates}
            className="flex-1 inline-flex items-center justify-center gap-2 h-12 rounded-xl text-base font-bold bg-gradient-to-r from-accent to-accent-light text-accent-foreground shadow-lg hover:shadow-glow hover:-translate-y-1 hover:scale-105 transition-all duration-300 disabled:opacity-50 disabled:pointer-events-none"
          >
            {isCheckingDates ? (
              <>Checking dates…</>
            ) : wizardStep === 4 ? (
              isSaving ? (
                <>Saving…</>
              ) : (
                <><Check className="w-4 h-4" /> Generate Itinerary</>
              )
            ) : (
              <>Next <ArrowRight className="w-4 h-4" /></>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
