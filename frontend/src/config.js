// API Configuration
// This will be replaced during build time with the actual backend URL
export const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://orchestrator-backend-yo2mex5f2a-ew.a.run.app';

export function formatDateInUserTimezone(isoString, timezone) {
  if (!isoString) return '—';
  const tz = timezone || Intl.DateTimeFormat().resolvedOptions().timeZone;
  return new Intl.DateTimeFormat('en-GB', {
    timeZone: tz,
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(isoString));
}
