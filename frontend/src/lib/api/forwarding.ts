// Request metadata the Next.js server forwards to the API (T01-09A).
// Shared by the same-origin proxy and the server-side session read.

/** The tenant session cookie (HttpOnly; never read by browser code). */
export const TENANT_SESSION_COOKIE = "__Host-mti360_tsid";

/** Session cookies the API reads (ADR-0010 §4). No other cookie is forwarded. */
export const API_SESSION_COOKIES = [
  TENANT_SESSION_COOKIE,
  "__Host-mti360_psid",
] as const;

/**
 * The Cookie header reduced to the session cookies, or null. Other cookies
 * of the application origin never reach the API.
 */
export function apiCookieHeader(cookieHeader: string | null): string | null {
  if (!cookieHeader) return null;
  const allowed = new Set<string>(API_SESSION_COOKIES);
  const kept = cookieHeader
    .split(";")
    .map((pair) => pair.trim())
    .filter((pair) => {
      const separator = pair.indexOf("=");
      return separator > 0 && allowed.has(pair.slice(0, separator));
    });
  return kept.length > 0 ? kept.join("; ") : null;
}

const IP_LIKE = /^[0-9A-Fa-f:.]{2,45}$/;

/**
 * The browser's address, from the incoming X-Forwarded-For, trusting exactly
 * `trustedProxyHops` proxies in front of this Next.js server (frontend
 * TRUSTED_PROXY_HOPS, the counterpart of the API's D08 setting).
 *
 * Every trusted proxy appends the address it received the request from, so
 * the client is the `trustedProxyHops`-th entry from the right; entries to its
 * left were written by the client and are ignored. With 0 or 1 that is the
 * right-most entry: the socket peer that Next.js records when the request has
 * no X-Forwarded-For, or the address one ingress appended. ARCHITECTURE.md
 * places Cloudflare and a reverse proxy in front of the frontend, which is 2.
 * With 0 and the server reachable directly, a client-supplied header cannot
 * be told apart (Next.js keeps it), so deployments set the real hop count.
 * Returns null when nothing usable is present (fewer entries than hops).
 */
export function clientAddress(
  forwardedFor: string | null,
  trustedProxyHops = 0,
): string | null {
  if (!forwardedFor) return null;
  const entries = forwardedFor
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean);
  const candidate = entries[entries.length - Math.max(1, trustedProxyHops)];
  return candidate && IP_LIKE.test(candidate) ? candidate : null;
}
