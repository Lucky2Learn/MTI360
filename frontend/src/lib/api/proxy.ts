import { UPSTREAM_UNAVAILABLE } from "./errors";
import { apiCookieHeader, clientAddress } from "./forwarding";

// Same-origin API proxy (T01-09A; D17, repository-structure.md §2). The
// browser calls /api/v1/* on the application origin; the Next.js server
// forwards to the internal API_BASE_URL, which never reaches browser code.
//
// Forwarded request headers (allow-list): Cookie (only the session cookie of
// the called realm: platform paths the platform cookie, every other path the
// tenant cookie; T01-09B D9B-10),
// X-CSRF-Token, Origin, Sec-Fetch-Site, Content-Type, Accept, User-Agent, and
// X-Forwarded-For rebuilt with exactly one entry: the browser address
// (clientAddress, trusting TRUSTED_PROXY_HOPS proxies in front of Next.js). Everything else — including a client-supplied
// X-Forwarded-For chain or X-Request-ID — is dropped.
//
// Returned response headers (allow-list): Set-Cookie (every one), X-Request-ID,
// Retry-After, Content-Type, Cache-Control (no-store when the API sets none).
// Status codes and the error envelope pass through unchanged.
//
// Logging: only an upstream failure is logged, as method + path + reason.
// Never request or response bodies (passwords, tokens, MFA and recovery
// codes), query strings, cookies, CSRF tokens or other headers (T01-04 UI
// contract S11).

const API_PATH = /^\/api\/v1(?:\/[A-Za-z0-9\-._~%]*)*$/;
const FORWARDED_REQUEST_HEADERS = [
  "x-csrf-token",
  "origin",
  "sec-fetch-site",
  "content-type",
  "accept",
  "user-agent",
] as const;
const RETURNED_RESPONSE_HEADERS = [
  "content-type",
  "cache-control",
  "x-request-id",
  "retry-after",
] as const;
const BODYLESS_METHODS = new Set(["GET", "HEAD"]);
const NULL_BODY_STATUS = new Set([101, 204, 205, 304]);
const UPSTREAM_TIMEOUT_MS = 30_000;

export type ProxyLogRecord = {
  event: "api_proxy.upstream_unavailable";
  method: string;
  path: string;
};

export type ProxyOptions = {
  /** Validated server-only base URL (lib/env.ts). */
  apiBaseUrl: string;
  /** Trusted proxies in front of this server (lib/env.ts, default 0). */
  trustedProxyHops?: number;
  fetchImpl?: typeof fetch;
  log?: (record: ProxyLogRecord) => void;
};

function envelope(status: number, code: string, message: string): Response {
  return Response.json(
    { error: { code, message, details: [], request_id: null } },
    { status, headers: { "cache-control": "no-store" } },
  );
}

/** A path the proxy may forward: /api/v1/…, no dot segments or backslashes. */
export function isForwardablePath(pathname: string): boolean {
  if (!API_PATH.test(pathname)) return false;
  const segments = pathname.split("/");
  return !segments.some((segment) => {
    let decoded: string;
    try {
      decoded = decodeURIComponent(segment);
    } catch {
      return true;
    }
    return (
      decoded === "." ||
      decoded === ".." ||
      decoded.includes("/") ||
      decoded.includes("\\")
    );
  });
}

/** Request headers for the API at `apiPath` (see the allow-list above). */
export function upstreamRequestHeaders(
  incoming: Headers,
  apiPath: string,
  trustedProxyHops = 0,
): Headers {
  const headers = new Headers();
  for (const name of FORWARDED_REQUEST_HEADERS) {
    const value = incoming.get(name);
    if (value !== null) headers.set(name, value);
  }
  const cookie = apiCookieHeader(incoming.get("cookie"), apiPath);
  if (cookie) headers.set("cookie", cookie);
  const address = clientAddress(
    incoming.get("x-forwarded-for"),
    trustedProxyHops,
  );
  if (address) headers.set("x-forwarded-for", address);
  return headers;
}

/** Response headers for the browser (see the allow-list above). */
export function downstreamResponseHeaders(upstream: Headers): Headers {
  const headers = new Headers();
  for (const name of RETURNED_RESPONSE_HEADERS) {
    const value = upstream.get(name);
    if (value !== null) headers.set(name, value);
  }
  for (const cookie of upstream.getSetCookie()) {
    headers.append("set-cookie", cookie);
  }
  if (!headers.has("cache-control")) headers.set("cache-control", "no-store");
  return headers;
}

export async function proxyToApi(
  request: Request,
  {
    apiBaseUrl,
    trustedProxyHops = 0,
    fetchImpl = fetch,
    log = logProxyEvent,
  }: ProxyOptions,
): Promise<Response> {
  const url = new URL(request.url);
  if (!isForwardablePath(url.pathname)) {
    return envelope(404, "NOT_FOUND", "The requested resource was not found.");
  }

  const method = request.method.toUpperCase();
  let upstream: Response;
  try {
    upstream = await fetchImpl(`${apiBaseUrl}${url.pathname}${url.search}`, {
      method,
      headers: upstreamRequestHeaders(
        request.headers,
        url.pathname,
        trustedProxyHops,
      ),
      body: BODYLESS_METHODS.has(method)
        ? undefined
        : await request.arrayBuffer(),
      redirect: "manual",
      cache: "no-store",
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
    });
  } catch {
    log({
      event: "api_proxy.upstream_unavailable",
      method,
      path: url.pathname,
    });
    return envelope(
      502,
      UPSTREAM_UNAVAILABLE,
      "The service could not be reached. Please try again.",
    );
  }

  return new Response(
    NULL_BODY_STATUS.has(upstream.status) ? null : upstream.body,
    {
      status: upstream.status,
      headers: downstreamResponseHeaders(upstream.headers),
    },
  );
}

function logProxyEvent(record: ProxyLogRecord): void {
  // Structured, value-free: no body, query, cookie or header ever.
  console.error(JSON.stringify(record));
}
