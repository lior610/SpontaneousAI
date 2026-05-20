/**
 * Food Intercept Service
 *
 * Decides if the user should get a food break suggestion instead of a regular attraction.
 * Uses a hybrid approach: cheap deterministic gate conditions run first (2-of-3 must pass),
 * then Gemini validates the decision. This avoids LLM calls on every request.
 *
 * Flow: cooldown check → gate conditions → LLM yes/no → fetch food batch → serve card
 * Any failure at any step silently falls through to normal recommendations.
 */
import { GoogleGenerativeAI } from '@google/generative-ai';
import axios from 'axios';
import * as usersDb from '../db/usersConnection.js';

const FOOD_COOLDOWN_MS = parseInt(process.env.FOOD_COOLDOWN_MS, 10) || 3600000;
const ACTIVITY_THRESHOLD = parseInt(process.env.FOOD_GATE_ACTIVITY_THRESHOLD, 10) || 2;
const HOURS_THRESHOLD = parseFloat(process.env.FOOD_GATE_HOURS_THRESHOLD) || 3.5;
const FOOD_INTERCEPT_ENABLED = process.env.FOOD_INTERCEPT_ENABLED !== 'false';

// Singleton Gemini client — avoids re-instantiating on every LLM call
const genAI = process.env.GEMINI_API_KEY ? new GoogleGenerativeAI(process.env.GEMINI_API_KEY) : null;
const geminiModel = genAI?.getGenerativeModel({ model: 'gemini-2.5-flash' });

// In-memory state: cooldowns after dismiss, and cached food batches per trip
const foodDismissalCooldowns = new Map();
const foodBatchCache = new Map();

// Periodic cleanup so these maps don't grow unbounded
setInterval(() => {
  const now = Date.now();
  for (const [tripId, entry] of foodDismissalCooldowns) {
    if (now - entry.dismissedAt > FOOD_COOLDOWN_MS * 2) {
      foodDismissalCooldowns.delete(tripId);
    }
  }
  for (const [tripId, entry] of foodBatchCache) {
    if (now - entry.storedAt > FOOD_COOLDOWN_MS * 2) {
      foodBatchCache.delete(tripId);
    }
  }
}, FOOD_COOLDOWN_MS).unref();

// Shapes an engine attraction into the card format the frontend expects
function buildFoodCard(foodPlace, position) {
  return {
    activity: {
      id: foodPlace.place_id || foodPlace.activity_id || 'food-1',
      title: foodPlace.name,
      description: foodPlace.description || 'Time for a food break! Here\'s a nearby spot.',
      image: '',
      rating: null,
      reviewCount: null,
      estimatedTime: '45 min - 1 hour',
      cost: foodPlace.budget ? `$${foodPlace.budget}` : '$$',
      category: 'food',
      address: foodPlace.address,
      lat: foodPlace.latitude,
      lng: foodPlace.longitude,
      completed: false
    },
    card_type: 'food_intercept',
    intercept_metadata: {
      reason: 'meal_time_suggestion',
      dismissable: true,
      cooldown_minutes: Math.round(FOOD_COOLDOWN_MS / 60000)
    },
    userLocation: position ? { lat: position.lat, lng: position.lng } : null
  };
}

export function dismissFoodSuggestion(tripId) {
  foodDismissalCooldowns.set(tripId, { dismissedAt: Date.now() });
  foodBatchCache.delete(tripId);
}

export function getNextFoodSuggestion(tripId, position) {
  const foodPlace = getNextFoodFromBatch(tripId);
  if (!foodPlace || !foodPlace.name) return null;
  return buildFoodCard(foodPlace, position);
}

// Fetches a fresh batch from the engine and returns the first result
export async function refillAndGetFood(tripId, trip, position) {
  if (!position) return null;
  const batch = await fetchFoodBatch(trip, position);
  if (batch.length === 0) return null;
  foodBatchCache.set(tripId, { results: batch, currentIndex: 1, storedAt: Date.now() });
  return buildFoodCard(batch[0], position);
}

function isInCooldown(tripId) {
  const entry = foodDismissalCooldowns.get(tripId);
  if (!entry) return false;
  return (Date.now() - entry.dismissedAt) < FOOD_COOLDOWN_MS;
}

function getLocalTime(trip) {
  const tz = trip.timezone || 'UTC';
  const now = new Date();
  const localStr = now.toLocaleString('en-US', { timeZone: tz, hour12: false });
  const timePart = localStr.split(', ')[1];
  const [hour, minute] = timePart.split(':').map(Number);
  return { hour, minute, localStr: timePart };
}

/**
 * Gate conditions — 2 of 3 must be true to proceed to LLM validation:
 *   1. Current time is in a meal window (11:30-14:00 or 17:30-20:30)
 *   2. User has done N+ activities since their last food
 *   3. It's been N+ hours since their last food
 */
function evaluateGateConditions(localHour, localMinute, todayActivities, lastFoodActivity) {
  const timeDecimal = localHour + localMinute / 60;
  const inMealWindow = (timeDecimal >= 11.5 && timeDecimal <= 14.0) ||
                       (timeDecimal >= 17.5 && timeDecimal <= 20.5);

  let activitiesSinceFood;
  if (lastFoodActivity) {
    const lastFoodTime = new Date(lastFoodActivity.completed_at).getTime();
    activitiesSinceFood = todayActivities.filter(
      a => new Date(a.completed_at).getTime() > lastFoodTime
    ).length;
  } else {
    activitiesSinceFood = todayActivities.length;
  }
  const activityCountMet = activitiesSinceFood >= ACTIVITY_THRESHOLD;

  const referenceTime = lastFoodActivity
    ? new Date(lastFoodActivity.completed_at).getTime()
    : (todayActivities.length > 0
        ? new Date(todayActivities[0].completed_at).getTime()
        : Date.now());
  const hoursSinceFood = (Date.now() - referenceTime) / (1000 * 60 * 60);
  const timeSinceFoodMet = hoursSinceFood >= HOURS_THRESHOLD;

  const conditionsMet = [inMealWindow, activityCountMet, timeSinceFoodMet].filter(Boolean).length;
  console.log(`[FoodIntercept] Gate check: mealWindow=${inMealWindow} (${timeDecimal.toFixed(2)}), activityCount=${activityCountMet} (${activitiesSinceFood}/${ACTIVITY_THRESHOLD}), timeSinceFood=${timeSinceFoodMet} (${hoursSinceFood.toFixed(2)}h/${HOURS_THRESHOLD}h) → ${conditionsMet}/3 conditions met`);
  return conditionsMet >= 2;
}

// Asks Gemini for a yes/no on whether a food break makes sense right now.
// Returns false on any error so we gracefully skip the intercept.
async function callLlmValidation(localTimeStr, todayActivities, lastFoodActivity) {
  if (!geminiModel) return false;

  const activitiesList = todayActivities
    .map(a => `- ${a.title} (${a.category}) at ${new Date(a.completed_at).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })}`)
    .join('\n');

  const lastFoodStr = lastFoodActivity
    ? `${lastFoodActivity.title} at ${new Date(lastFoodActivity.completed_at).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })}`
    : 'None today';

  const prompt = `You are a trip assistant. Decide if suggesting a food break is appropriate. Respond ONLY "yes" or "no".

Current local time: ${localTimeStr}

Today's activities (chronological):
${activitiesList || '(none yet)'}

Last food activity: ${lastFoodStr}

Given what this user has done today, is it appropriate to suggest a food break now?`;

  try {
    console.log('[FoodIntercept] LLM prompt:', prompt);
    const result = await geminiModel.generateContent(prompt);
    const answer = result.response.text().trim().toLowerCase();
    console.log('[FoodIntercept] LLM response:', answer);
    return answer.startsWith('yes');
  } catch (err) {
    console.error('[FoodIntercept] LLM validation failed:', err.message);
    return false;
  }
}

// Calls the engine recommendation pipeline restricted to food. Caller caches the results.
async function fetchFoodBatch(trip, position) {
  const rawHost = process.env.ENGINE_HOST || '127.0.0.1';
  const engineHost = rawHost === 'localhost' ? '127.0.0.1' : rawHost;

  const res = await axios.post(`http://${engineHost}:8000/recommendations/`, {
    user_id: trip.user_id,
    trip_id: trip.trip_id,
    current_location: { lat: position.lat, lng: position.lng },
    current_time: new Date().toISOString(),
    category_filter: 'food'
  });

  if (!res.data || res.data.length === 0) return [];
  return res.data.map(r => r.attraction).filter(a => a && a.name);
}

function getNextFoodFromBatch(tripId) {
  const cached = foodBatchCache.get(tripId);
  if (!cached || cached.currentIndex >= cached.results.length) return null;
  const food = cached.results[cached.currentIndex];
  cached.currentIndex++;
  return food;
}

// Main entry point — called on every getNextActivity request (unless specific_need is set).
// Returns { triggered: false } to fall through to normal flow, or { triggered: true, foodCard }
export async function checkFoodIntercept(tripId, trip, position) {
  if (!FOOD_INTERCEPT_ENABLED) return { triggered: false };
  if (!position) return { triggered: false };
  if (isInCooldown(tripId)) return { triggered: false };

  try {
    const { hour, minute, localStr } = getLocalTime(trip);

    // Get today's completed activities to evaluate gate conditions
    const todayResult = await usersDb.query(
      `SELECT title, category, completed_at
       FROM trip_activity_logs
       WHERE trip_id = $1 AND completed_at::date = (NOW() AT TIME ZONE COALESCE($2, 'UTC'))::date
       ORDER BY completed_at ASC`,
      [tripId, trip.timezone || 'UTC']
    );
    const todayActivities = todayResult.rows;
    const lastFoodActivity = [...todayActivities].reverse().find(a => a.category === 'food');

    if (!evaluateGateConditions(hour, minute, todayActivities, lastFoodActivity)) {
      return { triggered: false };
    }

    const llmApproved = await callLlmValidation(localStr, todayActivities, lastFoodActivity);
    if (!llmApproved) {
      console.log('[FoodIntercept] LLM declined food suggestion, continuing normal flow');
      return { triggered: false };
    }

    console.log('[FoodIntercept] LLM approved, fetching food batch from engine...');
    const batch = await fetchFoodBatch(trip, position);
    if (batch.length === 0) {
      console.log('[FoodIntercept] No food places found, continuing normal flow');
      return { triggered: false };
    }
    console.log(`[FoodIntercept] Got ${batch.length} food suggestions, serving first`);
    foodBatchCache.set(tripId, { results: batch, currentIndex: 1, storedAt: Date.now() });

    return { triggered: true, foodCard: buildFoodCard(batch[0], position) };
  } catch (err) {
    console.error(`[FoodIntercept] Error for tripId=${tripId}:`, err);
    return { triggered: false };
  }
}
