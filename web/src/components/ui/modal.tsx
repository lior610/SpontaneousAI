import { ReactNode } from 'react';

interface ModalProps {
  onDismiss: () => void;
  children: ReactNode;
}

/** Shared overlay + card shell for centered popup dialogs. */
export function Modal({ onDismiss, children }: ModalProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-foreground/45 backdrop-blur-sm animate-fade-in"
      onClick={onDismiss}
    >
      <div
        className="w-full max-w-md rounded-2xl border bg-card shadow-2xl animate-scale-in"
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}
