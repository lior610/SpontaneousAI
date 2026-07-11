/**
 * Unit tests for the engine-attraction -> frontend-activity mapper used by both
 * getNextActivity and the companion-suggestion passthrough.
 *
 * Runs with Node's built-in test runner (no extra dependencies):
 *   node --test api/tests/activityMapper.test.js
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import { mapEngineAttractionToActivity } from '../src/utils/activityMapper.js';

test('maps a full companion suggestion to the activity shape', () => {
  const attr = {
    place_id: 'p-123',
    name: 'The Louvre',
    description: 'World-famous art museum',
    hours: '09:00-18:00',
    budget: '17',
    categories: ['Museum', 'Art'],
    address: 'Rue de Rivoli',
    latitude: 48.8606,
    longitude: 2.3376,
  };

  const activity = mapEngineAttractionToActivity(attr);

  assert.equal(activity.id, 'p-123');
  assert.equal(activity.title, 'The Louvre');
  assert.equal(activity.description, 'World-famous art museum');
  assert.equal(activity.estimatedTime, '09:00-18:00');
  assert.equal(activity.cost, '$17');
  assert.equal(activity.category, 'museum'); // first category, lowercased
  assert.equal(activity.address, 'Rue de Rivoli');
  assert.equal(activity.lat, 48.8606);
  assert.equal(activity.lng, 2.3376);
  assert.equal(activity.completed, false);
});

test('falls back to activity_id, default time, Free cost, and general category', () => {
  const activity = mapEngineAttractionToActivity({
    activity_id: 'a-9',
    name: 'Hidden Park',
    budget: '0',
    categories: [],
  });

  assert.equal(activity.id, 'a-9');
  assert.equal(activity.estimatedTime, '1-2 hours');
  assert.equal(activity.cost, 'Free');
  assert.equal(activity.category, 'general');
});

test('treats missing budget as Free', () => {
  const activity = mapEngineAttractionToActivity({ place_id: 'x', name: 'N' });
  assert.equal(activity.cost, 'Free');
});
