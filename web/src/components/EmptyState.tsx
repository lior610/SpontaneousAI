import { MapPinOff, RefreshCw } from 'lucide-react';

interface EmptyStateProps {
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
}

export function EmptyState({ title, description, actionLabel, onAction }: EmptyStateProps) {
  return (
    <div className="max-w-md mx-auto rounded-xl border bg-card/80 backdrop-blur-md border-border/50 animate-scale-in">
      <div className="flex flex-col items-center text-center p-8">
        <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center mb-4">
          <MapPinOff className="w-8 h-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold mb-2">{title}</h3>
        <p className="text-muted-foreground text-sm mb-6">{description}</p>
        {actionLabel && onAction && (
          <button
            onClick={onAction}
            className="inline-flex items-center justify-center gap-2 h-11 px-6 rounded-lg text-sm font-semibold bg-primary text-primary-foreground hover:bg-primary/90 shadow-md hover:shadow-lg hover:-translate-y-0.5 transition-all duration-300"
          >
            <RefreshCw className="w-4 h-4" />
            {actionLabel}
          </button>
        )}
      </div>
    </div>
  );
}
