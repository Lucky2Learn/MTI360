import { vi } from "vitest";

// A scripted fetch for browser-side API tests (T01-09A). Each call is matched
// to the next scripted response for its "METHOD /path" and recorded with its
// headers and parsed body, so tests can assert exactly what was sent.

export type RecordedCall = {
  method: string;
  path: string;
  headers: Record<string, string>;
  body: unknown;
};

type Scripted = Response | (() => Response) | Error;

export function jsonResponse(
  status: number,
  body: unknown,
  headers: Record<string, string> = {},
): Response {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...headers },
  });
}

export const ok = (data: unknown) => jsonResponse(200, { data, meta: {} });
export const noContent = () => jsonResponse(204, null);

export function apiError(
  status: number,
  code: string,
  options: {
    details?: { field: string | null; code: string; message?: string }[];
    message?: string;
    requestId?: string;
    headers?: Record<string, string>;
  } = {},
): Response {
  return jsonResponse(
    status,
    {
      error: {
        code,
        // A server message the UI must never display.
        message: options.message ?? `SERVER-MESSAGE-${code}`,
        details: (options.details ?? []).map((detail) => ({
          message: "SERVER-DETAIL-MESSAGE",
          ...detail,
        })),
        request_id: options.requestId ?? "req-0000",
      },
    },
    options.headers,
  );
}

/** The URL of a fetch input, whatever its form. */
export function inputUrl(input: RequestInfo | URL): string {
  if (typeof input === "string") return input;
  return input instanceof URL ? input.href : input.url;
}

export function installFetch() {
  const script = new Map<string, Scripted[]>();
  const calls: RecordedCall[] = [];

  const fetchMock = vi.fn(
    (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      const url = new URL(inputUrl(input), "http://localhost");
      const method = (init?.method ?? "GET").toUpperCase();
      const path = url.pathname.replace(/^\/api\/v1/, "");
      const headers = Object.fromEntries(new Headers(init?.headers).entries());
      const body =
        typeof init?.body === "string"
          ? (JSON.parse(init.body) as unknown)
          : undefined;
      calls.push({ method, path, headers, body });
      const queue = script.get(`${method} ${path}`);
      const next = queue?.shift();
      if (next === undefined) {
        return Promise.reject(
          new Error(`unscripted request: ${method} ${path}`),
        );
      }
      if (next instanceof Error) return Promise.reject(next);
      return Promise.resolve(typeof next === "function" ? next() : next);
    },
  );
  vi.stubGlobal("fetch", fetchMock);

  return {
    calls,
    fetchMock,
    /** Queue responses for "METHOD /path" (path without /api/v1). */
    on(route: string, ...responses: Scripted[]) {
      script.set(route, [...(script.get(route) ?? []), ...responses]);
    },
    callsTo(route: string) {
      return calls.filter((call) => `${call.method} ${call.path}` === route);
    },
  };
}
