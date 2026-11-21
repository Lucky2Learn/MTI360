import "server-only";

import { notFound, redirect } from "next/navigation";

import type { ReadResult } from "@/lib/api/server-read";
import type { PlatformSessionWire } from "@/lib/api/types";
import { can } from "@/lib/authz/requirements";

import { platformSessionEndedUrl } from "./platform-routes";
import { requirePlatformSession } from "./platform-server";

// Page gate for explicit platform routes (Platform Tenants), the same order as
// the navigation-derived platform pages (T01-09B UI contract §8): (1) a full
// platform session or a redirect to the platform session-ended page; (2) the
// page's permission — missing → access denied at the same URL, never a
// role-name check; (3) the page reads its data, and the platform API
// authorizes every read again.

export type PlatformPageAccess = {
  session: PlatformSessionWire;
  allowed: boolean;
};

export async function platformPageAccess(
  path: string,
  permission: string,
): Promise<PlatformPageAccess> {
  const session = await requirePlatformSession(path);
  return { session, allowed: can(session.permissions, permission) };
}

/**
 * The data of a successful platform read, or the page state for the others:
 * not found → notFound(); no session → platform session ended. `denied` and
 * `error` are returned for the page to render.
 */
export function settlePlatform<T>(
  result: ReadResult<T>,
  path: string,
): Exclude<ReadResult<T>, { kind: "not-found" } | { kind: "unauthenticated" }> {
  if (result.kind === "not-found") notFound();
  if (result.kind === "unauthenticated")
    redirect(platformSessionEndedUrl(path));
  return result;
}
