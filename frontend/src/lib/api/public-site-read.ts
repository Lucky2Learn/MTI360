import "server-only";

import { headers } from "next/headers";

import { getServerEnv } from "@/lib/env";

import { clientAddress, publicHost } from "./forwarding";

// Server-side reads of the public realm for hosted institute pages (Phase
// 02-4, ADR-0024). No cookie is ever sent. The API resolves the institute
// from X-Forwarded-Host, which is rebuilt here from this request's Host
// (never a client-supplied X-Forwarded-Host), and serves only verified,
// active addresses; anything else is a 404.

export type PublicReadResult<T> =
  | { kind: "ok"; data: T }
  | { kind: "not-found" }
  | { kind: "error"; reference: string | null };

/** GET `/api/v1/public{path}` for the institute at this request's host. */
export async function publicSiteRead<T>(
  path: `/${string}`,
): Promise<PublicReadResult<T>> {
  const apiPath = `/api/v1/public${path}`;
  const incoming = await headers();
  const host = publicHost(incoming.get("host"), apiPath);
  if (!host) return { kind: "not-found" };
  const env = getServerEnv();
  const forwarded: Record<string, string> = {
    accept: "application/json",
    "x-forwarded-host": host,
  };
  const userAgent = incoming.get("user-agent");
  if (userAgent) forwarded["user-agent"] = userAgent;
  const address = clientAddress(
    incoming.get("x-forwarded-for"),
    env.trustedProxyHops,
  );
  if (address) forwarded["x-forwarded-for"] = address;

  let response: Response;
  try {
    response = await fetch(`${env.apiBaseUrl}${apiPath}`, {
      headers: forwarded,
      cache: "no-store",
    });
  } catch {
    return { kind: "error", reference: null };
  }
  if (response.status === 404) return { kind: "not-found" };
  if (!response.ok) {
    return { kind: "error", reference: response.headers.get("x-request-id") };
  }
  try {
    const body = (await response.json()) as { data: T };
    return { kind: "ok", data: body.data };
  } catch {
    return { kind: "error", reference: response.headers.get("x-request-id") };
  }
}
