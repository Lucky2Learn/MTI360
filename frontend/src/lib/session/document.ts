// Document-level navigation and URL access (T01-09A), isolated so tests can
// replace them (jsdom cannot navigate).
//
// Full document navigation is used whenever the session's institute changes
// or ends (sign-in, institute switch, sign-out, session ended): nothing kept
// in memory for the previous institute — session, permissions, CSRF token,
// page data — survives (T01-04 UI contract §6.2, S13; T01-05 S7).

export function assignLocation(url: string): void {
  window.location.assign(url);
}

export function reloadDocument(): void {
  window.location.reload();
}

/** The current /app path (no query or fragment), for `next`. */
export function currentPath(): string {
  return window.location.pathname;
}

/**
 * Reads `token` from the URL fragment (#token=…) and removes the fragment
 * from the address bar at once with history.replaceState (same path, no
 * fragment). The token is never in the query string, so it never reaches the
 * server, the proxy, access logs or Referer (T01-04 UI contract §6.1, S9, S10).
 * Keep the result in memory only.
 */
export function takeFragmentToken(): string | null {
  const { hash, pathname, search } = window.location;
  if (!hash) return null;
  const token = new URLSearchParams(hash.slice(1)).get("token");
  window.history.replaceState(window.history.state, "", pathname + search);
  return token || null;
}
