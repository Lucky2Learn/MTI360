import { apiRequest, type ApiRequestOptions } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { SessionWire } from "@/lib/api/types";

import { assignLocation } from "./document";
import { toSession, type Session } from "./session";

// Browser-side session calls shared by the authentication screens and the
// tenant shell (T01-09A). Thin wrappers over the API client: no caching, no
// storage, no logging of bodies.

/** GET /session → the session, or null when there is none (401). */
export async function readSession(): Promise<Session | null> {
  try {
    return toSession(await apiRequest<SessionWire>("/session"));
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
}

/** POST /auth/<path> (anonymous, same-origin checked by the API). */
export function authPost<T>(
  path: `/${string}`,
  body?: unknown,
  options: Omit<ApiRequestOptions, "method" | "body"> = {},
): Promise<T> {
  return apiRequest<T>(`/auth${path}`, { ...options, method: "POST", body });
}

/**
 * PUT /session/tenant or /session/campus with the session's CSRF token.
 * The API decides whether the selection is allowed (404 otherwise); the
 * value sent is a selector, never authority (S1).
 */
export async function selectInSession(
  target: "tenant" | "campus",
  body: { tenant_id: string } | { campus_id: string | null },
  csrfToken: string,
): Promise<Session> {
  return toSession(
    await apiRequest<SessionWire>(`/session/${target}`, {
      method: "PUT",
      body,
      csrfToken,
    }),
  );
}

/**
 * Sign out (J9): POST /auth/logout, then a full document navigation to
 * `destination` whatever the response — logout is idempotent, and the
 * navigation drops every in-memory value (session, permissions, institute,
 * campus, CSRF token).
 */
export async function signOut(
  destination = "/session-ended?reason=signed-out",
): Promise<void> {
  try {
    await authPost("/logout");
  } catch {
    // Ignored on purpose: the session is unusable either way.
  }
  assignLocation(destination);
}
