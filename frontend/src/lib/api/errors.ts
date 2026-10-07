// API error model (T01-09A). The backend error envelope is
// { error: { code, message, details: [{ field, code, message }], request_id } }.
//
// Only the machine-readable parts are kept: `code`, the field names and codes
// of `details`, the request ID (shown as a support reference) and Retry-After.
// The server `message` texts are deliberately dropped here, so no screen can
// render them (T01-04 UI contract §10.2-§10.3); screens map codes to copy.

export type ApiErrorDetail = {
  field: string | null;
  code: string;
};

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: readonly ApiErrorDetail[];
  readonly requestId: string | null;
  /** Seconds from the Retry-After header, when present. */
  readonly retryAfter: number | null;

  constructor(init: {
    status: number;
    code: string;
    details?: readonly ApiErrorDetail[];
    requestId?: string | null;
    retryAfter?: number | null;
  }) {
    // The message is the code only: never server text, never a value.
    super(init.code);
    this.name = "ApiError";
    this.status = init.status;
    this.code = init.code;
    this.details = init.details ?? [];
    this.requestId = init.requestId ?? null;
    this.retryAfter = init.retryAfter ?? null;
  }

  /** True when a detail names `field` (VALIDATION_ERROR). */
  hasField(field: string): boolean {
    return this.details.some((detail) => detail.field === field);
  }

  /** The detail code for `field`, e.g. "password_too_common". */
  fieldCode(field: string): string | undefined {
    return this.details.find((detail) => detail.field === field)?.code;
  }
}

/** No response: offline, DNS, the proxy could not reach the API, aborted. */
export class NetworkError extends Error {
  constructor() {
    super("NETWORK_ERROR");
    this.name = "NetworkError";
  }
}

/**
 * An unsafe request was refused with SESSION_REFRESH_REQUIRED and the session
 * was re-read (fresh CSRF token). It is never resent automatically: the UI
 * offers "Try again" (T01-05 UI contract §11).
 */
export class SessionRefreshedError extends Error {
  constructor() {
    super("SESSION_REFRESHED");
    this.name = "SessionRefreshedError";
  }
}

/** The proxy's code when the API cannot be reached (treated as no response). */
export const UPSTREAM_UNAVAILABLE = "UPSTREAM_UNAVAILABLE";

function parseRetryAfter(value: string | null): number | null {
  if (value === null) return null;
  const seconds = Number(value);
  return Number.isFinite(seconds) && seconds > 0 ? Math.ceil(seconds) : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

/** Builds an ApiError from a non-2xx response; tolerant of non-JSON bodies. */
export async function apiErrorFrom(response: Response): Promise<ApiError> {
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  const error = isRecord(body) && isRecord(body.error) ? body.error : {};
  const details = Array.isArray(error.details)
    ? error.details.filter(isRecord).map((detail) => ({
        field: typeof detail.field === "string" ? detail.field : null,
        code: typeof detail.code === "string" ? detail.code : "invalid",
      }))
    : [];
  return new ApiError({
    status: response.status,
    code: typeof error.code === "string" ? error.code : "HTTP_ERROR",
    details,
    requestId:
      (typeof error.request_id === "string" ? error.request_id : null) ??
      response.headers.get("x-request-id"),
    retryAfter: parseRetryAfter(response.headers.get("retry-after")),
  });
}

/**
 * A request answered 403 STEP_UP_REQUIRED and the person cancelled the
 * step-up dialog (T01-09B D9B-6). The action was not performed; the UI shows
 * nothing.
 */
export class StepUpCancelledError extends Error {
  constructor() {
    super("STEP_UP_CANCELLED");
    this.name = "StepUpCancelledError";
  }
}

/**
 * After a successful step-up, the single resend of the original request was
 * refused with STEP_UP_REQUIRED again. It is never resent a second time
 * (D9B-6: no loop).
 */
export class StepUpFailedError extends Error {
  constructor() {
    super("STEP_UP_FAILED");
    this.name = "StepUpFailedError";
  }
}
