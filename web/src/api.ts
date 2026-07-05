/**
 * The one place that knows how to reach the engine. Browser deployments leave the base URL empty
 * (same-origin, relative paths — unchanged behavior, no CORS involved). The Tauri desktop shell
 * has no same-origin server to talk to, so it persists an absolute base URL here instead (D55).
 */

const STORAGE_KEY = 'apiBaseUrl'

/** The configured base URL, trailing slash(es) stripped. ``''`` means same-origin (default). */
export function getApiBase(): string {
  return (localStorage.getItem(STORAGE_KEY) ?? '').replace(/\/+$/, '')
}

/** Persist the base URL (trailing slash(es) stripped). Pass ``''`` to reset to same-origin. */
export function setApiBase(url: string): void {
  localStorage.setItem(STORAGE_KEY, url.replace(/\/+$/, ''))
}

/** Resolve an absolute-path route against the configured base URL. */
export function apiUrl(path: string): string {
  return getApiBase() + path
}

/**
 * ``fetch`` against the configured base URL, injecting ``Authorization: Bearer <token>`` only
 * when a non-empty token is given (mirrors every hand-rolled call site this replaces).
 */
export function apiFetch(path: string, token: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers)
  if (token !== '') headers.set('Authorization', `Bearer ${token}`)
  return fetch(apiUrl(path), { ...init, headers })
}
