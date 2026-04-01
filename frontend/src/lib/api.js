export const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export function apiUrl(path) {
  if (!path.startsWith('/')) {
    return `${API_BASE}/${path}`;
  }
  return `${API_BASE}${path}`;
}
