import { apiRequest, type ApiRequestOptions } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { PlatformSessionWire } from "@/lib/api/types";

import { assignLocation } from "./document";
import { PLATFORM_SIGNED_OUT_URL } from "./platform-routes";
import { toPlatformSession, type PlatformSession } from "./platform-session";

// Browser-side platform session calls (T01-09B). Thin wrappers over the API
// client: every path is under /api/v1/platform, so the proxy forwards only
// the platform cookie (D9B-10). No caching, storage or logging of bodies.

export const PLATFORM_API = "/platform";

/** POST /platform/auth/<path> (anonymous or MFA-pending; see the contract). */
export function platformAuthPost<T>(
  path: `/${string}`,
  body?: unknown,
  options: Omit<ApiRequestOptions, "method" | "body"> = {},
): Promise<T> {
  return apiRequest<T>(`${PLATFORM_API}/auth${path}`, {
    ...options,
    method: "POST",
    body,
  });
}

/**
 * GET /platform/session → the full session, or null when there is none
 * (401, or a response that is not a full session).
 */
export async function readPlatformSessionClient(): Promise<PlatformSession | null> {
  try {
    return toPlatformSession(
      await apiRequest<PlatformSessionWire>(`${PLATFORM_API}/session`),
    );
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
}

/**
 * Platform sign-out: POST /platform/auth/logout, then a full document
 * navigation whatever the response (idempotent). Only the platform cookie is
 * sent and cleared; the tenant session is never touched.
 */
export async function signOutPlatform(
  destination = PLATFORM_SIGNED_OUT_URL,
): Promise<void> {
  try {
    await platformAuthPost("/logout");
  } catch {
    // Ignored on purpose: the session is unusable either way.
  }
  assignLocation(destination);
}
