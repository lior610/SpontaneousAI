import { MapPin, Navigation, Star, Clock, DollarSign, ExternalLink, Bus, Footprints } from 'lucide-react';
import { Activity } from '@/types/trip';
import { featureFlags } from '@/config/featureFlags';

interface ActivityCardProps {
  activity: Activity;
  onComplete: () => void;
  isLoading?: boolean;
  onTooFar?: () => void;
  onPreferWalk?: () => void;
}

const categoryIcons: Record<string, string> = {
  food: '🍜',
  nature: '🌲',
  culture: '🎭',
  nightlife: '🎉',
  general: '📍',
};

const categoryColors: Record<string, string> = {
  food: 'bg-accent/10 text-accent border-accent/20',
  nature: 'bg-secondary/10 text-secondary border-secondary/20',
  culture: 'bg-primary/10 text-primary border-primary/20',
  nightlife: 'bg-accent/10 text-accent border-accent/20',
  general: 'bg-muted text-muted-foreground border-border',
};

export function ActivityCard({ activity, onComplete, isLoading, onTooFar, onPreferWalk }: ActivityCardProps) {
  const isTransit = activity.reachableBy === 'transit';
  const handleNavigate = () => {
    const encodedAddress = encodeURIComponent(activity.address);
    window.open(`https://www.google.com/maps/search/?api=1&query=${encodedAddress}`, '_blank');
  };

  return (
    <div className="rounded-xl border-2 border-transparent hover:border-primary/20 bg-card shadow-card hover:shadow-lg transition-all duration-300 overflow-hidden animate-scale-in">
      <div className="p-5 pb-2">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border ${categoryColors[activity.category]}`}>
              {categoryIcons[activity.category]} {activity.category.charAt(0).toUpperCase() + activity.category.slice(1)}
            </span>
          </div>
          {(featureFlags.tripSuggestionCard.showRating || featureFlags.tripSuggestionCard.showReviewCount) && (
            <div className="flex items-center gap-1 text-accent">
              {featureFlags.tripSuggestionCard.showRating && (
                <>
                  <Star className="w-4 h-4 fill-accent" />
                  <span className="font-semibold">{activity.rating}</span>
                </>
              )}
              {featureFlags.tripSuggestionCard.showReviewCount && (
                <span className="text-muted-foreground text-sm">({activity.reviewCount})</span>
              )}
            </div>
          )}
        </div>
        <h3 className="text-lg font-bold mt-3">{activity.title}</h3>
        {isTransit && (
          <div className="mt-2 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border bg-primary/10 text-primary border-primary/20">
            <Bus className="w-3.5 h-3.5" />
            {activity.transitMinutes != null
              ? `~${activity.transitMinutes} min by public transport`
              : 'A short ride by public transport'}
            {activity.transitSummary ? ` · ${activity.transitSummary}` : ''}
          </div>
        )}
      </div>

      <div className="p-5 pt-0 space-y-4">
        <p className="text-muted-foreground text-sm leading-relaxed">
          {activity.description}
        </p>

        {/* Quick Info */}
        <div className="flex flex-wrap gap-3">
          {featureFlags.tripSuggestionCard.showEstimatedTime && (
            <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
              <Clock className="w-4 h-4 text-primary" />
              <span>{activity.estimatedTime}</span>
            </div>
          )}
          <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <DollarSign className="w-4 h-4 text-secondary" />
            <span>{activity.cost}</span>
          </div>
          <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <MapPin className="w-4 h-4 text-accent" />
            <span className="truncate max-w-[150px]">{activity.address}</span>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex gap-3 pt-2">
          <button
            onClick={handleNavigate}
            className="flex-1 inline-flex items-center justify-center gap-2 h-11 px-6 rounded-lg text-sm font-semibold border-2 border-primary text-primary bg-transparent hover:bg-primary hover:text-primary-foreground transition-all duration-300"
          >
            <Navigation className="w-4 h-4" />
            Navigate
            <ExternalLink className="w-3 h-3" />
          </button>
          <button
            onClick={onComplete}
            disabled={isLoading}
            className="flex-1 inline-flex items-center justify-center gap-2 h-11 px-6 rounded-lg text-sm font-bold bg-gradient-to-r from-accent to-accent-light text-accent-foreground shadow-lg hover:shadow-glow hover:-translate-y-1 hover:scale-105 transition-all duration-300 disabled:opacity-50 disabled:pointer-events-none"
          >
            {isLoading ? 'Loading...' : 'Done! Next →'}
          </button>
        </div>
        {isTransit && (onTooFar || onPreferWalk) && (
          <div className="flex gap-3">
            {onTooFar && (
              <button
                onClick={onTooFar}
                disabled={isLoading}
                className="flex-1 inline-flex items-center justify-center gap-2 h-10 px-4 rounded-lg text-sm font-semibold border text-foreground hover:bg-muted transition-all disabled:opacity-50"
              >
                Too far
              </button>
            )}
            {onPreferWalk && (
              <button
                onClick={onPreferWalk}
                disabled={isLoading}
                className="flex-1 inline-flex items-center justify-center gap-2 h-10 px-4 rounded-lg text-sm font-semibold border text-foreground hover:bg-muted transition-all disabled:opacity-50"
              >
                <Footprints className="w-4 h-4" />
                I'd rather walk
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
