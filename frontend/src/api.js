const API_BASE = (import.meta.env?.VITE_API_BASE_URL || '').replace(/\/$/, '');

export function describeApiError({ status = 0, body = null } = {}) {
  if (body?.error?.message) return body.error.message;
  if (status === 0) return 'Could not reach the server. Check your connection and try again.';
  if (status === 401) return 'Your session has expired. Please sign in again.';
  if (status === 403) return 'You do not have permission to view this information.';
  return `The request failed (HTTP ${status}). Please try again.`;
}

export class ApiError extends Error {
  constructor(message, status = 0, code = 'NETWORK_ERROR', details = undefined) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function request(path, { token, method = 'GET', body, formData, headers = {} } = {}) {
  const requestHeaders = new Headers(headers);
  if (token) requestHeaders.set('Authorization', `Bearer ${token}`);
  if (body !== undefined) requestHeaders.set('Content-Type', 'application/json');
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers: requestHeaders,
      body: formData ?? (body === undefined ? undefined : JSON.stringify(body))
    });
  } catch {
    throw new ApiError(describeApiError({ status: 0 }), 0);
  }
  const contentType = response.headers.get('content-type') || '';
  const data = contentType.includes('application/json') ? await response.json().catch(() => null) : null;
  if (!response.ok) {
    const error = data?.error;
    throw new ApiError(describeApiError({ status: response.status, body: data }), response.status, error?.code, error?.details);
  }
  return data;
}

export const api = {
  login: (credentials) => request('/auth/login', { method: 'POST', body: credentials }),
  me: (token) => request('/auth/me', { token }),
  subjects: (token) => request('/subjects', { token }),
  subject: (token, id) => request(`/subjects/${encodeURIComponent(id)}`, { token }),
  questions: (token, moduleId, filters = {}) => {
    const query = new URLSearchParams({ module_id: moduleId });
    for (const [key, value] of Object.entries(filters)) if (value) query.set(key, value);
    return request(`/questions?${query}`, { token });
  },
  questionAction: (token, id, action) => request(`/questions/${encodeURIComponent(id)}/${action}`, { token, method: 'POST' }),
  updateQuestion: (token, id, fields) => request(`/questions/${encodeURIComponent(id)}`, { token, method: 'PATCH', body: fields }),
  chat: (token, message, conversationId) => request('/agent/chat', { token, method: 'POST', body: { message, ...(conversationId ? { conversation_id: conversationId } : {}) } }),
  confirmProposal: (token, proposalId, approve) => request('/agent/confirm', { token, method: 'POST', body: { proposal_id: proposalId, approve } }),
  studyPlan: (token, subjectId) => request(`/students/me/study-plan?subject_id=${encodeURIComponent(subjectId)}`, { token }),
  buildStudyPlan: (token, subjectId) => request('/students/me/study-plan', { token, method: 'POST', body: { subject_id: subjectId } }),
  progress: (token, subjectId) => request(`/students/me/progress?subject_id=${encodeURIComponent(subjectId)}`, { token }),
  flashcards: (token, moduleId) => request(`/modules/${encodeURIComponent(moduleId)}/flashcards`, { token }),
  askCourse: (token, subjectId, question) => request('/qa', { token, method: 'POST', body: { subject_id: subjectId, question } }),
  retrieve: (token, subjectId, query) => request(`/retrieve?subject_id=${encodeURIComponent(subjectId)}&q=${encodeURIComponent(query)}`, { token }),
  events: (token, subjectId, from, to) => request(`/events?subject_id=${encodeURIComponent(subjectId)}&from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`, { token }),
  createEvent: (token, event) => request('/events', { token, method: 'POST', body: event }),
  updateEvent: (token, id, fields) => request(`/events/${encodeURIComponent(id)}`, { token, method: 'PATCH', body: fields }),
  deleteEvent: (token, id) => request(`/events/${encodeURIComponent(id)}`, { token, method: 'DELETE' }),
  usage: (token, from, to) => request(`/usage/summary?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`, { token })
};
