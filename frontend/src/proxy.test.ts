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

  it("runs only for the tenant application", () => {
    expect(config.matcher).toEqual(["/app", "/app/:path*"]);
  });
});
