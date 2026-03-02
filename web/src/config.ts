/**
 * API base URL for fetch calls.
 * In development we use relative URLs so the Vite proxy (vite.config.js proxy /api → localhost:3000)
 * handles requests—same origin, no CORS. Ensure the API is running on port 3000 (e.g. npm run dev in api/).
 * In production, use relative URLs so the same origin is used.
 */
export const API_BASE = '';
