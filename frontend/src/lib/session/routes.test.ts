import { describe, expect, it } from "vitest";

import {
  authUrl,
  destinationFor,
  loginReason,
  resolveNext,
  safeNextPath,
  sessionEndedReason,
  sessionEndedUrl,
} from "./routes";

// `next` and `reason` (T01-04 UI contract §6.1): only /app paths, no open
// redirects; notices are an allow-list, never free text.

describe("safeNextPath", () => {
  it.each([
    "/app",
    "/app/",
    "/app/administration/campuses",
    "/app/ai/sql-data-agent",
    "/app/finance/fee-structure/",
  ])("accepts %s", (value) => {
    expect(safeNextPath(value)).not.toBeNull();
  });

  it.each([
    // absolute and protocol-relative URLs
    "https://evil.example/app",
    "http://localhost:3100/app",
    "//evil.example/app",
    "///evil.example",
    "javascript:alert(1)",
    "app",
    // backslashes and their encoded forms
    "/app\\..\\..\\evil",
    "\\\\evil.example",
    "/app/%5C%5Cevil.example",
    // encoded slashes and dots, double encoding
    "/app/%2F%2Fevil.example",
    "/app%2F..%2Fevil",
    "/app/%2e%2e/login",
    "/app/%252e%252e/login",
    // dot segments and double slashes inside /app
    "/app/../login",
    "/app/./x",
    "/app//evil.example",
    // other paths, look-alikes, queries and fragments
    "/login",
    "/application",
    "/appx",
    "/platform",
    "/app?next=https://evil.example",
    "/app#token=abc",
    "/app/ space",
    // types and length
    "",
    "x".repeat(600),
  ])("rejects %s", (value) => {
    expect(safeNextPath(value)).toBeNull();
  });

  it("rejects non-strings", () => {
    expect(safeNextPath(undefined)).toBeNull();
    expect(safeNextPath(null)).toBeNull();
    expect(safeNextPath(["/app"])).toBeNull();
    expect(safeNextPath({ toString: () => "/app" })).toBeNull();
  });

  it("falls back to /app silently", () => {
    expect(resolveNext("https://evil.example")).toBe("/app");
    expect(resolveNext("/app/administration/users")).toBe(
      "/app/administration/users",
    );
  });
});

describe("auth URLs", () => {
  it("carries only a valid next", () => {
    expect(authUrl("/login", { next: "/app/administration/roles" })).toBe(
      "/login?next=%2Fapp%2Fadministration%2Froles",
    );
    expect(authUrl("/login", { next: "//evil.example" })).toBe("/login");
    expect(authUrl("/login", { next: "/app" })).toBe("/login");
  });

  it("builds the J10 session-ended URL", () => {
    expect(sessionEndedUrl("/app/administration/campuses")).toBe(
      "/session-ended?reason=ended&next=%2Fapp%2Fadministration%2Fcampuses",
    );
    expect(sessionEndedUrl("https://evil.example")).toBe(
      "/session-ended?reason=ended",
    );
  });

  it("routes each session status to its step, carrying next", () => {
    const next = "/app/administration/users";
    expect(destinationFor("ready", next)).toBe(next);
    expect(destinationFor("ready", "//evil")).toBe("/app");
    expect(destinationFor("institute_selection_required", next)).toBe(
      "/select-institute?next=%2Fapp%2Fadministration%2Fusers",
    );
    expect(destinationFor("campus_selection_required", next)).toBe(
      "/select-campus?next=%2Fapp%2Fadministration%2Fusers",
    );
    expect(destinationFor("mfa_required", next)).toBe(
      "/login?next=%2Fapp%2Fadministration%2Fusers",
    );
    expect(destinationFor(null, null)).toBe("/login");
  });
});

describe("reasons", () => {
  it("accepts only the allow-listed notices", () => {
    expect(loginReason("signed-out")).toBe("signed-out");
    expect(loginReason("password-reset")).toBe("password-reset");
    expect(loginReason("invitation-accepted")).toBe("invitation-accepted");
    expect(loginReason("<b>hacked</b>")).toBeNull();
    expect(loginReason("ended")).toBeNull();
    expect(sessionEndedReason("signed-out")).toBe("signed-out");
    expect(sessionEndedReason("anything")).toBe("ended");
    expect(sessionEndedReason(null)).toBe("ended");
  });
});
