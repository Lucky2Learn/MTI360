import "server-only";

import { cookies, headers } from "next/headers";

import { getServerEnv } from "@/lib/env";

import { clientAddress, TENANT_SESSION_COOKIE } from "./forwarding";

// Server-side tenant API reads for pages (Phase 02-1; generalises the
// T01-09A session read). Pages read their data on the server with the
// request's tenant session cookie ONLY (never the platform cookie or any
// other cookie of the origin), the browser's user agent and its address
// per TRUSTED_PROXY_HOPS. Nothing is cached, logged or stored; query strings
// may carry a search term (blueprint §23) and are never logged here.

/** Headers forwarded to the API for a tenant read with `token`. */
export async function tenantForwardHeaders(
  token: string,
): Promise<Record<string, string>> {
  const incoming = await headers();
  const forwarded: Record<string, string> = {
    accept: "application/json",
    cookie: `${TENANT_SESSION_COOKIE}=${token}`,
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

/** GET `/api/v1{path}` for the current tenant session. */
export async function tenantApiRead<T>(
  path: `/${string}`,
): Promise<ReadResult<T>> {
  const token = (await cookies()).get(TENANT_SESSION_COOKIE)?.value;
  if (!token) return { kind: "unauthenticated" };
  let response: Response;
  try {
    response = await fetch(`${getServerEnv().apiBaseUrl}/api/v1${path}`, {
      headers: await tenantForwardHeaders(token),
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
