// @vitest-environment node
import { describe, expect, it, vi } from "vitest";

import { inputUrl } from "@/test/fetch-mock";

import { apiCookieHeader, clientAddress } from "./forwarding";
import { isForwardablePath, proxyToApi, type ProxyLogRecord } from "./proxy";

// Same-origin API proxy (T01-09A, D17): exactly the allow-listed headers in
// both directions, the browser address as a single X-Forwarded-For entry,
// status and envelope unchanged, and logs without any secret.

const API = "http://api.internal:8000";
const SECRET_BODY = JSON.stringify({
  email: "ananya.rao@coastal-maritime.example",
  password: "correct horse battery staple",
});

type Captured = { url: string; init: RequestInit & { headers: Headers } };

function upstream(response: Response | Error) {
  const captured: Captured[] = [];
  const fetchImpl = vi.fn(
    (url: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      captured.push({
        url: inputUrl(url),
        init: { ...init, headers: new Headers(init?.headers) },
      });
      return response instanceof Error
        ? Promise.reject(response)
        : Promise.resolve(response);
    },
  );
  return { fetchImpl: fetchImpl as unknown as typeof fetch, captured };
}

function browserRequest(
  path: string,
  init: {
    method?: string;
    headers?: Record<string, string>;
    body?: string;
  } = {},
) {
  return new Request(`http://localhost:3100${path}`, {
    method: init.method ?? "GET",
    headers: init.headers,
    body: init.body,
  });
}

describe("proxy request forwarding", () => {
  it("forwards the allow-listed headers and the body to API_BASE_URL", async () => {
    const { fetchImpl, captured } = upstream(
      new Response(null, { status: 204 }),
    );
    await proxyToApi(
      browserRequest("/api/v1/auth/login", {
        method: "POST",
        body: SECRET_BODY,
        headers: {
          cookie:
            "__Host-mti360_tsid=session-value; mti360.other=1; _ga=tracker",
          "x-csrf-token": "csrf-value",
          origin: "http://localhost:3100",
          "sec-fetch-site": "same-origin",
          "content-type": "application/json",
          accept: "application/json",
          "user-agent": "Chromium test",
          "x-forwarded-for": "203.0.113.9",
        },
      }),
      { apiBaseUrl: API, fetchImpl },
    );
    const [call] = captured;
    expect(call!.url).toBe(`${API}/api/v1/auth/login`);
    expect(call!.init.method).toBe("POST");
    expect(call!.init.redirect).toBe("manual");
    expect(new TextDecoder().decode(call!.init.body as ArrayBuffer)).toBe(
      SECRET_BODY,
    );
    const headers: Record<string, string> = {};
    call!.init.headers.forEach((value, name) => {
      headers[name] = value;
    });
    expect(headers).toEqual({
      cookie: "__Host-mti360_tsid=session-value",
      "x-csrf-token": "csrf-value",
      origin: "http://localhost:3100",
      "sec-fetch-site": "same-origin",
      "content-type": "application/json",
      accept: "application/json",
      "user-agent": "Chromium test",
      "x-forwarded-for": "203.0.113.9",
    });
  });

  it("strips every other request header, including spoofable ones", async () => {
    const { fetchImpl, captured } = upstream(
      new Response(null, { status: 204 }),
    );
    await proxyToApi(
      browserRequest("/api/v1/session", {
        headers: {
          authorization: "Bearer stolen",
          "x-request-id": "attacker-chosen",
          "x-forwarded-host": "evil.example",
          "x-real-ip": "198.51.100.1",
          "x-tenant-id": "7d0c3c2e-6c55-4b8a-9f0e-2c1f4a7b9d01",
          referer: "http://localhost:3100/reset-password",
        },
      }),
      { apiBaseUrl: API, fetchImpl },
    );
    const sent = [...captured[0]!.init.headers.keys()];
    for (const name of [
      "authorization",
      "x-request-id",
      "x-forwarded-host",
      "x-real-ip",
      "x-tenant-id",
      "referer",
      "cookie",
    ]) {
      expect(sent).not.toContain(name);
    }
  });

  it("keeps the query string and sends GET without a body", async () => {
    const { fetchImpl, captured } = upstream(
      new Response("{}", { status: 200 }),
    );
    await proxyToApi(browserRequest("/api/v1/members?limit=20&offset=40"), {
      apiBaseUrl: API,
      fetchImpl,
    });
    expect(captured[0]!.url).toBe(`${API}/api/v1/members?limit=20&offset=40`);
    expect(captured[0]!.init.body).toBeUndefined();
  });

  it("forwards only the session cookie of the called realm (D9B-10)", () => {
    const both =
      "theme=dark; __Host-mti360_tsid=a; __Host-mti360_psid=b; broken; =x";
    expect(apiCookieHeader(both, "/api/v1/session")).toBe(
      "__Host-mti360_tsid=a",
    );
    expect(apiCookieHeader(both, "/api/v1/auth/login")).toBe(
      "__Host-mti360_tsid=a",
    );
    expect(apiCookieHeader(both, "/api/v1/platform/session")).toBe(
      "__Host-mti360_psid=b",
    );
    expect(apiCookieHeader(both, "/api/v1/platform")).toBe(
      "__Host-mti360_psid=b",
    );
    // A tenant path that merely starts with the letters "platform".
    expect(apiCookieHeader(both, "/api/v1/platformish")).toBe(
      "__Host-mti360_tsid=a",
    );
    expect(
      apiCookieHeader("__Host-mti360_psid=b", "/api/v1/session"),
    ).toBeNull();
    expect(
      apiCookieHeader("__Host-mti360_tsid=a", "/api/v1/platform/session"),
    ).toBeNull();
    expect(apiCookieHeader("theme=dark", "/api/v1/session")).toBeNull();
    expect(apiCookieHeader(null, "/api/v1/session")).toBeNull();
  });

  it("never sends both realm cookies upstream", async () => {
    for (const path of ["/api/v1/session", "/api/v1/platform/session"]) {
      const { fetchImpl, captured } = upstream(
        new Response("{}", { status: 200 }),
      );
      await proxyToApi(
        browserRequest(path, {
          headers: {
            cookie: "__Host-mti360_tsid=tenant-value; __Host-mti360_psid=pv",
          },
        }),
        { apiBaseUrl: API, fetchImpl },
      );
      const cookie = captured[0]!.init.headers.get("cookie");
      expect(cookie).toBe(
        path.startsWith("/api/v1/platform")
          ? "__Host-mti360_psid=pv"
          : "__Host-mti360_tsid=tenant-value",
      );
    }
  });
});

describe("browser address forwarding (TRUSTED_PROXY_HOPS=1)", () => {
  it("sends exactly one X-Forwarded-For entry: the right-most, infrastructure-added one", async () => {
    const { fetchImpl, captured } = upstream(
      new Response(null, { status: 204 }),
    );
    await proxyToApi(
      browserRequest("/api/v1/auth/login", {
        method: "POST",
        body: "{}",
        // A client wrote "6.6.6.6, 7.7.7.7"; the ingress appended the real one.
        headers: { "x-forwarded-for": "6.6.6.6, 7.7.7.7, 203.0.113.9" },
      }),
      { apiBaseUrl: API, fetchImpl },
    );
    expect(captured[0]!.init.headers.get("x-forwarded-for")).toBe(
      "203.0.113.9",
    );
  });

  it("trusts exactly TRUSTED_PROXY_HOPS proxies (Cloudflare + reverse proxy = 2)", async () => {
    // Client wrote 6.6.6.6; Cloudflare appended the client (203.0.113.9);
    // the reverse proxy appended Cloudflare's edge (198.51.100.20).
    const header = "6.6.6.6, 203.0.113.9, 198.51.100.20";
    const { fetchImpl, captured } = upstream(
      new Response(null, { status: 204 }),
    );
    await proxyToApi(
      browserRequest("/api/v1/session", {
        headers: { "x-forwarded-for": header },
      }),
      { apiBaseUrl: API, fetchImpl, trustedProxyHops: 2 },
    );
    expect(captured[0]!.init.headers.get("x-forwarded-for")).toBe(
      "203.0.113.9",
    );
    expect(clientAddress(header, 0)).toBe("198.51.100.20");
    expect(clientAddress(header, 1)).toBe("198.51.100.20");
    expect(clientAddress(header, 2)).toBe("203.0.113.9");
    // Fewer entries than trusted hops: no address rather than a guess.
    expect(clientAddress("203.0.113.9", 2)).toBeNull();
  });

  it("accepts IPv6 and IPv4-mapped peers and drops unusable values", () => {
    expect(clientAddress("::1")).toBe("::1");
    expect(clientAddress("::ffff:127.0.0.1")).toBe("::ffff:127.0.0.1");
    expect(clientAddress("203.0.113.9 , ")).toBe("203.0.113.9");
    expect(clientAddress("<script>")).toBeNull();
    expect(clientAddress("")).toBeNull();
    expect(clientAddress(null)).toBeNull();
  });

  it("sends no X-Forwarded-For when no address is known", async () => {
    const { fetchImpl, captured } = upstream(
      new Response(null, { status: 204 }),
    );
    await proxyToApi(browserRequest("/api/v1/session"), {
      apiBaseUrl: API,
      fetchImpl,
    });
    expect(captured[0]!.init.headers.has("x-forwarded-for")).toBe(false);
  });
});

describe("proxy responses", () => {
  it("returns status, body, every Set-Cookie, X-Request-ID and Retry-After", async () => {
    const headers = new Headers({
      "content-type": "application/json",
      "x-request-id": "5f0c-request",
      "retry-after": "120",
      server: "uvicorn",
      "x-powered-by": "internal",
    });
    headers.append(
      "set-cookie",
      "__Host-mti360_tsid=new; Path=/; Secure; HttpOnly; SameSite=Lax",
    );
    headers.append("set-cookie", "other=1; Path=/");
    const body = JSON.stringify({
      error: {
        code: "RATE_LIMITED",
        message: "Too many requests.",
        details: [],
        request_id: "5f0c-request",
      },
    });
    const { fetchImpl } = upstream(
      new Response(body, { status: 429, headers }),
    );
    const response = await proxyToApi(
      browserRequest("/api/v1/auth/login", { method: "POST", body: "{}" }),
      { apiBaseUrl: API, fetchImpl },
    );
    expect(response.status).toBe(429);
    expect(await response.text()).toBe(body);
    expect(response.headers.getSetCookie()).toEqual([
      "__Host-mti360_tsid=new; Path=/; Secure; HttpOnly; SameSite=Lax",
      "other=1; Path=/",
    ]);
    expect(response.headers.get("x-request-id")).toBe("5f0c-request");
    expect(response.headers.get("retry-after")).toBe("120");
    expect(response.headers.get("server")).toBeNull();
    expect(response.headers.get("x-powered-by")).toBeNull();
    expect(response.headers.get("cache-control")).toBe("no-store");
  });

  it("passes 204 through without a body and keeps an API Cache-Control", async () => {
    const { fetchImpl } = upstream(
      new Response(null, {
        status: 204,
        headers: { "cache-control": "private, max-age=0" },
      }),
    );
    const response = await proxyToApi(
      browserRequest("/api/v1/auth/logout", { method: "POST" }),
      { apiBaseUrl: API, fetchImpl },
    );
    expect(response.status).toBe(204);
    expect(response.body).toBeNull();
    expect(response.headers.get("cache-control")).toBe("private, max-age=0");
  });

  it("answers 502 UPSTREAM_UNAVAILABLE and logs no secret when the API is unreachable", async () => {
    const log = vi.fn<(record: ProxyLogRecord) => void>();
    const { fetchImpl } = upstream(new TypeError("fetch failed"));
    const response = await proxyToApi(
      browserRequest(
        "/api/v1/auth/password-reset/confirm?debug=token-in-query",
        {
          method: "POST",
          body: JSON.stringify({
            token: "reset-token-value",
            new_password: "secret-pass-123",
          }),
          headers: {
            cookie: "__Host-mti360_tsid=session-value",
            "x-csrf-token": "csrf-value",
          },
        },
      ),
      { apiBaseUrl: API, fetchImpl, log },
    );
    expect(response.status).toBe(502);
    expect(await response.json()).toEqual({
      error: {
        code: "UPSTREAM_UNAVAILABLE",
        message: "The service could not be reached. Please try again.",
        details: [],
        request_id: null,
      },
    });
    expect(log).toHaveBeenCalledWith({
      event: "api_proxy.upstream_unavailable",
      method: "POST",
      path: "/api/v1/auth/password-reset/confirm",
    });
    const logged = JSON.stringify(log.mock.calls);
    for (const secret of [
      "reset-token-value",
      "secret-pass-123",
      "session-value",
      "csrf-value",
      "token-in-query",
    ]) {
      expect(logged).not.toContain(secret);
    }
  });

  it("logs nothing when the API answers, whatever the status", async () => {
    const log = vi.fn();
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});
    const { fetchImpl } = upstream(new Response("{}", { status: 401 }));
    await proxyToApi(
      browserRequest("/api/v1/auth/login", {
        method: "POST",
        body: SECRET_BODY,
      }),
      { apiBaseUrl: API, fetchImpl, log },
    );
    expect(log).not.toHaveBeenCalled();
    expect(consoleError).not.toHaveBeenCalled();
  });
});

describe("forwardable paths", () => {
  it.each([
    "/api/v1/session",
    "/api/v1/auth/mfa/verify",
    "/api/v1/members/7d0c3c2e-6c55-4b8a-9f0e-2c1f4a7b9d01",
    "/api/v1",
  ])("forwards %s", (path) => {
    expect(isForwardablePath(path)).toBe(true);
  });

  it.each([
    "/api/v2/session",
    "/api/internal",
    "/api/v1/../admin",
    "/api/v1/%2e%2e/admin",
    "/api/v1/session%2Fx",
    "/api/v1/a%5Cb",
    "/api/v1/%zz",
    "/health",
  ])("refuses %s", (path) => {
    expect(isForwardablePath(path)).toBe(false);
  });

  it("does not call the API for a refused path", async () => {
    const { fetchImpl } = upstream(new Response(null, { status: 204 }));
    const response = await proxyToApi(browserRequest("/api/internal/x"), {
      apiBaseUrl: API,
      fetchImpl,
    });
    expect(response.status).toBe(404);
    expect(fetchImpl).not.toHaveBeenCalled();
  });
});
