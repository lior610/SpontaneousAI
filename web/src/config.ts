import { Capacitor } from '@capacitor/core';

/**
 * API base URL for fetch calls.
 * On web (dev/prod), an empty string uses relative URLs and relies on Vite/Nginx proxy.
 * On native mobile apps (Android/iOS), requests must target the external backend server URL
 * provided via VITE_API_URL environment variable.
 */
export const API_BASE = (import.meta.env.VITE_API_URL as string) || (Capacitor.isNativePlatform() ? 'http://10.0.2.2:3000' : '');
