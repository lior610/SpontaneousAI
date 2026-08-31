/**
 * Unit tests for reducing max_travel_time_min on "Too far".
 *
 *   node --test api/tests/travelTime.test.js
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import { computeReducedTravelTime } from '../src/utils/travelTime.js';

test('subtracts the step from the current travel time', () => {
  const r = computeReducedTravelTime(30, 10);
  assert.equal(r.next, 20);
  assert.equal(r.changed, true);
  assert.equal(r.atFloor, false);
});

test('floors at 0 and reports no change when already there', () => {
  const atFloor = computeReducedTravelTime(0, 10);
  assert.equal(atFloor.next, 0);
  assert.equal(atFloor.changed, false);
  assert.equal(atFloor.atFloor, true);

  const overshoot = computeReducedTravelTime(5, 10);
  assert.equal(overshoot.next, 0);
  assert.equal(overshoot.changed, true);
  assert.equal(overshoot.atFloor, true);
});

test('falls back to safe defaults for bad input', () => {
  const nullCurrent = computeReducedTravelTime(null, 10);
  assert.equal(nullCurrent.next, 0);

  const badStep = computeReducedTravelTime(30, -5);
  assert.equal(badStep.next, 20); // step falls back to 10
});
