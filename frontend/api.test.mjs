import test from 'node:test';
import assert from 'node:assert/strict';
import { api, describeApiError } from './src/api.js';

test('describes backend error envelopes without hiding their messages', () => {
  assert.equal(
    describeApiError({ status: 503, body: { error: { code: 'AGENT_NOT_CONFIGURED', message: 'Agent runtime is not configured.' } } }),
    'Agent runtime is not configured.'
  );
});

test('explains network failures without implying a request succeeded', () => {
  assert.equal(
    describeApiError({ status: 0, body: null }),
    'Could not reach the server. Check your connection and try again.'
  );
});

test('confirmation API posts the proposal id and explicit decision', async () => {
  const previousFetch = global.fetch;
  let observed;
  global.fetch = async (url, options) => {
    observed = { url, options };
    return new Response(JSON.stringify({ proposal_id: 'proposal-1', status: 'cancelled' }), {
      status: 200,
      headers: { 'content-type': 'application/json' }
    });
  };
  try {
    const result = await api.confirmProposal('token-1', 'proposal-1', false);
    assert.equal(observed.url, '/agent/confirm');
    assert.equal(observed.options.headers.get('Authorization'), 'Bearer token-1');
    assert.deepEqual(JSON.parse(observed.options.body), { proposal_id: 'proposal-1', approve: false });
    assert.equal(result.status, 'cancelled');
  } finally {
    global.fetch = previousFetch;
  }
});
