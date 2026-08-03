// Base notification service for SpontaneousAI
// Wraps the browser Notification API and provides fallbacks

export async function requestNotificationPermission(): Promise<NotificationPermission> {
  if (!('Notification' in window)) {
    console.warn('This browser does not support desktop notification');
    return 'denied';
  }

  if (Notification.permission !== 'denied' && Notification.permission !== 'granted') {
    return await Notification.requestPermission();
  }

  return Notification.permission;
}

type NotificationListener = (title: string, body: string, data?: any) => void;
const listeners: NotificationListener[] = [];

export function subscribeToNotifications(listener: NotificationListener) {
  listeners.push(listener);
  return () => {
    const idx = listeners.indexOf(listener);
    if (idx !== -1) listeners.splice(idx, 1);
  };
}

export async function showAppNotification(title: string, body: string, data?: any) {
  // Always trigger in-app listeners (useful for fallback or if OS blocks native)
  listeners.forEach((fn) => fn(title, body, data));

  if (!('Notification' in window)) {
    console.log(`[Notification Fallback] ${title}: ${body}`, data);
    return;
  }

  const permission = await requestNotificationPermission();

  if (permission === 'granted') {
    try {
      const notification = new Notification(title, {
        body,
        icon: '/logo.svg',
        data,
      });

      notification.onclick = function () {
        window.focus();
        this.close();
      };
    } catch (err) {
      console.error('[NotificationService] Failed to show native notification:', err);
    }
  } else {
    console.log(`[Notification Denied Fallback] ${title}: ${body}`, data);
  }
}
