import { ThumbsUp, Ban, ArrowRight } from 'lucide-react';
import { Activity } from '@/types/trip';

export type FeedbackChoice = 'liked' | 'skipped' | 'next';

interface FeedbackPopupProps {
  activity: Activity;
  onSubmit: (choice: FeedbackChoice) => void;
  onClose: () => void;
}

export function FeedbackPopup({ activity, onSubmit, onClose }: FeedbackPopupProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-foreground/45 backdrop-blur-sm animate-fade-in"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-2xl border bg-card shadow-2xl animate-scale-in"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="p-6">
          <h3 className="text-lg font-bold">How was {activity.title}?</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Tell us so we can fine-tune your next suggestions.
          </p>

          <div className="mt-5 grid gap-3">
            <button
              onClick={() => onSubmit('liked')}
              className="inline-flex items-center gap-3 w-full h-12 px-4 rounded-lg text-sm font-bold bg-gradient-to-r from-secondary to-secondary text-secondary-foreground shadow-lg hover:-translate-y-0.5 hover:shadow-glow transition-all duration-300"
            >
              <ThumbsUp className="w-5 h-5" />
              Liked it
            </button>

            <button
              onClick={() => onSubmit('skipped')}
              className="inline-flex items-center gap-3 w-full h-12 px-4 rounded-lg text-sm font-semibold border-2 border-destructive/40 text-destructive bg-transparent hover:bg-destructive/10 transition-all duration-300"
            >
              <Ban className="w-5 h-5" />
              Skip
              <span className="ml-auto text-xs font-normal text-muted-foreground">
                Show me fewer like this
              </span>
            </button>

            <button
              onClick={() => onSubmit('next')}
              className="inline-flex items-center gap-3 w-full h-12 px-4 rounded-lg text-sm font-semibold border-2 border-border text-foreground bg-transparent hover:bg-muted transition-all duration-300"
            >
              <ArrowRight className="w-5 h-5" />
              Next
              <span className="ml-auto text-xs font-normal text-muted-foreground">
                We'll figure it out
              </span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
