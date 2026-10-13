/** Pure validation and rate-limit rules shared by the backend and its unit tests. */
export const WINDOW_MS = 10 * 60 * 1000;
export const MAX_ATTEMPTS_PER_IP = 8;
export const COOLDOWN_MS = 15 * 60 * 1000;
export const MAX_PASSWORD_LENGTH = 512;

export function validatePassphrase(value) {
  return typeof value === 'string' && value.length >= 16 && value.length <= MAX_PASSWORD_LENGTH;
}

export function nextAttempt(previous, now) {
  if (!previous || !Number.isFinite(previous.start) || !Number.isFinite(previous.count) ||
      now - previous.start >= WINDOW_MS || now < previous.start) {
    return {start: now, count: 1, allowed: true, retryAfter: 0};
  }
  const count = previous.count + 1;
  return {
    start: previous.start,
    count,
    allowed: count <= MAX_ATTEMPTS_PER_IP,
    retryAfter: count <= MAX_ATTEMPTS_PER_IP ? 0 : Math.max(1, Math.ceil((WINDOW_MS - (now - previous.start)) / 1000)),
  };
}

export function cooldownStatus(last, now) {
  const remaining = last ? (last + COOLDOWN_MS - now) : 0;
  return {allowed: remaining <= 0, retryAfter: Math.max(0, Math.ceil(remaining / 1000))};
}

export function validateApiUrl(raw) {
  if (typeof raw !== 'string' || !raw || raw.length > 512) return null;
  try {
    const url = new URL(raw);
    if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash ||
        (url.pathname !== '/' && url.pathname !== '') || !url.hostname) return null;
    return url.origin;
  } catch { return null; }
}

export function sanitizedGithubError(status) {
  if (status === 401 || status === 403) return 'GitHub rejected the backend token. Check the token permissions and expiry.';
  if (status === 404) return 'The GitHub workflow or repository was not found. Check repository and workflow settings.';
  if (status === 422) return 'GitHub rejected the workflow request. Check the branch and workflow_dispatch settings.';
  if (status === 429) return 'GitHub API is rate limiting the backend. Try again later.';
  return 'GitHub did not accept the refresh request. Check backend logs and the GitHub Actions configuration.';
}
