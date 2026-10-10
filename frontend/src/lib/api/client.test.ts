import { afterEach, describe, expect, it, vi } from "vitest";

import {
  apiError,
  installFetch,
  jsonResponse,
  noContent,
  ok,
} from "@/test/fetch-mock";

import { apiRequest } from "./client";
import { ApiError, NetworkError } from "./errors";

// Browser API client (T01-09A): same-origin /api/v1, CSRF only on unsafe
// methods, the envelope's data, and errors reduced to code / fields /
// request ID / Retry-After — never the server message.

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("apiRequest", () => {
  it("calls the same-origin proxy and returns the envelope data", async () => {
    const api = installFetch();
    api.on("GET /session", ok({ status: "ready" }));
    await expect(
      apiRequest("/session", { csrfToken: "csrf" }),
    ).resolves.toEqual({
      status: "ready",
    });
    const [call] = api.calls;
    expect(api.fetchMock.mock.calls[0]![0]).toBe("/api/v1/session");
    // GET never carries the CSRF token.
    expect(call!.headers["x-csrf-token"]).toBeUndefined();
    expect(api.fetchMock.mock.calls[0]![1]).toMatchObject({
      credentials: "same-origin",
      cache: "no-store",
    });
  });

  it("sends JSON and the CSRF token on unsafe methods", async () => {
    const api = installFetch();
    api.on("PUT /session/campus", ok({}));
    await apiRequest("/session/campus", {
      method: "PUT",
      body: { campus_id: null },
      csrfToken: "csrf-123",
    });
    expect(api.calls[0]).toMatchObject({
      method: "PUT",
      body: { campus_id: null },
      headers: {
        "content-type": "application/json",
        "x-csrf-token": "csrf-123",
      },
    });
  });

  it("sends FormData as multipart, without a JSON content type (Phase 02-2 uploads)", async () => {
    const api = installFetch();
    api.on("POST /applications/a1/documents", ok({ id: "d1" }));
    const form = new FormData();
    form.append("document_type", "PASSPORT");
    form.append(
      "file",
      new File(["%PDF-1.7"], "passport.pdf", { type: "application/pdf" }),
    );
    await apiRequest("/applications/a1/documents", {
      method: "POST",
      body: form,
      csrfToken: "csrf-123",
    });
    const [call] = api.calls;
    expect(call!.headers["content-type"]).toBeUndefined();
    expect(call!.headers["x-csrf-token"]).toBe("csrf-123");
    expect(call!.body).toEqual({
      document_type: "PASSPORT",
      file: { file: "passport.pdf", type: "application/pdf" },
    });
    expect(api.fetchMock.mock.calls[0]![1]!.body).toBe(form);
  });

  it("returns undefined for 204", async () => {
    const api = installFetch();
    api.on("POST /auth/logout", noContent());
    await expect(
      apiRequest("/auth/logout", { method: "POST" }),
    ).resolves.toBeUndefined();
  });

  it("accepts 202 with a null or empty body (password reset)", async () => {
    const api = installFetch();
    api.on(
      "POST /auth/password-reset",
      jsonResponse(202, null),
      new Response("", { status: 202 }),
    );
    for (let attempt = 0; attempt < 2; attempt += 1) {
      await expect(
        apiRequest("/auth/password-reset", { method: "POST", body: {} }),
      ).resolves.toBeUndefined();
    }
  });

  it("maps the error envelope without keeping the server message", async () => {
    const api = installFetch();
    api.on(
      "POST /auth/password-reset/confirm",
      apiError(422, "VALIDATION_ERROR", {
        details: [{ field: "new_password", code: "password_too_common" }],
        requestId: "req-42",
        message: "Some server sentence",
      }),
    );
    const error = await apiRequest("/auth/password-reset/confirm", {
      method: "POST",
      body: {},
    }).catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ApiError);
    const apiErr = error as ApiError;
    expect(apiErr.status).toBe(422);
    expect(apiErr.code).toBe("VALIDATION_ERROR");
    expect(apiErr.fieldCode("new_password")).toBe("password_too_common");
    expect(apiErr.requestId).toBe("req-42");
    expect(apiErr.message).toBe("VALIDATION_ERROR");
    expect(JSON.stringify(apiErr)).not.toContain("Some server sentence");
    expect(JSON.stringify(apiErr)).not.toContain("SERVER-DETAIL-MESSAGE");
  });

  it("reads Retry-After", async () => {
    const api = installFetch();
    api.on(
      "POST /auth/login",
      apiError(429, "RATE_LIMITED", { headers: { "retry-after": "185" } }),
    );
    const error = (await apiRequest("/auth/login", {
      method: "POST",
      body: {},
    }).catch((caught: unknown) => caught)) as ApiError;
    expect(error.retryAfter).toBe(185);
  });

  it("tolerates a non-JSON error body", async () => {
    const api = installFetch();
    api.on(
      "GET /session",
      new Response("<html>Bad gateway</html>", { status: 500 }),
    );
    const error = (await apiRequest("/session").catch(
      (caught: unknown) => caught,
    )) as ApiError;
    expect(error.code).toBe("HTTP_ERROR");
    expect(error.status).toBe(500);
  });

  it("raises NetworkError when there is no response or the proxy cannot reach the API", async () => {
    const api = installFetch();
    api.on("GET /session", new TypeError("Failed to fetch"));
    await expect(apiRequest("/session")).rejects.toBeInstanceOf(NetworkError);
    api.on(
      "GET /session",
      jsonResponse(502, {
        error: {
          code: "UPSTREAM_UNAVAILABLE",
          message: "x",
          details: [],
          request_id: null,
        },
      }),
    );
    await expect(apiRequest("/session")).rejects.toBeInstanceOf(NetworkError);
  });
});
