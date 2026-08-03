import React, { useEffect, useState } from 'react';
import { API_BASE } from '@/config';
import { showAppNotification, subscribeToNotifications } from '../services/notificationService';

export function NotificationProvider({ children }: { children: React.ReactNode }) {
  const [toast, setToast] = useState<{ title: string; body: string; id: number } | null>(null);

  useEffect(() => {
    // Listen for in-app fallback toasts
    const unsubscribe = subscribeToNotifications((title, body) => {
      setToast({ title, body, id: Date.now() });
      setTimeout(() => {
        setToast((prev) => (prev?.id === Date.now() ? null : prev));
      }, 5000);
    });

    // Only connect SSE if we have a logged in user
    const rawUser = window.localStorage.getItem('currentUser');
    if (!rawUser) return unsubscribe;
    
    let userId;
    try {
      userId = JSON.parse(rawUser).id;
    } catch (e) {
      return unsubscribe;
    }

    if (!userId) return unsubscribe;

    const eventSource = new EventSource(`${API_BASE}/api/notifications/stream?user_id=${userId}`);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'TRIP_GENERATED') {
          showAppNotification('Trip Ready!', 'Your trip has been fully generated and is ready to explore.');
        }
      } catch (err) {
        console.error('Failed to parse SSE message', err);
      }
    };

    eventSource.onerror = (err) => {
      console.error('SSE connection error:', err);
    };

    return () => {
      unsubscribe();
      eventSource.close();
    };
  }, []);

  return (
    <>
      {children}
      {toast && (
        <div className="fixed top-4 right-4 z-50 bg-white border border-slate-200 shadow-2xl rounded-lg p-4 w-80 animate-in slide-in-from-top fade-in duration-300">
          <div className="flex justify-between items-start mb-1">
            <h4 className="font-bold text-slate-800 text-sm">{toast.title}</h4>
            <button onClick={() => setToast(null)} className="text-slate-400 hover:text-slate-600 text-xs">
              ✕
            </button>
          </div>
          <p className="text-sm text-slate-600">{toast.body}</p>
        </div>
      )}
    </>
  );
}
