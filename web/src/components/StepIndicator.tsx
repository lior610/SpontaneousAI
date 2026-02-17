import { Check } from 'lucide-react';

interface StepIndicatorProps {
  currentStep: number;
  totalSteps: number;
  labels: string[];
}

export function StepIndicator({ currentStep, totalSteps, labels }: StepIndicatorProps) {
  return (
    <div className="w-full px-4 py-6">
      <div className="flex items-center justify-between relative">
        {/* Progress line background */}
        <div className="absolute top-4 left-0 right-0 h-1 bg-muted rounded-full" />
        
        {/* Progress line filled */}
        <div 
          className="absolute top-4 left-0 h-1 bg-gradient-hero rounded-full transition-all duration-500 ease-out"
          style={{ width: `${((currentStep - 1) / (totalSteps - 1)) * 100}%` }}
        />

        {Array.from({ length: totalSteps }, (_, i) => i + 1).map((step) => (
          <div key={step} className="relative z-10 flex flex-col items-center">
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center font-semibold text-sm transition-all duration-300 shadow-sm ${
                step < currentStep
                  ? 'bg-secondary text-secondary-foreground'
                  : step === currentStep
                  ? 'bg-primary text-primary-foreground shadow-md scale-110'
                  : 'bg-muted text-muted-foreground'
              }`}
            >
              {step < currentStep ? <Check className="w-4 h-4" /> : step}
            </div>
            <span
              className={`mt-2 text-xs font-medium transition-colors duration-300 ${
                step === currentStep
                  ? 'text-primary'
                  : step < currentStep
                  ? 'text-secondary'
                  : 'text-muted-foreground'
              }`}
            >
              {labels[step - 1]}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
