import { NextResponse, type NextRequest } from "next/server";

import { TENANT_SESSION_COOKIE } from "@/lib/api/forwarding";
import { sessionEndedUrl } from "@/lib/session/routes";

// Next.js Proxy (formerly Middleware; T01-09A, repository-structure.md §2,
// T01-04 UI contract §6.2 row 1): an /app/* request without the tenant
// session cookie goes straight to /session-ended?reason=ended&next=<path>.
//
// UX only. It checks that the cookie is PRESENT, never what it holds: it
// makes no authorization decision and derives no tenant. With a cookie, the
// server-side page gate (lib/session/server.ts) reads the session from the
// API and decides; an expired or revoked cookie still ends there.
// Security headers and the CSP nonce (security.md §6) are not part of this
// task.

export function proxy(request: NextRequest) {
  if (request.cookies.has(TENANT_SESSION_COOKIE)) return NextResponse.next();
  return NextResponse.redirect(
    new URL(sessionEndedUrl(request.nextUrl.pathname), request.url),
  );
}

export const config = {
  matcher: ["/app", "/app/:path*"],
};
