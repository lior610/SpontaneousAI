/**
 * Ask the attraction engine to compute and store user_preference_embeddings for a trip.
 * Failures are logged only — trip/user HTTP handlers still succeed if the engine is down.
 */

import axios from 'axios';

function getEngineBaseUrl() {
  const rawHost = process.env.ENGINE_HOST || '127.0.0.1';
  const engineHost = rawHost === 'localhost' ? '127.0.0.1' : rawHost;
  const port = process.env.ENGINE_PORT || '8000';
  return `http://${engineHost}:${port}`;
}

/**
 * @param {number} userId
 * @param {number} tripId
 * @param {{ forceRebuild?: boolean }} [options]
 */
export async function rebuildPreferenceEmbedding(userId, tripId, options = {}) {
  const { forceRebuild = true } = options;
  const base = getEngineBaseUrl();
  await axios.post(
    `${base}/preferences/build`,
    {
      user_id: userId,
      trip_id: tripId,
      force_rebuild: forceRebuild,
    },
    { timeout: 120000 },
  );
}

/**
 * Fire-and-forget: does not throw; logs on failure.
 * @param {number} userId
 * @param {number} tripId
 */
export function schedulePreferenceEmbeddingRebuild(userId, tripId) {
  rebuildPreferenceEmbedding(userId, tripId, { forceRebuild: true }).catch((err) => {
    console.error(
      `[API] Preference embedding rebuild failed for user_id=${userId} trip_id=${tripId}:`,
      err.response?.data ?? err.message,
    );
  });
}
