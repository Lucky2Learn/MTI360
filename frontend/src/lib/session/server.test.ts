// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { readySession, sessionIn } from "@/test/session-fixtures";

// The server-side gate of /app/* (T01-09A; T01-05 UI contract §7 step 1):
// the session comes only from the API, read with the request's session
// cookie; status decides the redirect; `next` is the requested path.

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
  }),
}));

const { readTenantSession, requireReadyTenantSession, SessionReadError } =
  await import("./server");

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

describe("readTenantSession", () => {
  it("returns null without calling the API when there is no session cookie", async () => {
    await expect(readTenantSession()).resolves.toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("reads GET /api/v1/session with only the session cookie, the user agent and the browser address", async () => {
    request.cookies.set("__Host-mti360_tsid", "opaque-session");
    request.headers = new Headers({
      "user-agent": "Chromium test",
      "x-forwarded-for": "6.6.6.6, 203.0.113.9",
      "x-tenant-id": "forged",
      authorization: "Bearer forged",
    });
    const session = readySession();
    respond(200, { data: session, meta: {} });

    await expect(readTenantSession()).resolves.toEqual(session);
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("http://api.internal:8000/api/v1/session");
    expect(init?.cache).toBe("no-store");
    expect(init?.headers).toEqual({
      accept: "application/json",
      cookie: "__Host-mti360_tsid=opaque-session",
      "user-agent": "Chromium test",
      "x-forwarded-for": "203.0.113.9",
    });
  });

  it("treats 401 as no session", async () => {
    request.cookies.set("__Host-mti360_tsid", "expired");
    respond(401, { error: { code: "AUTHENTICATION_REQUIRED" } });
    await expect(readTenantSession()).resolves.toBeNull();
  });

  it("fails safely on other errors (the error boundary shows fixed text)", async () => {
    request.cookies.set("__Host-mti360_tsid", "opaque");
    respond(500, { error: { code: "INTERNAL_ERROR", message: "stack trace" } });
    const error = await readTenantSession().catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(SessionReadError);
    expect((error as Error).message).toBe("SESSION_READ_FAILED");

    fetchMock.mockRejectedValueOnce(new TypeError("connect ECONNREFUSED"));
    await expect(readTenantSession()).rejects.toBeInstanceOf(SessionReadError);
  });
});

describe("requireReadyTenantSession", () => {
  const path = "/app/administration/users";

  beforeEach(() => {
    request.cookies.set("__Host-mti360_tsid", "opaque");
  });

  it("returns a ready session", async () => {
    const session = readySession({ permissions: ["member.read"] });
    respond(200, { data: session });
    await expect(requireReadyTenantSession(path)).resolves.toEqual(session);
  });

  it("no session → /session-ended with next (J10)", async () => {
    respond(401);
    await expect(requireReadyTenantSession(path)).rejects.toThrow(
      "NEXT_REDIRECT /session-ended?reason=ended&next=%2Fapp%2Fadministration%2Fusers",
    );
  });

  it("membership suspended or revoked (no institute) → /select-institute with next", async () => {
    respond(200, { data: sessionIn("institute_selection_required") });
    await expect(requireReadyTenantSession(path)).rejects.toThrow(
      "NEXT_REDIRECT /select-institute?next=%2Fapp%2Fadministration%2Fusers",
    );
  });

  it("no institutes left at all → /select-institute (its empty state)", async () => {
    respond(200, {
      data: sessionIn("institute_selection_required", { institutes: [] }),
    });
    await expect(requireReadyTenantSession("/app")).rejects.toThrow(
      "NEXT_REDIRECT /select-institute",
    );
  });

  it("campus choice required → /select-campus with next and the withdrawn notice", async () => {
    respond(200, { data: sessionIn("campus_selection_required") });
    await expect(requireReadyTenantSession(path)).rejects.toThrow(
      "NEXT_REDIRECT /select-campus?reason=campus-unavailable&next=%2Fapp%2Fadministration%2Fusers",
    );
  });

  it("an MFA-pending status is never a usable session", async () => {
    respond(200, { data: sessionIn("mfa_required") });
    await expect(requireReadyTenantSession(path)).rejects.toThrow(
      "NEXT_REDIRECT /session-ended",
    );
  });

  it("never carries an unsafe path as next", async () => {
    respond(401);
    await expect(requireReadyTenantSession("/app/%2F%2Fevil")).rejects.toThrow(
      /NEXT_REDIRECT \/session-ended\?reason=ended$/,
    );
  });
});
