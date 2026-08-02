import { Sparkles, MapPin, ArrowRight } from 'lucide-react';
import { CompanionSuggestion } from '@/services/tripService';

interface CompanionSuggestionPopupProps {
  suggestion: CompanionSuggestion;
  onAccept: () => void;
  onDismiss: () => void;
}

/**
 * "Because you liked X, you might also like Y" prompt.
 *
 * Shown after a user likes an attraction that belongs to a popular trip matching
 * their persona. Accepting makes the suggested attraction the next activity;
 * dismissing continues with the normal recommendation flow.
 */
export function CompanionSuggestionPopup({ suggestion, onAccept, onDismiss }: CompanionSuggestionPopupProps) {
  const { activity, reason, distance_km } = suggestion;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-foreground/45 backdrop-blur-sm animate-fade-in"
      onClick={onDismiss}
    >
      <div
        className="w-full max-w-md rounded-2xl border bg-card shadow-2xl animate-scale-in"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="p-6">
          <div className="flex items-center gap-2 text-sm font-medium text-accent">
            <Sparkles className="w-4 h-4" />
            You might also like
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            {reason ?? 'Based on what you just liked, here is another popular spot for you.'}
          </p>

          <div className="mt-4 rounded-xl border bg-gradient-to-br from-card to-accent/5 p-4">
            <h3 className="text-lg font-bold">{activity.title}</h3>
            {activity.description && (
              <p className="mt-1 text-sm text-muted-foreground line-clamp-3">{activity.description}</p>
            )}
            <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
              {activity.cost && <span className="font-medium">{activity.cost}</span>}
              {activity.address && (
                <span className="inline-flex items-center gap-1">
                  <MapPin className="w-3.5 h-3.5" />
                  {activity.address}
                </span>
              )}
              {distance_km != null && <span>{distance_km} km away</span>}
            </div>
          </div>

          <div className="mt-5 grid gap-3">
            <button
              onClick={onAccept}
              className="inline-flex items-center gap-3 w-full h-12 px-4 rounded-lg text-sm font-bold bg-gradient-to-r from-secondary to-secondary text-secondary-foreground shadow-lg hover:-translate-y-0.5 hover:shadow-glow transition-all duration-300"
            >
              <ArrowRight className="w-5 h-5" />
              Show me this next
            </button>
            <button
              onClick={onDismiss}
              className="inline-flex items-center gap-3 w-full h-12 px-4 rounded-lg text-sm font-semibold border-2 border-border text-foreground bg-transparent hover:bg-muted transition-all duration-300"
            >
              No thanks, something else
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
