import type { SessionStatus } from "@/lib/api/types";

// Authentication routes, the `next` parameter and notice reasons (T01-04 UI
// contract §6). Pure functions, used on the server (entry checks, layouts)
// and in the browser (after sign-in, 401 handling).

export const APP_HOME = "/app";

export const AUTH_ROUTES = {
  login: "/login",
  forgotPassword: "/forgot-password",
  resetPassword: "/reset-password",
  acceptInvitation: "/accept-invitation",
  selectInstitute: "/select-institute",
  selectCampus: "/select-campus",
  sessionEnded: "/session-ended",
} as const;

const MAX_NEXT_LENGTH = 512;
// Unreserved characters only: no scheme (":"), no "%" (so no encoded "/",
// "\" or "."), no query, fragment, "//" or backslash can get through.
const SEGMENT = /^[A-Za-z0-9\-._~]+$/;

/**
 * `next` is accepted only as "/app" or "/app/…" built from plain path
 * segments; anything else (absolute URLs, "//host", backslashes, encoded
 * forms, dot segments, other paths) is ignored. Prevents open redirects (§6.1).
 */
export function safeNextPath(value: unknown): string | null {
  if (typeof value !== "string" || value.length > MAX_NEXT_LENGTH) return null;
  if (value === APP_HOME) return value;
  if (!value.startsWith(`${APP_HOME}/`)) return null;
  const segments = value.slice(APP_HOME.length + 1).split("/");
  // A trailing slash leaves one empty segment, which is allowed.
  if (segments.at(-1) === "") segments.pop();
  if (segments.length === 0) return APP_HOME;
  const valid = segments.every(
    (segment) => SEGMENT.test(segment) && segment !== "." && segment !== "..",
  );
  return valid ? value : null;
}

/** `next` when valid, otherwise the application home. */
export function resolveNext(value: unknown): string {
  return safeNextPath(value) ?? APP_HOME;
}

/** Adds a valid `next` (and optional extra parameters) to an auth route. */
export function authUrl(
  route: string,
  params: { next?: unknown; reason?: string } = {},
): string {
  const search = new URLSearchParams();
  if (params.reason) search.set("reason", params.reason);
  const next = safeNextPath(params.next);
  if (next && next !== APP_HOME) search.set("next", next);
  const query = search.toString();
  return query ? `${route}?${query}` : route;
}

/** Notices on /login and /session-ended: an allow-list, never free text. */
export const LOGIN_REASONS = [
  "signed-out",
  "password-reset",
  "invitation-accepted",
] as const;
export type LoginReason = (typeof LOGIN_REASONS)[number];

export const SESSION_ENDED_REASONS = ["signed-out", "ended"] as const;
export type SessionEndedReason = (typeof SESSION_ENDED_REASONS)[number];

/** /select-campus notice when the active campus was withdrawn (§8.6). */
export const CAMPUS_UNAVAILABLE_REASON = "campus-unavailable";

export function loginReason(value: unknown): LoginReason | null {
  return (LOGIN_REASONS as readonly unknown[]).includes(value)
    ? (value as LoginReason)
    : null;
}

export function sessionEndedReason(value: unknown): SessionEndedReason {
  return value === "signed-out" ? "signed-out" : "ended";
}

/** First query value of a Next.js searchParams entry. */
export function firstParam(
  value: string | string[] | undefined,
): string | null {
  if (Array.isArray(value)) return value[0] ?? null;
  return value ?? null;
}

/**
 * Where a session in `status` goes next (§6.2): the shell, or the institute
 * or campus step with `next` carried. `mfa_required` and no session both mean
 * "not signed in" for routing.
 */
export function destinationFor(
  status: SessionStatus | null,
  next: unknown,
): string {
  switch (status) {
    case "ready":
      return resolveNext(next);
    case "institute_selection_required":
      return authUrl(AUTH_ROUTES.selectInstitute, { next });
    case "campus_selection_required":
      return authUrl(AUTH_ROUTES.selectCampus, { next });
    default:
      return authUrl(AUTH_ROUTES.login, { next });
  }
}

/** J10: the session ended while working; come back to `next` after sign-in. */
export function sessionEndedUrl(next?: unknown): string {
  return authUrl(AUTH_ROUTES.sessionEnded, { reason: "ended", next });
}
