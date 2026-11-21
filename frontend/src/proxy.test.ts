// @vitest-environment node
import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";

import { config, proxy, SITE_NOT_FOUND } from "./proxy";

// src/proxy.ts (T01-09A; T01-04 UI contract §6.2 row 1): cookie presence
// only — UX routing, never authorization.

const request = (path: string, cookie?: string) =>
  new NextRequest(`http://localhost:3100${path}`, {
    headers: cookie ? { cookie } : {},
  });

describe("proxy", () => {
  it("sends /app/* without a session cookie to /session-ended with next", () => {
    const response = proxy(request("/app/administration/users"));
    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe(
      "http://localhost:3100/session-ended?reason=ended&next=%2Fapp%2Fadministration%2Fusers",
    );
  });

  it("never carries an unsafe path as next", () => {
    const response = proxy(request("/app/%2F%2Fevil.example"));
    expect(response.headers.get("location")).toBe(
      "http://localhost:3100/session-ended?reason=ended",
    );
  });

  it("lets a request with the cookie through to the server-side gate, unchanged", () => {
    const response = proxy(
      request("/app", "theme=dark; __Host-mti360_tsid=opaque-value"),
    );
    expect(response.headers.get("x-middleware-next")).toBe("1");
    expect(response.headers.get("location")).toBeNull();
  });

  it("ignores look-alike cookies", () => {
    const response = proxy(
      request("/app", "mti360_tsid=x; __Host-mti360_psid=y"),
    );
    expect(response.status).toBe(307);
  });

  it("runs for every page path, never for the API, Next.js internals or files", () => {
    expect(config.matcher).toHaveLength(1);
    const pattern = new RegExp(`^${config.matcher[0]}$`);
    for (const path of [
      "/",
      "/app",
      "/app/admissions/leads",
      "/platform/tenants",
      "/enquiry",
      "/sites/x/y",
      "/login",
    ]) {
      expect(pattern.test(path), path).toBe(true);
    }
    for (const path of [
      "/api/v1/public/enquiries",
      "/_next/static/chunks/a.js",
      "/__nextjs_original-stack-frame",
      "/favicon.ico",
      "/fonts/inter.woff2",
    ]) {
      expect(pattern.test(path), path).toBe(false);
    }
  });

  it("lets other application pages through untouched", () => {
    for (const path of ["/", "/login", "/design-system"]) {
      const response = proxy(request(path));
      expect(response.headers.get("x-middleware-next")).toBe("1");
      expect(response.headers.get("x-middleware-rewrite")).toBeNull();
    }
  });

  it("never lets a platform cookie through to /app", () => {
    const response = proxy(request("/app", "__Host-mti360_psid=platform"));
    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe(
      "http://localhost:3100/session-ended?reason=ended",
    );
  });
});

describe("proxy — platform (T01-09B)", () => {
  it("sends a protected platform path without the platform cookie to the platform session-ended page", () => {
    const response = proxy(request("/platform/profile"));
    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe(
      "http://localhost:3100/platform/session-ended?reason=ended&next=%2Fplatform%2Fprofile",
    );
    const home = proxy(request("/platform"));
    expect(home.headers.get("location")).toBe(
      "http://localhost:3100/platform/session-ended?reason=ended",
    );
  });

  it("never lets a tenant cookie authenticate a platform path", () => {
    const response = proxy(
      request("/platform/tenants", "__Host-mti360_tsid=tenant-session"),
    );
    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toContain(
      "/platform/session-ended",
    );
  });

  it("lets the platform cookie through to the server-side gate", () => {
    const response = proxy(
      request("/platform/users", "__Host-mti360_psid=opaque-value"),
    );
    expect(response.headers.get("x-middleware-next")).toBe("1");
  });

  it.each([
    "/platform/login",
    "/platform/forgot-password",
    "/platform/reset-password",
    "/platform/accept-invitation",
    "/platform/session-ended",
  ])("keeps %s public (no redirect loop)", (path) => {
    const response = proxy(request(path));
    expect(response.headers.get("x-middleware-next")).toBe("1");
    expect(response.headers.get("location")).toBeNull();
  });

  it("does not treat a look-alike segment as an authentication route", () => {
    const response = proxy(request("/platform/login-history"));
    expect(response.status).toBe(307);
  });
});

// Hosted institute pages (Phase 02-4, ADR-0024): routing by Host only.
describe("proxy: hosted institute pages", () => {
  const site = (path: string, host: string, cookie?: string) =>
    new NextRequest(`http://${host}${path}`, {
      headers: cookie ? { host, cookie } : { host },
    });
  const rewrite = (path: string, host: string, cookie?: string) =>
    proxy(site(path, host, cookie)).headers.get("x-middleware-rewrite");

  it("rewrites /enquiry on an institute address to the internal site route", () => {
    expect(rewrite("/enquiry", "Konkan.mti360.in")).toBe(
      "http://konkan.mti360.in/sites/konkan.mti360.in/enquiry",
    );
  });

  it("ignores the port of the address", () => {
    expect(rewrite("/enquiry", "konkan.mti360.in:8443")).toContain(
      "/sites/konkan.mti360.in/enquiry",
    );
  });

  it.each([
    "/",
    "/about",
    "/app",
    "/app/admissions/leads",
    "/platform",
    "/login",
    "/sites/x/enquiry",
  ])("serves the branded public 404 for %s on an institute address", (path) => {
    expect(rewrite(path, "konkan.mti360.in", "__Host-mti360_tsid=x")).toBe(
      `http://konkan.mti360.in/sites/konkan.mti360.in/${SITE_NOT_FOUND}`,
    );
  });

  it("never redirects to a staff sign-in page on an institute address", () => {
    const response = proxy(site("/app", "konkan.mti360.in"));
    expect(response.status).not.toBe(307);
    expect(response.headers.get("location")).toBeNull();
  });

  it.each([
    "mti360.in",
    "localhost:3100",
    "app.example.com",
    "a.b.mti360.in",
    "konkan.mti360.in.evil.example",
  ])("answers /enquiry on %s with the public 404", (host) => {
    const name = host.replace(/:[0-9]+$/, "");
    expect(rewrite("/enquiry", host)).toBe(
      `http://${host}/sites/${name}/${SITE_NOT_FOUND}`,
    );
  });

  it("never serves the internal route directly", () => {
    for (const path of ["/sites", "/sites/konkan.mti360.in/enquiry"]) {
      expect(rewrite(path, "localhost:3100")).toBe(
        `http://localhost:3100/sites/localhost/${SITE_NOT_FOUND}`,
      );
    }
  });

  it("keeps /app and /platform behaviour on the application host", () => {
    expect(proxy(site("/app", "localhost:3100")).status).toBe(307);
    expect(
      proxy(site("/platform/tenants", "localhost:3100")).headers.get(
        "location",
      ),
    ).toContain("/platform/session-ended");
  });
});
