import { Capacitor } from '@capacitor/core';

/**
 * API base URL for fetch calls.
 * On web (dev/prod), an empty string uses relative URLs and relies on Vite/Nginx proxy.
 * On native mobile apps (Android/iOS), requests target the backend server URL.
 * Defaults to production domain https://spontai.cs.colman.ac.il when VITE_API_URL is not set.
 */
export const API_BASE = (import.meta.env.VITE_API_URL as string) || (Capacitor.isNativePlatform() ? 'https://spontai.cs.colman.ac.il' : '');
