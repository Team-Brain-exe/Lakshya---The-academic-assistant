const SERVER_PROPOSAL_STATUSES = new Set([
  'pending_confirmation', 'pending', 'processing', 'approved', 'cancelled', 'failed'
]);

export function normalizeProposalStatus(response) {
  const status = response && typeof response.status === 'string' ? response.status : '';
  return SERVER_PROPOSAL_STATUSES.has(status) ? status : 'decision_submitted';
}

export function proposalStatusLabel(status) {
  if (status === 'decision_submitted') return 'Decision submitted; server status not provided';
  return String(status || '').replaceAll('_', ' ');
}
