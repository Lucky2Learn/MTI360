import { NextResponse, type NextRequest } from "next/server";

import {
  isSiteHost,
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
//
// Hosted institute pages (Phase 02-4, ADR-0024; repository-structure.md §2,
// INC-27). On a site host `<slug>.<PUBLIC_SITE_DOMAIN>` only the site's pages
// are served: /enquiry is rewritten to the internal route
// /sites/<host>/enquiry, and every other page path (including /, /app,
// /platform and /login) to /sites/<host>/not-found, the branded public 404
// (no staff or platform pages on an institute address). On any other host,
// /enquiry and /sites/* get the same public 404. /api/*, Next.js internals and
// static files are not matched. Routing only: the pages and the API resolve
// the institute from the request's Host, never from this path, and the API
// serves only verified, active addresses (an unknown one gets a neutral 404).

const DEFAULT_SITE_DOMAIN = "mti360.in";
const SITE_PAGES = new Set(["/enquiry"]);
/** Last segment of the public not-found route (app/sites/[site]/[...missing]). */
export const SITE_NOT_FOUND = "not-found";

function siteDomain(): string {
  return process.env.PUBLIC_SITE_DOMAIN?.trim() || DEFAULT_SITE_DOMAIN;
}

function siteSegment(host: string | null): string {
  const name = (host ?? "").toLowerCase().replace(/:[0-9]+$/, "");
  return encodeURIComponent(name || "unknown");
}

function sitePage(request: NextRequest, host: string | null, page: string) {
  return NextResponse.rewrite(
    new URL(`/sites/${siteSegment(host)}/${page}`, request.url),
  );
}

function isUnder(pathname: string, prefix: string): boolean {
  return pathname === prefix || pathname.startsWith(`${prefix}/`);
}

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const host = request.headers.get("host");

  if (host && isSiteHost(host, siteDomain())) {
    return SITE_PAGES.has(pathname)
      ? sitePage(request, host, pathname.slice(1))
      : sitePage(request, host, SITE_NOT_FOUND);
  }
  if (SITE_PAGES.has(pathname) || isUnder(pathname, "/sites")) {
    return sitePage(request, host, SITE_NOT_FOUND);
  }

  if (isUnder(pathname, "/platform")) {
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

  if (isUnder(pathname, "/app")) {
    if (request.cookies.has(TENANT_SESSION_COOKIE)) return NextResponse.next();
    return NextResponse.redirect(
      new URL(sessionEndedUrl(request.nextUrl.pathname), request.url),
    );
  }

  return NextResponse.next();
}

export const config = {
  // Every page path: not /api, Next.js internals (/_next, /__nextjs*) or
  // files with an extension (public assets, favicon).
  matcher: ["/((?!api/|_next/|__nextjs|.*\\.[A-Za-z0-9]+$).*)"],
};
