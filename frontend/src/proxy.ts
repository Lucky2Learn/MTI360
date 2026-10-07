import { NextResponse, type NextRequest } from "next/server";

import {
  PLATFORM_SESSION_COOKIE,
  TENANT_SESSION_COOKIE,
} from "@/lib/api/forwarding";
import {
  isProtectedPlatformPath,
  platformSessionEndedUrl,
} from "@/lib/session/platform-routes";
import { sessionEndedUrl } from "@/lib/session/routes";

// Next.js Proxy (formerly Middleware; T01-09A, repository-structure.md §2,
// T01-04 UI contract §6.2 row 1; T01-09B UI contract §4):
// - an /app/* request without the TENANT session cookie goes straight to
//   /session-ended?reason=ended&next=<path>;
// - a protected /platform request (the console — not the five platform
//   authentication routes) without the PLATFORM session cookie goes to
//   /platform/session-ended?reason=ended&next=<path>.
// Each realm looks only at its own cookie: a tenant cookie never lets a
// platform page through, and vice versa.
//
// UX only. It checks that the cookie is PRESENT, never what it holds: it
// makes no authorization decision and derives no tenant. With a cookie, the
// server-side page gate (lib/session/server.ts, platform-server.ts) reads
// the session from the API and decides; an expired, revoked or MFA-pending
// cookie still ends there. Security headers and the CSP nonce (security.md
// §6) are not part of this task.

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (pathname === "/platform" || pathname.startsWith("/platform/")) {
    if (
      !isProtectedPlatformPath(pathname) ||
      request.cookies.has(PLATFORM_SESSION_COOKIE)
    ) {
      return NextResponse.next();
    }
    return NextResponse.redirect(
      new URL(platformSessionEndedUrl(pathname), request.url),
    );
  }

  if (request.cookies.has(TENANT_SESSION_COOKIE)) return NextResponse.next();
  return NextResponse.redirect(
    new URL(sessionEndedUrl(request.nextUrl.pathname), request.url),
  );
}

export const config = {
  matcher: ["/app", "/app/:path*", "/platform", "/platform/:path*"],
};
