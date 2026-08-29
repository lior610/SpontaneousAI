import { useState } from 'react';
import { Footprints, Flag, Bus } from 'lucide-react';

interface WalkFurtherPromptProps {
  /** Current walking radius (km), if known. */
  maxWalkingDistance: number | null;
  /** How many km the "walk further" action adds. */
  stepKm: number;
  /** True while any request is in flight. */
  isExpanding: boolean;
  onExpand: () => void;
  onEnableTransit?: (minutes: number) => void;
  onFinish: () => void;
}

/**
 * Shown when the engine returns no attraction within the current walking radius.
 *
 * Users can either widen the walking radius or enable public transportation
 * with a quick-select travel time slider to reach farther attractions.
 */
export function WalkFurtherPrompt({
  maxWalkingDistance,
  stepKm,
  isExpanding,
  onExpand,
  onEnableTransit,
  onFinish,
}: WalkFurtherPromptProps) {
  const [transitMinutes, setTransitMinutes] = useState(30);
  const [showTransitConfig, setShowTransitConfig] = useState(false);

  const nextRadius =
    maxWalkingDistance != null ? Number((maxWalkingDistance + stepKm).toFixed(2)) : null;

  return (
    <div className="max-w-lg mx-auto">
      <div className="rounded-2xl border bg-card shadow-card p-6 text-center">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-accent/10 text-accent">
          <Footprints className="h-6 w-6" />
        </div>
        <h2 className="text-lg font-bold">Not enough nearby attractions</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          {maxWalkingDistance != null
            ? `We couldn't find anything else within ${maxWalkingDistance} km. Enlarge your walking distance, switch to public transport to explore further, or try again later.`
            : "We couldn't find enough nearby attractions right now. Enlarge your walking distance, switch to public transport, or try again later."}
        </p>

        <div className="mt-5 grid gap-3">
          {/* Option 1: Enlarge walking distance */}
          <button
            onClick={onExpand}
            disabled={isExpanding}
            className="inline-flex items-center justify-center gap-2 w-full h-12 px-4 rounded-lg text-sm font-bold bg-primary text-primary-foreground shadow-sm hover:shadow-glow hover:-translate-y-0.5 transition-all duration-300 disabled:opacity-60 disabled:translate-y-0"
          >
            <Footprints className="w-5 h-5" />
            {isExpanding
              ? 'Finding more…'
              : nextRadius != null
                ? `Enlarge walking distance (+${stepKm} km → ${nextRadius} km)`
                : `Enlarge walking distance (+${stepKm} km)`}
          </button>

          {/* Option 2: Enable Public Transport */}
          {onEnableTransit && (
            <div className="rounded-xl border border-primary/20 bg-primary/5 p-4 text-left space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Bus className="w-4 h-4 text-primary" />
                  <span className="text-sm font-semibold text-foreground">
                    Or switch to Public Transport
                  </span>
                </div>
                {!showTransitConfig ? (
                  <button
                    type="button"
                    onClick={() => setShowTransitConfig(true)}
                    className="text-xs text-primary font-medium underline hover:text-primary/80"
                  >
                    Adjust time ({transitMinutes}m)
                  </button>
                ) : (
                  <span className="text-xs font-bold text-primary">{transitMinutes} min max</span>
                )}
              </div>

              {showTransitConfig && (
                <div className="space-y-2 pt-1 animate-fade-in">
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>Max ride duration</span>
                    <span className="font-semibold text-primary">{transitMinutes} minutes</span>
                  </div>
                  <input
                    type="range"
                    min={10}
                    max={60}
                    step={5}
                    value={transitMinutes}
                    onChange={(e) => setTransitMinutes(Number(e.target.value))}
                    className="w-full h-2 bg-muted rounded-full appearance-none cursor-pointer accent-primary"
                  />
                  <div className="flex justify-between gap-1">
                    {[15, 30, 45, 60].map((preset) => (
                      <button
                        key={preset}
                        type="button"
                        onClick={() => setTransitMinutes(preset)}
                        className={`text-xs px-2 py-1 rounded-md transition-colors ${
                          transitMinutes === preset
                            ? 'bg-primary text-primary-foreground font-semibold'
                            : 'bg-muted text-muted-foreground hover:bg-muted/80'
                        }`}
                      >
                        {preset}m
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <button
                type="button"
                onClick={() => onEnableTransit(transitMinutes)}
                disabled={isExpanding}
                className="inline-flex items-center justify-center gap-2 w-full h-11 px-4 rounded-lg text-sm font-bold bg-primary text-primary-foreground hover:bg-primary/90 transition-all duration-200 disabled:opacity-60"
              >
                <Bus className="w-4 h-4" />
                {isExpanding ? 'Enabling transit…' : `Enable Public Transport (${transitMinutes} min cap)`}
              </button>
            </div>
          )}

          {/* Option 3: Finish trip */}
          <button
            onClick={onFinish}
            disabled={isExpanding}
            className="inline-flex items-center justify-center gap-2 w-full h-12 px-4 rounded-lg text-sm font-semibold border-2 border-border text-foreground bg-transparent hover:bg-muted transition-all duration-300 disabled:opacity-60"
          >
            <Flag className="w-4 h-4" />
            Try again later / finish trip
          </button>
        </div>
      </div>
    </div>
  );
}

