import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { format, isAfter, isBefore, isWithinInterval, startOfDay } from 'date-fns';
import { Plus, Pencil, Trash2, MapPin, ArrowRight, Compass, Calendar, CheckCircle2, ArrowLeft, FileText } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { getCurrentUser } from '@/services/authService';
import { API_BASE } from '@/config';
import { EmptyState } from '@/components/EmptyState';
import { TripSetup, defaultTripSetup } from '@/types/trip';

type TripCategory = 'active' | 'future' | 'past';

interface ApiTrip {
  trip_id: number;
  user_id: number;
  destination: string;
  start_date: string;
  end_date: string;
  preference_breakdown: Record<string, number> | null;
  max_walking_distance: number | null;
  preferred_transportation: 'walking' | 'public' | 'taxi' | null;
}

function parseApiDate(raw: string | null | undefined): Date | null {
  if (!raw) return null;
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed;
}

function tripCategory(trip: ApiTrip): TripCategory {
  const today = startOfDay(new Date());
  const startDate = parseApiDate(trip.start_date);
  const endDate = parseApiDate(trip.end_date);
  const start = startDate ? startOfDay(startDate) : null;
  const end = endDate ? startOfDay(endDate) : null;

  if (start && end) {
    if (isWithinInterval(today, { start, end })) return 'active';
    if (isBefore(today, start)) return 'future';
    if (isAfter(today, end)) return 'past';
  }
  return 'future';
}

function toTripSetup(trip: ApiTrip): TripSetup {
  const pref = trip.preference_breakdown ?? {};
  return {
    startDate: parseApiDate(trip.start_date),
    endDate: parseApiDate(trip.end_date),
    destination: trip.destination,
    preferences: {
      ...defaultTripSetup.preferences,
      ...pref,
    },
    constraints: {
      maxWalkingDistance: trip.max_walking_distance ?? defaultTripSetup.constraints.maxWalkingDistance,
      transportType: trip.preferred_transportation ?? defaultTripSetup.constraints.transportType,
    },
  };
}

const sectionConfig: Record<TripCategory, { label: string; icon: typeof Compass; emptyText: string }> = {
  active: { label: 'Active Trips', icon: Compass, emptyText: 'No trips happening right now' },
  future: { label: 'Upcoming Trips', icon: Calendar, emptyText: 'No upcoming trips planned' },
  past: { label: 'Past Trips', icon: CheckCircle2, emptyText: 'No past trips yet' },
};

export function TripsPage() {
  const navigate = useNavigate();
  const [trips, setTrips] = useState<ApiTrip[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ApiTrip | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const user = getCurrentUser();

  const loadTrips = async () => {
    if (!user) {
      navigate('/login', { replace: true });
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/trips?user_id=${user.id}`);
      const text = await res.text();
      if (!res.ok) {
        throw new Error(text || `Failed to load trips (${res.status})`);
      }
      const data = JSON.parse(text) as { trips?: ApiTrip[] };
      setTrips(Array.isArray(data.trips) ? data.trips : []);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load trips';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadTrips();
  }, []);

  const grouped = useMemo(
    () =>
      trips.reduce<Record<TripCategory, ApiTrip[]>>(
        (acc, trip) => {
          acc[tripCategory(trip)].push(trip);
          return acc;
        },
        { active: [], future: [], past: [] },
      ),
    [trips],
  );

  const handleOpen = (trip: ApiTrip) => {
    navigate('/trip', { state: { tripSetup: toTripSetup(trip), tripId: trip.trip_id } });
  };

  const handleEdit = (trip: ApiTrip) => {
    navigate('/wizard', { state: { editTripId: trip.trip_id, tripSetup: toTripSetup(trip) } });
  };

  const handleViewSummary = (trip: ApiTrip) => {
    navigate(`/trips/${trip.trip_id}/summary`);
  };

  const handleDelete = async (trip: ApiTrip) => {
    setIsDeleting(true);
    try {
      const res = await fetch(`${API_BASE}/api/trips/${trip.trip_id}`, { method: 'DELETE' });
      const text = await res.text();
      if (!res.ok) {
        throw new Error(text || `Failed to delete trip (${res.status})`);
      }
      setTrips((prev) => prev.filter((t) => t.trip_id !== trip.trip_id));
      setDeleteTarget(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to delete trip';
      setError(message);
    } finally {
      setIsDeleting(false);
    }
  };

  const formatDates = (trip: ApiTrip) => {
    const start = parseApiDate(trip.start_date);
    const end = parseApiDate(trip.end_date);
    if (!start || !end) return 'No dates set';
    return `${format(start, 'MMM d, yyyy')} – ${format(end, 'MMM d, yyyy')}`;
  };

  const renderTripCard = (trip: ApiTrip, category: TripCategory) => {
    const isPast = category === 'past';
    return (
      <article
        key={trip.trip_id}
        className={`group relative rounded-2xl border bg-card p-5 shadow-card hover:shadow-lg transition-all duration-300 hover:-translate-y-0.5 ${isPast ? 'opacity-80' : ''}`}
      >
        <div className="absolute top-3 right-3 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={() => setDeleteTarget(trip)}
            className="p-1.5 rounded-md bg-muted/80 hover:bg-destructive/10 transition-colors"
            title="Delete trip"
          >
            <Trash2 className="w-3.5 h-3.5 text-destructive" />
          </button>
        </div>

        <div className="flex items-start gap-3 mb-3">
          <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center flex-shrink-0">
            <MapPin className="w-5 h-5 text-primary" />
          </div>
          <div className="min-w-0">
            <h3 className="font-semibold text-base truncate">{trip.destination}</h3>
            <p className="text-xs text-muted-foreground">{formatDates(trip)}</p>
          </div>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground capitalize">
            {trip.preferred_transportation ?? 'walking'}
          </span>
          {category === 'active' && (
            <Button variant="default" size="sm" onClick={() => handleOpen(trip)} className="h-7 text-xs">
              Open Trip <ArrowRight className="w-3 h-3 ml-1" />
            </Button>
          )}
          {category === 'future' && (
            <Button variant="secondary" size="sm" onClick={() => handleEdit(trip)} className="h-7 text-xs">
              <Pencil className="w-3 h-3 mr-1" />
              Edit Preferences
            </Button>
          )}
          {category === 'past' && (
            <Button variant="secondary" size="sm" onClick={() => handleViewSummary(trip)} className="h-7 text-xs">
              <FileText className="w-3 h-3 mr-1" />
              View Summary
            </Button>
          )}
        </div>
      </article>
    );
  };

  const renderSection = (category: TripCategory) => {
    const config = sectionConfig[category];
    const Icon = config.icon;
    const sectionTrips = grouped[category];

    return (
      <section key={category} className="mb-8">
        <div className="flex items-center gap-2 mb-4">
          <Icon className="w-5 h-5 text-primary" />
          <h2 className="text-lg font-semibold">{config.label}</h2>
          <span className="text-sm text-muted-foreground">({sectionTrips.length})</span>
        </div>

        {sectionTrips.length === 0 ? (
          <p className="text-sm text-muted-foreground pl-7">{config.emptyText}</p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {sectionTrips.map((trip) => renderTripCard(trip, category))}
          </div>
        )}
      </section>
    );
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-20 bg-card/80 backdrop-blur-md border-b">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
          <Button variant="ghost" size="sm" onClick={() => navigate('/')}>
            <ArrowLeft className="w-4 h-4 mr-1" />
            Back
          </Button>
          <div className="flex items-center gap-2">
            <div className="w-9 h-9 rounded-xl bg-gradient-hero flex items-center justify-center">
              <Compass className="w-5 h-5 text-primary-foreground" />
            </div>
            <h1 className="text-xl font-bold">My Trips</h1>
          </div>
          <Button variant="default" size="sm" onClick={() => navigate('/wizard')}>
            <Plus className="w-4 h-4 mr-1.5" />
            New Trip
          </Button>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-8">
        {loading && <p className="text-sm text-muted-foreground">Loading your trips...</p>}

        {error && (
          <div className="mb-6 rounded-xl border border-destructive/40 bg-destructive/10 p-4">
            <p className="text-sm font-semibold text-destructive">Could not load trips</p>
            <p className="text-sm text-muted-foreground mt-1">{error}</p>
            <Button variant="outline" size="sm" className="mt-3" onClick={() => void loadTrips()}>
              Retry
            </Button>
          </div>
        )}

        {!loading && !error && trips.length === 0 && (
          <div className="py-16">
            <EmptyState
              title="No Trips Yet"
              description="Create your first trip and let AI plan the perfect itinerary for you."
            />
            <div className="flex justify-center mt-6">
              <Button variant="hero" size="xl" onClick={() => navigate('/wizard')}>
                <Plus className="w-5 h-5 mr-2" />
                Create Your First Trip
              </Button>
            </div>
          </div>
        )}

        {!loading && !error && trips.length > 0 && (
          <>
            {renderSection('active')}
            {renderSection('future')}
            {renderSection('past')}
          </>
        )}
      </main>

      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-foreground/45 backdrop-blur-sm animate-fade-in">
          <div className="w-full max-w-md rounded-2xl border bg-card shadow-2xl animate-scale-in">
            <div className="p-5">
              <h3 className="text-lg font-semibold">Delete trip?</h3>
              <p className="mt-2 text-sm text-muted-foreground">
                <span className="font-medium text-foreground">{deleteTarget.destination}</span>
                <br />
                {formatDates(deleteTarget)}
              </p>
              <p className="mt-3 text-sm text-muted-foreground">This action cannot be undone.</p>
            </div>
            <div className="px-5 pb-5 flex justify-end gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setDeleteTarget(null)}
                disabled={isDeleting}
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => void handleDelete(deleteTarget)}
                disabled={isDeleting}
              >
                {isDeleting ? 'Deleting...' : 'Delete Trip'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
