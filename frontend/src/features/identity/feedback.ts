import { ApiError, NetworkError } from "@/lib/api/errors";

// Form-level outcomes of the authentication screens (T01-04 UI contract
// §8, §10). Every message is fixed copy chosen by error code; the server's
// `message` is never displayed (§10.2-§10.3), and no copy distinguishes an
// unknown email, a wrong password, a locked or disabled account or a missing
// institute (S2, S8).

export type Feedback = {
  tone: "error" | "warning" | "info" | "success";
  title: string;
  body?: string;
  /** Offer "Reload page" (session refresh needed, S6). */
  reload?: boolean;
};

export const SIGN_IN_FAILED: Feedback = {
  tone: "error",
  title: "We couldn't sign you in",
  body: "Check your email and password and try again. If the problem continues, contact your institute administrator.",
};

export const SESSION_REFRESH_NEEDED: Feedback = {
  tone: "warning",
  title: "Your sign-in page has expired. Reload the page and try again.",
  reload: true,
};

export const NETWORK_FAILURE: Feedback = {
  tone: "error",
  title: "We couldn't reach MTI 360. Check your connection and try again.",
};

export const SERVER_FAILURE: Feedback = {
  tone: "error",
  title: "Something went wrong on our side. Try again in a moment.",
};

/** Rounded retry time from Retry-After, when the API supplies one (OQ-2). */
export function retryHint(error: ApiError): string | undefined {
  if (error.retryAfter === null) return undefined;
  const minutes = Math.max(1, Math.ceil(error.retryAfter / 60));
  return `Try again in about ${minutes} ${minutes === 1 ? "minute" : "minutes"}.`;
}

/** Sign-in rate limit (AUTH-01). */
export function tooManyAttempts(error: ApiError): Feedback {
  return {
    tone: "warning",
    title: "Too many attempts",
    body: retryHint(error) ?? "Wait a few minutes before trying again.",
  };
}

/** Rate limit on the recovery and invitation screens. */
export function tooManyRequests(error: ApiError, after?: string): Feedback {
  return {
    tone: "warning",
    title: after
      ? `Too many requests. Wait a few minutes, then ${after}.`
      : "Too many requests. Wait a few minutes before trying again.",
    body: retryHint(error),
  };
}

/**
 * The common rows of §10.2 (network, server, rate limit, refresh needed).
 * Screen-specific codes (401 on sign-in, 404 on links, 422 on fields) are
 * handled by the screen before calling this.
 */
export function commonFeedback(
  error: unknown,
  rateLimited: (error: ApiError) => Feedback = tooManyRequests,
): Feedback {
  if (error instanceof NetworkError) return NETWORK_FAILURE;
  if (!(error instanceof ApiError)) return SERVER_FAILURE;
  if (error.status === 429) return rateLimited(error);
  // OQ-5: any 403 from /auth/* or /session/* means "session refresh needed".
  if (error.status === 403) return SESSION_REFRESH_NEEDED;
  return SERVER_FAILURE;
}

/** Field errors for the password rules (ADR-0010 §7; T01-04 §8.3). */
export function passwordFieldError(code: string | undefined): string {
  switch (code) {
    case "password_too_common":
      return "This password is too common. Choose a different one.";
    case "password_too_long":
      return "Use 128 characters or fewer.";
    default:
      return "Use at least 12 characters.";
  }
}
