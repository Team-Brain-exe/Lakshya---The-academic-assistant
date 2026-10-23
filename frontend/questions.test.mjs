import test from 'node:test';
import assert from 'node:assert/strict';
import { questionMatchesCourseOutcome } from './src/questions.js';

test('matches a question without co_number using its loaded CO record', () => {
  const question = { id: 'q-1', co_id: 'co-2' };
  const outcomes = [{ id: 'co-2', number: 2 }];

  assert.equal(questionMatchesCourseOutcome(question, '2', outcomes), true);
  assert.equal(questionMatchesCourseOutcome(question, '3', outcomes), false);
});
