import "server-only";

import { notFound, redirect } from "next/navigation";

import type { ReadResult } from "@/lib/api/server-read";
import type { SessionWire } from "@/lib/api/types";
import { can } from "@/lib/authz/requirements";

import { sessionEndedUrl } from "./routes";
import { requireReadyTenantSession } from "./server";

// Page gate for explicit business routes (Phase 02-1; T01-05 UI contract §7),
// the same order as the navigation-derived pages: (1) a ready tenant session
// or a redirect (session ended / select institute / select campus); (2) the
// page's permission — missing → AUTHZ-01 at the same URL; (3) the page reads
// its data, and the API authorizes every read again.

export type PageAccess = { session: SessionWire; allowed: boolean };

export async function tenantPageAccess(
  path: string,
  permission: string,
): Promise<PageAccess> {
  const session = await requireReadyTenantSession(path);
  return { session, allowed: can(session.permissions, permission) };
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** A route ID that cannot be a record ID is simply not found (RESOURCE-02). */
export function requireRecordId(value: string): string {
  if (!UUID.test(value)) notFound();
  return value.toLowerCase();
}

/**
 * The data of a successful read, or the page state for the others:
 * not found → RESOURCE-02 (notFound()); no session → session ended. `denied`
 * and `error` are returned for the page to render (AUTHZ-01 / ErrorState).
 */
export function settle<T>(
  result: ReadResult<T>,
  path: string,
): Exclude<ReadResult<T>, { kind: "not-found" } | { kind: "unauthenticated" }> {
  if (result.kind === "not-found") notFound();
  if (result.kind === "unauthenticated") redirect(sessionEndedUrl(path));
  return result;
}
