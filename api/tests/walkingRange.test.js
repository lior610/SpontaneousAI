/**
 * Unit tests for the "walk a bit further?" radius math.
 *
 *   node --test api/tests/walkingRange.test.js
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import { computeExpandedRange } from '../src/utils/walkingRange.js';

test('adds the step to the current radius', () => {
  const r = computeExpandedRange(2, 1, 20);
  assert.equal(r.next, 3);
  assert.equal(r.changed, true);
  assert.equal(r.atMax, false);
});

test('caps at the maximum and reports no change when already there', () => {
  const atCeiling = computeExpandedRange(20, 1, 20);
  assert.equal(atCeiling.next, 20);
  assert.equal(atCeiling.changed, false);
  assert.equal(atCeiling.atMax, true);

  const overshoot = computeExpandedRange(19.5, 1, 20);
  assert.equal(overshoot.next, 20);
  assert.equal(overshoot.changed, true);
  assert.equal(overshoot.atMax, true);
});

test('supports a custom step (e.g. 0.5 km)', () => {
  const r = computeExpandedRange(0.5, 0.5, 20);
  assert.equal(r.next, 1);
  assert.equal(r.changed, true);
});

test('avoids floating-point drift', () => {
  const r = computeExpandedRange(0.1, 0.2, 20);
  assert.equal(r.next, 0.3);
});

test('falls back to safe defaults for bad input', () => {
  const nullCurrent = computeExpandedRange(null, 1, 20);
  assert.equal(nullCurrent.next, 1); // treats current as 0

  const badStep = computeExpandedRange(2, -5, 20);
  assert.equal(badStep.next, 3); // step falls back to 1

  const badMax = computeExpandedRange(2, 1, NaN);
  assert.equal(badMax.next, 3); // max falls back to 20
});
