/**
 * Recommended-stay service.
 *
 * Answers "how long should a typical visitor stay at this attraction?" using Google
 * Gemini. Results are cached per attraction so the LLM is asked at most once per place:
 *   1. In-memory cache (fast path within a process)
 *   2. attractions.recommended_stay_minutes column (persists across restarts)
 *   3. Gemini call (only on a full cache miss), then written back to both caches.
 */

import axios from 'axios';
import { pool as attractionsPool } from '../db/attractionsConnection.js';

const GEMINI_MODEL = process.env.GEMINI_MODEL || 'gemini-2.5-flash';
const GEMINI_API_KEY = process.env.GEMINI_API_KEY;

// place_id -> minutes (number) | null. null = looked up but unusable, don't retry this process.
const memoryCache = new Map();

function clampMinutes(value) {
  const n = Math.round(Number(value));
  if (!Number.isFinite(n) || n <= 0) return null;
  // Keep within a sane range (5 min .. 8 hours) to guard against bad LLM output.
  return Math.min(Math.max(n, 5), 480);
}

function buildPrompt({ name, category, description, address }) {
  const facts = [
    name && `Name: ${name}`,
    category && `Category: ${category}`,
    address && `Location: ${address}`,
    description && `Description: ${description}`,
  ]
    .filter(Boolean)
    .join('\n');

  return `You estimate how long a typical visitor spends at a place of interest.\n\n${facts}\n\nReturn ONLY the typical visit duration in whole minutes as a single integer (no words, no units, no range). For example: 90`;
}

function parseMinutesFromText(text) {
  if (!text) return null;
  const match = String(text).match(/\d+/);
  return match ? clampMinutes(match[0]) : null;
}

async function askGemini(attraction) {
  if (!GEMINI_API_KEY) {
    console.warn('[recommendedStay] GEMINI_API_KEY not set; skipping LLM lookup');
    return null;
  }
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent?key=${GEMINI_API_KEY}`;
  try {
    const res = await axios.post(
      url,
      {
        contents: [{ parts: [{ text: buildPrompt(attraction) }] }],
        // thinkingBudget: 0 disables "thinking" on Gemini 2.5 models so the small output
        // budget isn't consumed by hidden reasoning tokens (which would yield empty text).
        generationConfig: { temperature: 0, maxOutputTokens: 256, thinkingConfig: { thinkingBudget: 0 } },
      },
      { timeout: 8000, headers: { 'Content-Type': 'application/json' } }
    );
    const text = res.data?.candidates?.[0]?.content?.parts?.[0]?.text;
    return parseMinutesFromText(text);
  } catch (err) {
    console.error('[recommendedStay] Gemini request failed:', err.response?.data?.error?.message || err.message);
    return null;
  }
}

/**
 * @param {{ placeId?: string, name?: string, category?: string, description?: string, address?: string }} attraction
 * @returns {Promise<number|null>} recommended stay in minutes, or null if unavailable
 */
export async function getRecommendedStayMinutes(attraction) {
  const { placeId } = attraction;

  if (placeId && memoryCache.has(placeId)) {
    return memoryCache.get(placeId);
  }

  // DB cache lookup (and a way to read attraction details if not supplied).
  let dbAttraction = null;
  if (placeId) {
    try {
      const result = await attractionsPool.query(
        'SELECT name, categories, description, address, recommended_stay_minutes FROM attractions WHERE place_id = $1',
        [placeId]
      );
      dbAttraction = result.rows[0] || null;
      if (dbAttraction?.recommended_stay_minutes != null) {
        const cached = clampMinutes(dbAttraction.recommended_stay_minutes);
        memoryCache.set(placeId, cached);
        return cached;
      }
    } catch (err) {
      console.error('[recommendedStay] DB cache lookup failed:', err.message);
    }
  }

  const minutes = await askGemini({
    name: attraction.name || dbAttraction?.name,
    category:
      attraction.category ||
      (Array.isArray(dbAttraction?.categories) ? dbAttraction.categories[0] : undefined),
    description: attraction.description || dbAttraction?.description,
    address: attraction.address || dbAttraction?.address,
  });

  if (placeId) {
    memoryCache.set(placeId, minutes);
    if (minutes != null) {
      try {
        await attractionsPool.query(
          'UPDATE attractions SET recommended_stay_minutes = $1 WHERE place_id = $2',
          [minutes, placeId]
        );
      } catch (err) {
        console.error('[recommendedStay] Failed to persist recommended stay:', err.message);
      }
    }
  }

  return minutes;
}
