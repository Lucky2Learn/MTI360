import { safePathBelow } from "./routes";

// Platform authentication routes, `next` and notice reasons (T01-09B UI
// contract §4). Pure functions, used on the server (entry checks, the proxy,
// page gates) and in the browser. The tenant equivalents live in routes.ts
// and never accept a platform path; these never accept a tenant path.

export const PLATFORM_HOME = "/platform";

export const PLATFORM_AUTH_ROUTES = {
  login: "/platform/login",
  forgotPassword: "/platform/forgot-password",
  resetPassword: "/platform/reset-password",
  acceptInvitation: "/platform/accept-invitation",
  sessionEnded: "/platform/session-ended",
} as const;

export const PLATFORM_PROFILE = "/platform/profile";

/** First segments below /platform that are public authentication routes. */
export const PLATFORM_AUTH_SEGMENTS: ReadonlySet<string> = new Set(
  Object.values(PLATFORM_AUTH_ROUTES).map((route) =>
    route.slice(PLATFORM_HOME.length + 1),
  ),
);

/** A protected platform path (the shell), as opposed to an auth route. */
export function isProtectedPlatformPath(pathname: string): boolean {
  if (pathname === PLATFORM_HOME || pathname === `${PLATFORM_HOME}/`) {
    return true;
  }
  if (!pathname.startsWith(`${PLATFORM_HOME}/`)) return false;
  const first = pathname.slice(PLATFORM_HOME.length + 1).split("/")[0]!;
  return !PLATFORM_AUTH_SEGMENTS.has(first);
}

/**
 * `next` for the platform: only "/platform" or "/platform/<plain segments>",
 * never an authentication route and never anything outside /platform
 * (prevents open redirects and sign-in loops).
 */
export function safePlatformNextPath(value: unknown): string | null {
  return safePathBelow(PLATFORM_HOME, value, PLATFORM_AUTH_SEGMENTS);
}

/** `next` when valid, otherwise the platform home. */
export function resolvePlatformNext(value: unknown): string {
  return safePlatformNextPath(value) ?? PLATFORM_HOME;
}

/** Adds a valid `next` and an optional reason to a platform auth route. */
export function platformAuthUrl(
  route: string,
  params: { next?: unknown; reason?: string } = {},
): string {
  const search = new URLSearchParams();
  if (params.reason) search.set("reason", params.reason);
  const next = safePlatformNextPath(params.next);
  if (next && next !== PLATFORM_HOME) search.set("next", next);
  const query = search.toString();
  return query ? `${route}?${query}` : route;
}

/** Notices on /platform/login: an allow-list, never free text. */
export const PLATFORM_LOGIN_REASONS = [
  "signed-out",
  "password-reset",
  "invitation-accepted",
] as const;
export type PlatformLoginReason = (typeof PLATFORM_LOGIN_REASONS)[number];

export function platformLoginReason(
  value: unknown,
): PlatformLoginReason | null {
  return (PLATFORM_LOGIN_REASONS as readonly unknown[]).includes(value)
    ? (value as PlatformLoginReason)
    : null;
}

/** The session ended while working; come back to `next` after sign-in. */
export function platformSessionEndedUrl(next?: unknown): string {
  return platformAuthUrl(PLATFORM_AUTH_ROUTES.sessionEnded, {
    reason: "ended",
    next,
  });
}

export const PLATFORM_SIGNED_OUT_URL = platformAuthUrl(
  PLATFORM_AUTH_ROUTES.sessionEnded,
  { reason: "signed-out" },
);
