// Pure helper for the "Too far" transit flow — subtracts a step from
// max_travel_time_min, floored at 0. Side-effect free so it's unit-testable.
/**
 * @param {number} current - current max travel time (minutes); non-finite treated as 0.
 * @param {number} step - minutes to subtract; non-positive/non-finite falls back to 10.
 * @returns {{ next: number, changed: boolean, atFloor: boolean }}
 */
export function computeReducedTravelTime(current, step) {
  const safeCurrent = Number.isFinite(current) && current > 0 ? current : 0;
  const safeStep = Number.isFinite(step) && step > 0 ? step : 10;
  const next = Math.max(0, safeCurrent - safeStep);
  return {
    next,
    changed: next < safeCurrent,
    atFloor: next <= 0,
  };
}
