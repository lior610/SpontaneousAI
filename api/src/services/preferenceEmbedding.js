/**
 * Triggers the Python engine to build/persist user–trip preference embeddings.
 */
import axios from 'axios';
import * as usersDb from '../db/usersConnection.js';

function engineBaseUrl() {
  if (process.env.ENGINE_URL && process.env.ENGINE_URL.trim()) {
    return process.env.ENGINE_URL.replace(/\/$/, '');
  }
  const host = process.env.ENGINE_HOST || 'localhost';
  const port = process.env.ENGINE_PORT || '8000';
  return `http://${host}:${port}`;
}

/**
 * Build preference embedding for one trip (writes user_preference_embeddings).
 */
export async function buildUserTripPreferenceEmbedding(userId, tripId) {
  const url = `${engineBaseUrl()}/preferences/build`;
  await axios.post(
    url,
    { user_id: userId, trip_id: tripId, force_rebuild: true },
    { timeout: 180000 },
  );
}

/**
 * Build embeddings for every trip owned by the user (e.g. after profile preference change).
 */
export async function buildPreferenceEmbeddingsForUser(userId) {
  const r = await usersDb.query('SELECT trip_id FROM trips WHERE user_id = $1', [userId]);
  for (const row of r.rows) {
    const tid = row.trip_id;
    try {
      await buildUserTripPreferenceEmbedding(userId, tid);
    } catch (err) {
      console.error(
        `[preference embedding] user_id=${userId} trip_id=${tid}:`,
        err.message || err,
      );
    }
  }
}
