import "server-only";

import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import { cache } from "react";

import { clientAddress, PLATFORM_SESSION_COOKIE } from "@/lib/api/forwarding";
import type { PlatformSessionWire } from "@/lib/api/types";
import { getServerEnv } from "@/lib/env";

import { platformSessionEndedUrl } from "./platform-routes";
import { SessionReadError } from "./server";

// Server platform session helpers (T01-09B UI contract §4, §8). The real
// gate of the platform shell: every layout and page render reads
// GET /api/v1/platform/session with ONLY the platform session cookie — never
// the tenant cookie (realm separation, ADR-0005). Nothing is trusted from the
// URL, browser storage or client state. An MFA-pending session answers 401
// there, so it never reaches the shell (D9B-2).

export { PLATFORM_SESSION_COOKIE, SessionReadError };

/**
 * The current full platform session, or null when there is none (no cookie,
 * or 401: expired, revoked, suspended, MFA still pending). Throws
 * SessionReadError for any other failure.
 */
export const readPlatformSession = cache(
  async (): Promise<PlatformSessionWire | null> => {
    const token = (await cookies()).get(PLATFORM_SESSION_COOKIE)?.value;
    if (!token) return null;

    const incoming = await headers();
    const forwarded: Record<string, string> = {
      accept: "application/json",
      cookie: `${PLATFORM_SESSION_COOKIE}=${token}`,
    };
    const userAgent = incoming.get("user-agent");
    if (userAgent) forwarded["user-agent"] = userAgent;
    const address = clientAddress(
      incoming.get("x-forwarded-for"),
      getServerEnv().trustedProxyHops,
    );
    if (address) forwarded["x-forwarded-for"] = address;

    let response: Response;
    try {
      response = await fetch(
        `${getServerEnv().apiBaseUrl}/api/v1/platform/session`,
        { headers: forwarded, cache: "no-store" },
      );
    } catch {
      throw new SessionReadError();
    }
    if (response.status === 401) return null;
    if (!response.ok) throw new SessionReadError();
    const session = ((await response.json()) as { data: PlatformSessionWire })
      .data;
    // Defence in depth: only a full session counts as signed in.
    return session.status === "authenticated" && session.user ? session : null;
  },
);

/**
 * Gate for the platform shell: a full session, or a redirect to the platform
 * session-ended page with `path` as `next`.
 */
export async function requirePlatformSession(
  path: string,
): Promise<PlatformSessionWire> {
  const session = await readPlatformSession();
  if (!session) redirect(platformSessionEndedUrl(path));
  return session;
}
