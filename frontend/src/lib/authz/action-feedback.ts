import { toast } from "@/design-system/components";
import {
  ApiError,
  NetworkError,
  SessionRefreshedError,
} from "@/lib/api/errors";

// Action feedback inside the Tenant Application (T01-05 UI contract §8.3,
// §11 "Action" column). Fixed copy only: never the server message,
// permission codes, role names or identifiers.

export const ACTION_DENIED = {
  title: "You can't do this",
  description:
    "Your access changed. This action is no longer available to you.",
} as const;

export const SESSION_REFRESHED = {
  title: "Your session was refreshed. Try again.",
} as const;

const DEDUPE_WINDOW_MS = 5000;
const recent = new Map<string, number>();

/** Once per `key` within 5 seconds (repeated identical failures, §11). */
function once(key: string, show: () => void): void {
  const now = Date.now();
  const last = recent.get(key);
  if (last !== undefined && now - last < DEDUPE_WINDOW_MS) return;
  recent.set(key, now);
  show();
}

/** Test hook: forget deduplication state. */
export function resetActionFeedback(): void {
  recent.clear();
}

export type FormFeedback = {
  tone: "error" | "warning";
  title: string;
  body?: string;
};

/**
 * Form or dialog actions: the Alert to show at the top of the form, or null
 * when the error is handled elsewhere (401 navigates; 422 → field errors;
 * 404 → the caller closes and re-fetches).
 */
export function formFeedback(error: unknown): FormFeedback | null {
  if (error instanceof SessionRefreshedError) {
    return { tone: "warning", title: SESSION_REFRESHED.title };
  }
  if (error instanceof NetworkError) {
    return {
      tone: "error",
      title: "Something went wrong",
      body: "Something went wrong. Try again in a moment.",
    };
  }
  if (!(error instanceof ApiError)) {
    return {
      tone: "error",
      title: "Something went wrong",
      body: "Something went wrong. Try again in a moment.",
    };
  }
  switch (error.code) {
    case "PERMISSION_DENIED":
      return {
        tone: "error",
        title: ACTION_DENIED.title,
        body: ACTION_DENIED.description,
      };
    case "CONFLICT":
      return {
        tone: "warning",
        title: "This was changed by someone else",
        body: "This was changed by someone else. Reload it and try again.",
      };
    case "RATE_LIMITED":
      return {
        tone: "warning",
        title: "Too many attempts",
        body: "Too many attempts. Wait a few minutes before trying again.",
      };
    case "SERVICE_UNAVAILABLE":
      return {
        tone: "error",
        title: "This service is temporarily unavailable",
        body: "Please try again shortly.",
      };
    case "AUTHENTICATION_REQUIRED":
    case "VALIDATION_ERROR":
    case "NOT_FOUND":
      return null;
    default:
      return {
        tone: "error",
        title: "Something went wrong",
        body: "Something went wrong. Try again in a moment.",
      };
  }
}

/**
 * Page, row, menu or button actions without a form: one toast per failure,
 * deduplicated by `actionKey` for 5 seconds. 401 shows nothing (the session
 * flow navigates).
 */
export function notifyActionError(error: unknown, actionKey: string): void {
  if (error instanceof ApiError && error.status === 401) return;
  if (error instanceof SessionRefreshedError) {
    once(`${actionKey}:refresh`, () => toast.warning(SESSION_REFRESHED.title));
    return;
  }
  if (error instanceof ApiError) {
    switch (error.code) {
      case "PERMISSION_DENIED":
        once(`${actionKey}:denied`, () =>
          toast.error(ACTION_DENIED.title, {
            description: ACTION_DENIED.description,
          }),
        );
        return;
      case "NOT_FOUND":
        once(`${actionKey}:not-found`, () =>
          toast.info("This item is no longer available."),
        );
        return;
      case "SERVICE_UNAVAILABLE":
        once(`${actionKey}:unavailable`, () =>
          toast.error(
            "This service is temporarily unavailable. Please try again shortly.",
          ),
        );
        return;
    }
  }
  once(`${actionKey}:error`, () =>
    toast.error("Something went wrong. Try again in a moment."),
  );
}
