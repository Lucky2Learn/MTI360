// @vitest-environment node
import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";

import { config, proxy } from "./proxy";

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

  it("runs only for the tenant application and the platform", () => {
    expect(config.matcher).toEqual([
      "/app",
      "/app/:path*",
      "/platform",
      "/platform/:path*",
    ]);
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
