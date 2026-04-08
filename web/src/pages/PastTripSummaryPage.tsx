import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { eachDayOfInterval, format, isSameDay, isValid } from 'date-fns';
import { ArrowLeft, CalendarDays, MapPin, Route } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { API_BASE } from '@/config';
import { fetchCompletedActivities, CompletedActivityLog } from '@/services/tripService';

interface ApiTrip {
  trip_id: number;
  destination: string;
  start_date: string;
  end_date: string;
  preference_breakdown: Record<string, number> | null;
}

function parseApiDate(raw: string | null | undefined): Date | null {
  if (!raw) return null;
  const parsed = new Date(raw);
  if (!isValid(parsed)) return null;
  return parsed;
}

export function PastTripSummaryPage() {
  const navigate = useNavigate();
  const { tripId } = useParams();
  const [trip, setTrip] = useState<ApiTrip | null>(null);
  const [completedLogs, setCompletedLogs] = useState<CompletedActivityLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadTrip = async () => {
      if (!tripId) {
        setError('Missing trip id');
        setLoading(false);
        return;
      }
      try {
        setLoading(true);
        const res = await fetch(`${API_BASE}/api/trips/${tripId}`);
        const text = await res.text();
        if (!res.ok) {
          throw new Error(text || `Failed to load trip (${res.status})`);
        }
        const data = JSON.parse(text) as { trip?: ApiTrip };
        if (!data.trip) throw new Error('Trip not found');
        setTrip(data.trip);
        const completed = await fetchCompletedActivities(Number(tripId));
        setCompletedLogs(completed);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load trip summary');
      } finally {
        setLoading(false);
      }
    };

    void loadTrip();
  }, [tripId]);

  const tripDays = useMemo(() => {
    if (!trip) return [] as Date[];
    const start = parseApiDate(trip.start_date);
    const end = parseApiDate(trip.end_date);
    if (!start || !end || end < start) return [] as Date[];
    return eachDayOfInterval({ start, end });
  }, [trip]);

  const logsByDay = useMemo(() => {
    return tripDays.map((day) => ({
      day,
      logs: completedLogs.filter((log) => {
        const completedAt = parseApiDate(log.completed_at);
        return completedAt ? isSameDay(completedAt, day) : false;
      }),
    }));
  }, [completedLogs, tripDays]);

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-20 bg-card/80 backdrop-blur-md border-b">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
          <Button variant="ghost" size="sm" onClick={() => navigate('/trips')}>
            <ArrowLeft className="w-4 h-4 mr-1" />
            Back to Trips
          </Button>
          <h1 className="text-xl font-bold">Past Trip Summary</h1>
          <div className="w-24" />
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-8">
        {loading && <p className="text-sm text-muted-foreground">Loading summary...</p>}

        {error && (
          <div className="rounded-xl border border-destructive/40 bg-destructive/10 p-4">
            <p className="text-sm font-semibold text-destructive">Could not load summary</p>
            <p className="text-sm text-muted-foreground mt-1">{error}</p>
          </div>
        )}

        {!loading && !error && trip && (
          <div className="space-y-6">
            <section className="rounded-2xl border bg-card p-5">
              <h2 className="text-lg font-semibold flex items-center gap-2">
                <MapPin className="w-4 h-4 text-primary" />
                {trip.destination}
              </h2>
              <p className="text-sm text-muted-foreground mt-1">
                {parseApiDate(trip.start_date) ? format(parseApiDate(trip.start_date) as Date, 'MMM d, yyyy') : trip.start_date}
                {' - '}
                {parseApiDate(trip.end_date) ? format(parseApiDate(trip.end_date) as Date, 'MMM d, yyyy') : trip.end_date}
              </p>
            </section>

            <section className="space-y-3">
              <h3 className="text-base font-semibold flex items-center gap-2">
                <CalendarDays className="w-4 h-4 text-secondary" />
                Day-by-day summary
              </h3>

              {tripDays.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  No valid date range found for this trip.
                </p>
              )}

              {logsByDay.map(({ day, logs }, index) => (
                <article key={day.toISOString()} className="rounded-xl border bg-card p-4">
                  <p className="text-sm font-semibold">
                    Day {index + 1} · {format(day, 'EEEE, MMM d, yyyy')}
                  </p>

                  {logs.length === 0 && (
                    <p className="mt-2 text-sm text-muted-foreground">
                      No completed activities recorded for this day.
                    </p>
                  )}

                  {logs.length > 0 && (
                    <div className="mt-3 space-y-2">
                      {logs.map((log) => (
                        <div key={log.id} className="rounded-lg border bg-muted/30 p-3">
                          <p className="text-sm font-medium">{log.title}</p>
                          {log.address && (
                            <p className="text-xs text-muted-foreground mt-1">{log.address}</p>
                          )}
                          <div className="mt-2 inline-flex items-center gap-1 text-xs text-muted-foreground">
                            <Route className="w-3.5 h-3.5" />
                            Completed at {format(new Date(log.completed_at), 'HH:mm')}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </article>
              ))}
            </section>
          </div>
        )}
      </main>
    </div>
  );
}
