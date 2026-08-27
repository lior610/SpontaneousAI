import { Bus, Flag, Footprints } from 'lucide-react';

interface TransitFurtherPromptProps {
  isExpanding: boolean;
  onAcceptTransit: () => void;
  onWalkFurther?: () => void;
  onFinish: () => void;
  walkFurtherStepKm?: number;
}

/**
 * Shown when walkable attractions are exhausted but transit-reachable places remain.
 */
export function TransitFurtherPrompt({
  isExpanding,
  onAcceptTransit,
  onWalkFurther,
  onFinish,
  walkFurtherStepKm = 1,
}: TransitFurtherPromptProps) {
  return (
    <div className="max-w-lg mx-auto">
      <div className="rounded-2xl border bg-card shadow-sm p-6 text-center">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
          <Bus className="h-6 w-6" />
        </div>
        <h2 className="text-lg font-bold">Go a bit further by public transport?</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Nothing else is within walking distance, but there are highly matched places a short ride away.
        </p>

        <div className="mt-5 grid gap-3">
          <button
            onClick={onAcceptTransit}
            disabled={isExpanding}
            className="inline-flex items-center justify-center gap-2 w-full h-12 px-4 rounded-lg text-sm font-bold bg-gradient-to-r from-primary to-primary text-primary-foreground shadow-lg hover:-translate-y-0.5 hover:shadow-glow transition-all duration-300 disabled:opacity-60 disabled:translate-y-0"
          >
            <Bus className="w-5 h-5" />
            {isExpanding ? 'Finding more…' : 'Suggest places a short ride away'}
          </button>
          {onWalkFurther && (
            <button
              onClick={onWalkFurther}
              disabled={isExpanding}
              className="inline-flex items-center justify-center gap-2 w-full h-12 px-4 rounded-lg text-sm font-semibold border-2 border-border text-foreground bg-transparent hover:bg-muted transition-all duration-300 disabled:opacity-60"
            >
              <Footprints className="w-4 h-4" />
              Enlarge walking distance instead (+{walkFurtherStepKm} km)
            </button>
          )}
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
