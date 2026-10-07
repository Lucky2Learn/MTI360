// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  pendingPlatformSession,
  platformSession,
} from "@/test/platform-fixtures";

// The server-side gate of the platform console (T01-09B UI contract §4, §8):
// the session comes only from GET /api/v1/platform/session, read with ONLY
// the platform cookie. No cookie, 401, a pending session or a tenant cookie
// alone never reach the shell.

const request = vi.hoisted(() => ({
  cookies: new Map<string, string>(),
  headers: new Headers(),
}));

vi.mock("server-only", () => ({}));
vi.mock("next/headers", () => ({
  cookies: () =>
    Promise.resolve({
      get: (name: string) =>
        request.cookies.has(name)
          ? { name, value: request.cookies.get(name)! }
          : undefined,
    }),
  headers: () => Promise.resolve(request.headers),
}));
vi.mock("next/navigation", () => ({
  redirect: (url: string) => {
    throw new Error(`NEXT_REDIRECT ${url}`);
  },
}));
vi.mock("@/lib/env", () => ({
  getServerEnv: () => ({
    appEnv: "test",
    apiBaseUrl: "http://api.internal:8000",
    trustedProxyHops: 1,
  }),
}));

const { readPlatformSession, requirePlatformSession, SessionReadError } =
  await import("./platform-server");

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  request.cookies.clear();
  request.headers = new Headers();
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

const respond = (status: number, body: unknown = {}) =>
  fetchMock.mockResolvedValueOnce(
    new Response(JSON.stringify(body), { status }),
  );

describe("readPlatformSession", () => {
  it("returns null without calling the API when there is no platform cookie", async () => {
    await expect(readPlatformSession()).resolves.toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("a tenant cookie alone never authenticates the platform", async () => {
    request.cookies.set("__Host-mti360_tsid", "tenant-session");
    await expect(readPlatformSession()).resolves.toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("reads GET /api/v1/platform/session with only the platform cookie", async () => {
    request.cookies.set("__Host-mti360_psid", "opaque-platform");
    request.cookies.set("__Host-mti360_tsid", "tenant-session");
    request.headers = new Headers({
      "user-agent": "Chromium test",
      "x-forwarded-for": "6.6.6.6, 203.0.113.9",
      authorization: "Bearer forged",
    });
    const session = platformSession();
    respond(200, { data: session, meta: {} });

    await expect(readPlatformSession()).resolves.toEqual(session);
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("http://api.internal:8000/api/v1/platform/session");
    expect(init?.cache).toBe("no-store");
    expect(init?.headers).toEqual({
      accept: "application/json",
      cookie: "__Host-mti360_psid=opaque-platform",
      "user-agent": "Chromium test",
      "x-forwarded-for": "203.0.113.9",
    });
  });

  it("treats 401 (invalid, expired, revoked or MFA-pending) as no session", async () => {
    request.cookies.set("__Host-mti360_psid", "stale");
    respond(401, { error: { code: "AUTHENTICATION_REQUIRED" } });
    await expect(readPlatformSession()).resolves.toBeNull();
  });

  it("never treats a pending session as signed in (defence in depth)", async () => {
    request.cookies.set("__Host-mti360_psid", "pending");
    respond(200, { data: pendingPlatformSession("mfa_required") });
    await expect(readPlatformSession()).resolves.toBeNull();
  });

  it("throws SessionReadError for other failures", async () => {
    request.cookies.set("__Host-mti360_psid", "x");
    respond(500);
    await expect(readPlatformSession()).rejects.toBeInstanceOf(
      SessionReadError,
    );
    fetchMock.mockRejectedValueOnce(new TypeError("fetch failed"));
    await expect(readPlatformSession()).rejects.toBeInstanceOf(
      SessionReadError,
    );
  });
});

describe("requirePlatformSession", () => {
  it("redirects without a session to /platform/session-ended with next", async () => {
    await expect(requirePlatformSession("/platform/users")).rejects.toThrow(
      "NEXT_REDIRECT /platform/session-ended?reason=ended&next=%2Fplatform%2Fusers",
    );
  });

  it("redirects a pending session (401) the same way", async () => {
    request.cookies.set("__Host-mti360_psid", "pending");
    respond(401);
    await expect(requirePlatformSession("/platform")).rejects.toThrow(
      "NEXT_REDIRECT /platform/session-ended?reason=ended",
    );
  });

  it("returns a full session", async () => {
    request.cookies.set("__Host-mti360_psid", "valid");
    const session = platformSession();
    respond(200, { data: session });
    await expect(requirePlatformSession("/platform")).resolves.toEqual(session);
  });
});
