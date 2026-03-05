import { Loader2, Compass } from 'lucide-react';

export function LoadingSpinner() {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-12 animate-fade-in">
      <div className="relative">
        <div className="w-16 h-16 rounded-full border-4 border-muted animate-spin-slow">
          <div className="absolute inset-0 rounded-full border-4 border-t-primary border-r-transparent border-b-transparent border-l-transparent animate-spin" />
        </div>
        <Compass className="absolute inset-0 m-auto w-6 h-6 text-primary animate-pulse" />
      </div>
      <div className="text-center">
        <p className="font-semibold text-foreground">Finding your next adventure...</p>
        <p className="text-sm text-muted-foreground">Our AI is working its magic ✨</p>
      </div>
    </div>
  );
}

export function SimpleLoader() {
  return (
    <div className="flex items-center justify-center p-4">
      <Loader2 className="w-6 h-6 text-primary animate-spin" />
    </div>
  );
}
