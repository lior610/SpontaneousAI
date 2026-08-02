import { Footprints, Flag } from 'lucide-react';

interface WalkFurtherPromptProps {
  /** Current walking radius (km), if known. */
  maxWalkingDistance: number | null;
  /** How many km the "walk further" action adds. */
  stepKm: number;
  /** True while the expand request is in flight. */
  isExpanding: boolean;
  onExpand: () => void;
  onFinish: () => void;
}

/**
 * Shown when the engine returns no attraction within the current walking radius.
 *
 * Instead of declaring the trip finished, we offer to widen the radius (which is
 * persisted to the trip in the DB) and keep exploring. Choosing to finish falls
 * back to the normal trip-complete summary.
 */
export function WalkFurtherPrompt({
  maxWalkingDistance,
  stepKm,
  isExpanding,
  onExpand,
  onFinish,
}: WalkFurtherPromptProps) {
  const nextRadius =
    maxWalkingDistance != null ? Number((maxWalkingDistance + stepKm).toFixed(2)) : null;

  return (
    <div className="max-w-lg mx-auto">
      <div className="rounded-2xl border bg-card shadow-sm p-6 text-center">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-accent/10 text-accent">
          <Footprints className="h-6 w-6" />
        </div>
        <h2 className="text-lg font-bold">Not enough nearby attractions</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          {maxWalkingDistance != null
            ? `We couldn't find anything else within ${maxWalkingDistance} km. Enlarge your max walking distance to keep exploring, or try again later when more places are open.`
            : "We couldn't find enough nearby attractions right now. Enlarge your max walking distance to keep exploring, or try again later when more places are open."}
        </p>

        <div className="mt-5 grid gap-3">
          <button
            onClick={onExpand}
            disabled={isExpanding}
            className="inline-flex items-center justify-center gap-2 w-full h-12 px-4 rounded-lg text-sm font-bold bg-gradient-to-r from-primary to-primary text-primary-foreground shadow-lg hover:-translate-y-0.5 hover:shadow-glow transition-all duration-300 disabled:opacity-60 disabled:translate-y-0"
          >
            <Footprints className="w-5 h-5" />
            {isExpanding
              ? 'Finding more…'
              : nextRadius != null
                ? `Enlarge walking distance (+${stepKm} km → ${nextRadius} km)`
                : `Enlarge walking distance (+${stepKm} km)`}
          </button>
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
