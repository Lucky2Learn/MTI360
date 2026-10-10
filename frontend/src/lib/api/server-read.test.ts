// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Server-side tenant reads for business pages (Phase 02-1; blueprint §3,
// §28): only the tenant session cookie travels (never the platform cookie or
// other cookies of the origin, never a forged tenant header), and every API
// answer maps to one page state.

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
vi.mock("@/lib/env", () => ({
  getServerEnv: () => ({
    appEnv: "test",
    apiBaseUrl: "http://api.internal:8000",
    trustedProxyHops: 0,
  }),
}));

const { tenantApiRead } = await import("./server-read");

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

const respond = (
  status: number,
  body: unknown = {},
  headers: Record<string, string> = {},
) =>
  fetchMock.mockResolvedValueOnce(
    new Response(JSON.stringify(body), { status, headers }),
  );

describe("tenantApiRead", () => {
  it("does not call the API without a tenant session cookie", async () => {
    request.cookies.set("__Host-mti360_psid", "platform-session");
    await expect(tenantApiRead("/leads")).resolves.toEqual({
      kind: "unauthenticated",
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("forwards the tenant cookie only, the user agent and the browser address", async () => {
    request.cookies.set("__Host-mti360_tsid", "tenant-session");
    request.cookies.set("__Host-mti360_psid", "platform-session");
    request.cookies.set("analytics", "x");
    request.headers = new Headers({
      "user-agent": "Chromium test",
      "x-forwarded-for": "203.0.113.9",
      "x-tenant-id": "forged",
      cookie: "__Host-mti360_psid=platform-session; analytics=x",
    });
    respond(200, {
      data: [{ id: "lead-1" }],
      meta: { page: { limit: 25, offset: 0, total: 1 } },
    });

    await expect(tenantApiRead("/leads?status=NEW")).resolves.toEqual({
      kind: "ok",
      data: [{ id: "lead-1" }],
      page: { limit: 25, offset: 0, total: 1 },
    });
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("http://api.internal:8000/api/v1/leads?status=NEW");
    expect(init?.cache).toBe("no-store");
    expect(init?.headers).toEqual({
      accept: "application/json",
      cookie: "__Host-mti360_tsid=tenant-session",
      "user-agent": "Chromium test",
      "x-forwarded-for": "203.0.113.9",
    });
  });

  it.each([
    [401, { kind: "unauthenticated" }],
    [403, { kind: "denied" }],
    [404, { kind: "not-found" }],
  ])("maps %i to a page state", async (status, expected) => {
    request.cookies.set("__Host-mti360_tsid", "tenant-session");
    respond(status, { error: { code: "X", message: "SERVER TEXT" } });
    await expect(tenantApiRead("/leads/abc")).resolves.toEqual(expected);
  });

  it("keeps only the request ID of a failure, never the server message", async () => {
    request.cookies.set("__Host-mti360_tsid", "tenant-session");
    respond(
      500,
      { error: { message: "SELECT secret" } },
      { "x-request-id": "req-42" },
    );
    await expect(tenantApiRead("/courses")).resolves.toEqual({
      kind: "error",
      reference: "req-42",
    });
    fetchMock.mockRejectedValueOnce(new TypeError("fetch failed"));
    await expect(tenantApiRead("/courses")).resolves.toEqual({
      kind: "error",
      reference: null,
    });
  });
});
