import { apiUrl } from './api';

function buildHeaders({ auth = false, headers = {}, hasJsonBody = false }) {
  const nextHeaders = { ...headers };

  if (auth) {
    const token = localStorage.getItem('token');
    if (token) nextHeaders.Authorization = `Bearer ${token}`;
  }

  if (hasJsonBody && !nextHeaders['Content-Type']) {
    nextHeaders['Content-Type'] = 'application/json';
  }

  return nextHeaders;
}

export async function apiFetch(path, { method = 'GET', auth = false, headers = {}, body } = {}) {
  const hasJsonBody = body !== undefined && body !== null && !(body instanceof FormData);
  const payload = hasJsonBody ? JSON.stringify(body) : body;

  return fetch(apiUrl(path), {
    method,
    headers: buildHeaders({ auth, headers, hasJsonBody }),
    body: payload,
  });
}

export async function apiFetchJson(path, options = {}) {
  const res = await apiFetch(path, options);
  const data = await res.json().catch(() => null);

  if (!res.ok) {
    const detail = data?.detail || data?.message || `Request failed (${res.status})`;
    throw new Error(detail);
  }

  return data;
}
