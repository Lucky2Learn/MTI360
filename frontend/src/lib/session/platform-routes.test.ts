import { describe, expect, it } from "vitest";

import {
  isProtectedPlatformPath,
  platformAuthUrl,
  platformLoginReason,
  platformSessionEndedUrl,
  PLATFORM_AUTH_ROUTES,
  PLATFORM_SIGNED_OUT_URL,
  resolvePlatformNext,
  safePlatformNextPath,
} from "./platform-routes";
import { safeNextPath, sessionEndedReason } from "./routes";

// Platform routes, `next` and reasons (T01-09B UI contract §4).

describe("platform next", () => {
  it.each([
    "/platform",
    "/platform/tenants",
    "/platform/users",
    "/platform/profile",
    "/platform/audit/events",
  ])("accepts %s", (value) => {
    expect(safePlatformNextPath(value)).toBe(value);
  });

  it.each([
    // Other realms and the root.
    "/app",
    "/app/administration",
    "/",
    "/platformx",
    "/platform-admin",
    // Authentication routes are never destinations (no sign-in loops).
    "/platform/login",
    "/platform/login/",
    "/platform/forgot-password",
    "/platform/reset-password",
    "/platform/accept-invitation",
    "/platform/session-ended",
    // Open redirects and traversal.
    "https://evil.example/platform",
    "//evil.example/platform",
    "/platform//evil.example",
    "/platform/%2F%2Fevil.example",
    "/platform/../app",
    "/platform/./tenants",
    "/platform\\evil",
    "/platform/tenants?x=1",
    "/platform/tenants#frag",
    "/platform/javascript:alert(1)",
    `/platform/${"a".repeat(600)}`,
    "",
    null,
    42,
  ])("rejects %s", (value) => {
    expect(safePlatformNextPath(value)).toBeNull();
    expect(resolvePlatformNext(value)).toBe("/platform");
  });

  it("normalises a trailing slash to the platform home", () => {
    expect(safePlatformNextPath("/platform/")).toBe("/platform");
  });

  it("the tenant next never accepts a platform path", () => {
    expect(safeNextPath("/platform")).toBeNull();
    expect(safeNextPath("/platform/tenants")).toBeNull();
  });
});

describe("protected platform paths (proxy)", () => {
  it.each([
    "/platform",
    "/platform/",
    "/platform/tenants",
    "/platform/profile",
  ])("%s is protected", (path) =>
    expect(isProtectedPlatformPath(path)).toBe(true),
  );

  it.each([...Object.values(PLATFORM_AUTH_ROUTES), "/app", "/platformx"])(
    "%s is not protected",
    (path) => {
      expect(isProtectedPlatformPath(path)).toBe(false);
    },
  );
});

describe("platform URLs and reasons", () => {
  it("builds auth URLs with a valid next only", () => {
    expect(
      platformAuthUrl(PLATFORM_AUTH_ROUTES.login, {
        reason: "password-reset",
        next: "/platform/users",
      }),
    ).toBe("/platform/login?reason=password-reset&next=%2Fplatform%2Fusers");
    expect(
      platformAuthUrl(PLATFORM_AUTH_ROUTES.login, { next: "/app/finance" }),
    ).toBe("/platform/login");
    expect(platformSessionEndedUrl("/platform/tenants")).toBe(
      "/platform/session-ended?reason=ended&next=%2Fplatform%2Ftenants",
    );
    expect(PLATFORM_SIGNED_OUT_URL).toBe(
      "/platform/session-ended?reason=signed-out",
    );
  });

  it("allow-lists login reasons and never echoes free text", () => {
    expect(platformLoginReason("signed-out")).toBe("signed-out");
    expect(platformLoginReason("password-reset")).toBe("password-reset");
    expect(platformLoginReason("invitation-accepted")).toBe(
      "invitation-accepted",
    );
    expect(platformLoginReason("<script>")).toBeNull();
    expect(platformLoginReason("mfa-ended")).toBeNull();
    expect(sessionEndedReason("anything")).toBe("ended");
  });
});
