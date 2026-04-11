import { useState } from 'react';
import { ThumbsUp, ThumbsDown, Clock, Footprints, DollarSign, Pill, HeartPulse, ShoppingCart, Store, ShieldAlert, X } from 'lucide-react';
import { Activity } from '@/types/trip';
import { featureFlags } from '@/config/featureFlags';

interface FeedbackPopupProps {
  activity: Activity;
  onSubmit: (feedback: Activity['feedback'], needSpecific?: string) => void;
  onClose: () => void;
}

const allFeedbackOptions = [
  { key: 'liked', icon: ThumbsUp, label: 'Liked it', positive: true },
  { key: 'disliked', icon: ThumbsDown, label: "Didn't like", positive: false },
  { key: 'tooLong', icon: Clock, label: 'Too long', positive: false },
  { key: 'tooFar', icon: Footprints, label: 'Too far', positive: false },
  { key: 'tooExpensive', icon: DollarSign, label: 'Too expensive', positive: false },
] as const;

const specificNeeds = [
  { key: 'pharmacy', icon: Pill, label: 'Pharmacy' },
  { key: 'medical', icon: HeartPulse, label: 'Medical' },
  { key: 'grocery', icon: ShoppingCart, label: 'Grocery' },
  { key: 'convenience', icon: Store, label: 'Convenience' },
  { key: 'police_emergency', icon: ShieldAlert, label: 'Police Emergency' },
] as const;

export function FeedbackPopup({ activity, onSubmit, onClose }: FeedbackPopupProps) {
  const [selectedFeedback, setSelectedFeedback] = useState<string | null>(null);
  const [showSpecificNeeds, setShowSpecificNeeds] = useState(false);
  const feedbackOptions = featureFlags.feedbackPopup.showExtendedFeedbackOptions
    ? allFeedbackOptions
    : allFeedbackOptions.filter((option) => option.key === 'liked' || option.key === 'disliked');

  const handleSubmit = () => {
    const feedback: Activity['feedback'] = {};
    if (selectedFeedback === 'liked') feedback.liked = true;
    if (selectedFeedback === 'disliked') feedback.liked = false;
    if (selectedFeedback === 'tooLong') feedback.tooLong = true;
    if (selectedFeedback === 'tooFar') feedback.tooFar = true;
    if (selectedFeedback === 'tooExpensive') feedback.tooExpensive = true;
    onSubmit(feedback);
  };

  const handleSpecificNeed = (need: string) => {
    onSubmit({}, need);
  };

  return (
    <div className="fixed inset-0 bg-foreground/50 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-fade-in">
      <div className="w-full max-w-md rounded-xl border bg-card shadow-lg animate-scale-in">
        <div className="relative p-5">
          <button
            onClick={onClose}
            className="absolute right-3 top-3 w-10 h-10 flex items-center justify-center rounded-lg text-foreground hover:bg-muted transition-all"
          >
            <X className="w-5 h-5" />
          </button>
          <h3 className="text-xl font-bold text-center pr-8">
            How was {activity.title}? 🎯
          </h3>
        </div>

        <div className="p-5 pt-0 space-y-6">
          {!showSpecificNeeds ? (
            <>
              <div className="grid grid-cols-2 gap-3">
                {feedbackOptions.map(({ key, icon: Icon, label, positive }) => (
                  <button
                    key={key}
                    onClick={() => setSelectedFeedback(key)}
                    className={`flex items-center gap-2 p-4 rounded-xl border-2 transition-all duration-200 ${
                      selectedFeedback === key
                        ? positive
                          ? 'border-secondary bg-secondary/10 text-secondary'
                          : 'border-accent bg-accent/10 text-accent'
                        : 'border-border hover:border-primary/30 hover:bg-muted'
                    }`}
                  >
                    <Icon className="w-5 h-5" />
                    <span className="font-medium text-sm">{label}</span>
                  </button>
                ))}
              </div>

              {featureFlags.feedbackPopup.showSpecificNeeds && (
                <button
                  onClick={() => setShowSpecificNeeds(true)}
                  className="w-full p-3 text-center text-muted-foreground hover:text-primary border border-dashed border-border rounded-xl hover:border-primary/30 transition-all duration-200"
                >
                  🎯 I need something specific right now
                </button>
              )}

              <button
                onClick={handleSubmit}
                disabled={!selectedFeedback}
                className="w-full h-12 rounded-xl text-base font-bold bg-gradient-to-r from-accent to-accent-light text-accent-foreground shadow-lg hover:shadow-glow hover:-translate-y-1 hover:scale-105 transition-all duration-300 disabled:opacity-50 disabled:pointer-events-none"
              >
                Generate Next Activity →
              </button>
            </>
          ) : (
            <>
              <p className="text-center text-muted-foreground">What do you need right now?</p>
              <div className="grid grid-cols-2 gap-3">
                {specificNeeds.map(({ key, icon: Icon, label }) => (
                  <button
                    key={key}
                    onClick={() => handleSpecificNeed(key)}
                    className="flex flex-col items-center gap-2 p-4 rounded-xl border-2 border-border hover:border-accent hover:bg-accent/10 transition-all duration-200"
                  >
                    <Icon className="w-6 h-6 text-accent" />
                    <span className="font-medium text-sm">{label}</span>
                  </button>
                ))}
              </div>
              
              <button
                onClick={() => setShowSpecificNeeds(false)}
                className="w-full h-11 rounded-lg text-sm font-semibold text-foreground hover:bg-muted transition-all duration-300"
              >
                ← Back to feedback
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
