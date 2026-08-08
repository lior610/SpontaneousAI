import { Capacitor } from '@capacitor/core';
import { LocalNotifications } from '@capacitor/local-notifications';
import { Haptics, ImpactStyle } from '@capacitor/haptics';

export async function requestNotificationPermission(): Promise<boolean> {
  if (Capacitor.isNativePlatform()) {
    try {
      const perm = await LocalNotifications.requestPermissions();
      return perm.display === 'granted';
    } catch (err) {
      console.warn('[NativeNotificationService] Permission request failed:', err);
      return false;
    }
  }

  if (typeof window !== 'undefined' && 'Notification' in window) {
    if (Notification.permission === 'granted') return true;
    if (Notification.permission !== 'denied') {
      const res = await Notification.requestPermission();
      return res === 'granted';
    }
  }

  return false;
}

export async function triggerHapticFeedback(): Promise<void> {
  if (Capacitor.isNativePlatform()) {
    try {
      await Haptics.impact({ style: ImpactStyle.Heavy });
    } catch {
      // no-op
    }
  } else if (typeof navigator !== 'undefined' && 'vibrate' in navigator) {
    navigator.vibrate([200, 100, 200]);
  }
}

export async function sendArrivalNotification(title: string, body: string): Promise<void> {
  await triggerHapticFeedback();

  if (Capacitor.isNativePlatform()) {
    try {
      await LocalNotifications.schedule({
        notifications: [
          {
            id: Math.floor(Math.random() * 100000),
            title: title || 'You Arrived!',
            body: body || 'You reached your destination.',
            schedule: { at: new Date(Date.now() + 100) },
          },
        ],
      });
      return;
    } catch (err) {
      console.warn('[NativeNotificationService] LocalNotification failed:', err);
    }
  }

  if (typeof window !== 'undefined' && 'Notification' in window && Notification.permission === 'granted') {
    new Notification(title, { body, icon: '/logo.svg' });
  }
}

export async function sendDepartureNotification(title: string, body: string): Promise<void> {
  await triggerHapticFeedback();

  if (Capacitor.isNativePlatform()) {
    try {
      await LocalNotifications.schedule({
        notifications: [
          {
            id: Math.floor(Math.random() * 100000),
            title: title || 'Departed Location',
            body: body || 'Head towards your next stop!',
            schedule: { at: new Date(Date.now() + 100) },
          },
        ],
      });
      return;
    } catch (err) {
      console.warn('[NativeNotificationService] LocalNotification departure failed:', err);
    }
  }

  if (typeof window !== 'undefined' && 'Notification' in window && Notification.permission === 'granted') {
    new Notification(title, { body, icon: '/logo.svg' });
  }
}
