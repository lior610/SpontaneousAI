// Pure helper for the "walk a bit further?" flow — computes the next radius from the
// current one, a step, and a ceiling. Side-effect free so it's unit-testable without a
// DB (the controller handles persistence + cache invalidation).
/**
 * @param {number} current - current max walking distance (km); non-finite treated as 0.
 * @param {number} step - km to add; non-positive/non-finite falls back to 1.
 * @param {number} max - hard ceiling (km); non-finite falls back to 20.
 * @returns {{ next: number, changed: boolean, atMax: boolean }}
 */
export function computeExpandedRange(current, step, max) {
  const safeCurrent = Number.isFinite(current) && current > 0 ? current : 0;
  const safeStep = Number.isFinite(step) && step > 0 ? step : 1;
  const safeMax = Number.isFinite(max) && max > 0 ? max : 20;

  const raw = Number((safeCurrent + safeStep).toFixed(2));
  const next = Math.min(raw, safeMax);
  return {
    next,
    changed: next > safeCurrent,
    atMax: next >= safeMax,
  };
}
