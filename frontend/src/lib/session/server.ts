import "server-only";

import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import { cache } from "react";

import { clientAddress, TENANT_SESSION_COOKIE } from "@/lib/api/forwarding";
import type { SessionWire } from "@/lib/api/types";
import { getServerEnv } from "@/lib/env";

import {
  AUTH_ROUTES,
  authUrl,
  CAMPUS_UNAVAILABLE_REASON,
  sessionEndedUrl,
} from "./routes";

// Server session helpers (T01-09A). The real gate of /app/*: every layout
// and page render reads the session from the API (GET /api/v1/session) with
// the request's session cookie — on every navigation, before any protected
// content is rendered (T01-05 UI contract §7, S9). Nothing is trusted from
// the URL, browser storage or client state. React `cache` shares one read per
// server request between the layout, the page and metadata.

export { TENANT_SESSION_COOKIE };

/** The API could not answer the session read (not "signed out"). */
export class SessionReadError extends Error {
  constructor() {
    super("SESSION_READ_FAILED");
    this.name = "SessionReadError";
  }
}

/**
 * The current tenant session, or null when there is none (no cookie, or the
 * API answers 401: expired, revoked, MFA still pending). Throws
 * SessionReadError for any other failure, so error boundaries show the
 * fixed, user-safe error state.
 */
export const readTenantSession = cache(
  async (): Promise<SessionWire | null> => {
    const token = (await cookies()).get(TENANT_SESSION_COOKIE)?.value;
    if (!token) return null;

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

    let response: Response;
    try {
      response = await fetch(`${getServerEnv().apiBaseUrl}/api/v1/session`, {
        headers: forwarded,
        cache: "no-store",
      });
    } catch {
      throw new SessionReadError();
    }
    if (response.status === 401) return null;
    if (!response.ok) throw new SessionReadError();
    return ((await response.json()) as { data: SessionWire }).data;
  },
);

/**
 * Gate for /app/* (§7 step 1): returns a ready session or redirects —
 * no session → /session-ended (J10); no institute → /select-institute;
 * campus choice required → /select-campus. `path` becomes `next`.
 */
export async function requireReadyTenantSession(
  path: string,
): Promise<SessionWire> {
  const session = await readTenantSession();
  if (!session || session.status === "mfa_required") {
    redirect(sessionEndedUrl(path));
  }
  if (!session.active_institute) {
    redirect(authUrl(AUTH_ROUTES.selectInstitute, { next: path }));
  }
  if (session.campus_selection_required) {
    redirect(
      authUrl(AUTH_ROUTES.selectCampus, {
        next: path,
        reason: CAMPUS_UNAVAILABLE_REASON,
      }),
    );
  }
  return session;
}
