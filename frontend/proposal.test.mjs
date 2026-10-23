import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeProposalStatus } from './src/proposals.js';

test('proposal confirmation preserves only a status returned by the server', () => {
  assert.equal(normalizeProposalStatus({ status: 'approved' }), 'approved');
  assert.equal(normalizeProposalStatus({ status: 'cancelled' }), 'cancelled');
});

test('proposal confirmation without a server status stays non-final', () => {
  assert.equal(normalizeProposalStatus({ proposal_id: 'p-1' }), 'decision_submitted');
  assert.equal(normalizeProposalStatus({ status: 'unexpected' }), 'decision_submitted');
});
