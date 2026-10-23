import test from 'node:test';
import assert from 'node:assert/strict';
import { advanceCalendarPeriod } from './src/calendar.js';

test('month navigation advances from the first day into the next month', () => {
  const next = advanceCalendarPeriod(new Date(2026, 0, 1, 12), 'month', 1);
  assert.equal(next.getFullYear(), 2026);
  assert.equal(next.getMonth(), 1);
  assert.equal(next.getDate(), 1);
});

test('month navigation clamps end-of-month dates instead of overflowing', () => {
  const next = advanceCalendarPeriod(new Date(2026, 0, 31, 12), 'month', 1);
  assert.equal(next.getMonth(), 1);
  assert.equal(next.getDate(), 28);
});

test('week navigation moves by exactly seven days', () => {
  const next = advanceCalendarPeriod(new Date(2026, 1, 1, 12), 'week', -1);
  assert.equal(next.getMonth(), 0);
  assert.equal(next.getDate(), 25);
});
