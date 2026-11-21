import "server-only";

import { cookies, headers } from "next/headers";

import { getServerEnv } from "@/lib/env";

import {
  type ApiSessionCookie,
  clientAddress,
  PLATFORM_SESSION_COOKIE,
  TENANT_SESSION_COOKIE,
} from "./forwarding";

// Server-side API reads for pages (Phase 02-1; generalises the T01-09A
// session read). A tenant page reads with the request's tenant session
// cookie ONLY, a platform page (Platform Tenants) with the platform session
// cookie ONLY — never the other realm's cookie or any other cookie of the
// origin — plus the browser's user agent and its address per
// TRUSTED_PROXY_HOPS. Nothing is cached, logged or stored; query strings may
// carry a search term (blueprint §23) and are never logged here.

async function forwardHeaders(
  cookie: ApiSessionCookie,
  token: string,
): Promise<Record<string, string>> {
  const incoming = await headers();
  const forwarded: Record<string, string> = {
    accept: "application/json",
    cookie: `${cookie}=${token}`,
  };
  const userAgent = incoming.get("user-agent");
  if (userAgent) forwarded["user-agent"] = userAgent;
  const address = clientAddress(
    incoming.get("x-forwarded-for"),
    getServerEnv().trustedProxyHops,
  );
  if (address) forwarded["x-forwarded-for"] = address;
  return forwarded;
}

/** Headers forwarded to the API for a tenant read with `token`. */
export function tenantForwardHeaders(
  token: string,
): Promise<Record<string, string>> {
  return forwardHeaders(TENANT_SESSION_COOKIE, token);
}

export type PageMeta = { limit: number; offset: number; total: number };

/**
 * The outcome of a page read. Pages map it to their states: `not-found` →
 * RESOURCE-02 (another tenant's or campus's item is indistinguishable),
 * `denied` → AUTHZ-01, `unauthenticated` → session ended, `error` →
 * ErrorState with the support reference (never the server message).
 */
export type ReadResult<T> =
  | { kind: "ok"; data: T; page: PageMeta | null }
  | { kind: "not-found" }
  | { kind: "denied" }
  | { kind: "unauthenticated" }
  | { kind: "error"; reference: string | null };

async function apiRead<T>(
  cookie: ApiSessionCookie,
  url: string,
): Promise<ReadResult<T>> {
  const token = (await cookies()).get(cookie)?.value;
  if (!token) return { kind: "unauthenticated" };
  let response: Response;
  try {
    response = await fetch(url, {
      headers: await forwardHeaders(cookie, token),
      cache: "no-store",
    });
  } catch {
    return { kind: "error", reference: null };
  }
  if (response.status === 401) return { kind: "unauthenticated" };
  if (response.status === 404) return { kind: "not-found" };
  if (response.status === 403) return { kind: "denied" };
  if (!response.ok) {
    return { kind: "error", reference: response.headers.get("x-request-id") };
  }
  try {
    const body = (await response.json()) as {
      data: T;
      meta?: { page?: PageMeta };
    };
    return { kind: "ok", data: body.data, page: body.meta?.page ?? null };
  } catch {
    return { kind: "error", reference: response.headers.get("x-request-id") };
  }
}

/** GET `/api/v1{path}` for the current tenant session. */
export function tenantApiRead<T>(path: `/${string}`): Promise<ReadResult<T>> {
  return apiRead<T>(
    TENANT_SESSION_COOKIE,
    `${getServerEnv().apiBaseUrl}/api/v1${path}`,
  );
}

/** GET `/api/v1/platform{path}` for the current platform session. */
export function platformApiRead<T>(path: `/${string}`): Promise<ReadResult<T>> {
  return apiRead<T>(
    PLATFORM_SESSION_COOKIE,
    `${getServerEnv().apiBaseUrl}/api/v1/platform${path}`,
  );
}
