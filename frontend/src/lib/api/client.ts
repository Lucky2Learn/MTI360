import {
  ApiError,
  apiErrorFrom,
  NetworkError,
  UPSTREAM_UNAVAILABLE,
} from "./errors";

// Browser API client (T01-09A). Every call goes to the same-origin proxy
// (/api/v1/*, app/api/[...path]/route.ts), never to the API host directly.
// The session cookie is HttpOnly and travels with the request automatically;
// the browser never reads it. Unsafe methods carry the CSRF token from the
// in-memory session (X-CSRF-Token, ADR-0010 §5). Nothing is cached, logged or
// stored: request bodies of /auth/* and /session/* contain secrets.
//
// This is the transport only. The T01-05 error matrix (401 re-read,
// SESSION_REFRESH_REQUIRED, PERMISSION_DENIED) is applied by the tenant
// session provider (lib/session/SessionProvider.tsx), which wraps it.

export const API_PREFIX = "/api/v1";

export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export const SAFE_METHODS: ReadonlySet<HttpMethod> = new Set(["GET"]);

export type ApiRequestOptions = {
  method?: HttpMethod;
  /**
   * JSON body (unsafe methods only), or FormData for a file upload (Phase
   * 02-2): the browser then sets the multipart Content-Type with its boundary.
   */
  body?: unknown;
  /** Sent as X-CSRF-Token on unsafe methods when present. */
  csrfToken?: string | null;
  signal?: AbortSignal;
};

/**
 * Calls `/api/v1{path}` and returns the envelope's `data` (undefined for 204).
 * Throws ApiError for error responses and NetworkError when there is no
 * usable response.
 */
export async function apiRequest<T>(
  path: `/${string}`,
  { method = "GET", body, csrfToken, signal }: ApiRequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  const isForm = typeof FormData !== "undefined" && body instanceof FormData;
  if (body !== undefined && !isForm)
    headers["Content-Type"] = "application/json";
  if (!SAFE_METHODS.has(method) && csrfToken) {
    headers["X-CSRF-Token"] = csrfToken;
  }

  let response: Response;
  try {
    response = await fetch(`${API_PREFIX}${path}`, {
      method,
      headers,
      body:
        body === undefined ? undefined : isForm ? body : JSON.stringify(body),
      credentials: "same-origin",
      cache: "no-store",
      signal,
    });
  } catch {
    throw new NetworkError();
  }

  if (!response.ok) {
    const error = await apiErrorFrom(response);
    if (error.code === UPSTREAM_UNAVAILABLE) throw new NetworkError();
    throw error;
  }
  if (response.status === 204) return undefined as T;
  // 202 Accepted (password reset) has no envelope: an empty or `null` body.
  const text = await response.text().catch(() => "");
  if (!text) return undefined as T;
  try {
    const payload = JSON.parse(text) as { data: T } | null;
    return (payload?.data ?? undefined) as T;
  } catch {
    throw new ApiError({ status: response.status, code: "INVALID_RESPONSE" });
  }
}
