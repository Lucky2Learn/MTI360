import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { toastQueue } from "@/design-system/components";
import {
  ApiError,
  NetworkError,
  SessionRefreshedError,
} from "@/lib/api/errors";

import {
  ACTION_DENIED,
  formFeedback,
  notifyActionError,
  resetActionFeedback,
} from "./action-feedback";

// RESOURCE-01 and the §11 "Action" column (T01-05 UI contract).

const denied = () => new ApiError({ status: 403, code: "PERMISSION_DENIED" });
const visible = () => toastQueue.visibleToasts.map((item) => item.content);

beforeEach(() => {
  resetActionFeedback();
  vi.useFakeTimers();
});

afterEach(() => {
  for (const item of toastQueue.visibleToasts) toastQueue.close(item.key);
  vi.useRealTimers();
});

describe("notifyActionError (actions without a form)", () => {
  it("shows one 'You can't do this' toast per denied action within 5 seconds", () => {
    notifyActionError(denied(), "member:suspend");
    notifyActionError(denied(), "member:suspend");
    expect(visible()).toEqual([
      {
        tone: "error",
        title: ACTION_DENIED.title,
        description: ACTION_DENIED.description,
      },
    ]);
    vi.advanceTimersByTime(5001);
    notifyActionError(denied(), "member:suspend");
    expect(visible()).toHaveLength(2);
  });

  it("deduplicates per action key", () => {
    notifyActionError(denied(), "member:suspend");
    notifyActionError(denied(), "role:delete");
    expect(visible()).toHaveLength(2);
  });

  it.each([
    [
      new ApiError({ status: 404, code: "NOT_FOUND" }),
      "This item is no longer available.",
    ],
    [
      new ApiError({ status: 503, code: "SERVICE_UNAVAILABLE" }),
      "This service is temporarily unavailable. Please try again shortly.",
    ],
    [new NetworkError(), "Something went wrong. Try again in a moment."],
    [
      new ApiError({ status: 500, code: "INTERNAL_ERROR" }),
      "Something went wrong. Try again in a moment.",
    ],
    [new SessionRefreshedError(), "Your session was refreshed. Try again."],
  ])("maps %o to fixed copy", (error, title) => {
    notifyActionError(error, "row:action");
    expect(visible().map((content) => content.title)).toEqual([title]);
  });

  it("shows nothing for 401 (the session flow navigates)", () => {
    notifyActionError(
      new ApiError({ status: 401, code: "AUTHENTICATION_REQUIRED" }),
      "row:action",
    );
    expect(visible()).toEqual([]);
  });
});

describe("formFeedback (forms and dialogs)", () => {
  it("returns the RESOURCE-01 Alert for a denied form action", () => {
    expect(formFeedback(denied())).toEqual({
      tone: "error",
      title: "You can't do this",
      body: "Your access changed. This action is no longer available to you.",
    });
  });

  it("asks to try again after a session refresh (never resent automatically)", () => {
    expect(formFeedback(new SessionRefreshedError())).toEqual({
      tone: "warning",
      title: "Your session was refreshed. Try again.",
    });
  });

  it("leaves 401, 404 and 422 to their own handling", () => {
    for (const [status, code] of [
      [401, "AUTHENTICATION_REQUIRED"],
      [404, "NOT_FOUND"],
      [422, "VALIDATION_ERROR"],
    ] as const) {
      expect(formFeedback(new ApiError({ status, code }))).toBeNull();
    }
  });

  it("uses fixed copy for conflicts, rate limits and server errors", () => {
    expect(
      formFeedback(new ApiError({ status: 409, code: "CONFLICT" }))?.title,
    ).toBe("This was changed by someone else");
    expect(
      formFeedback(new ApiError({ status: 429, code: "RATE_LIMITED" }))?.body,
    ).toBe("Too many attempts. Wait a few minutes before trying again.");
    expect(
      formFeedback(new ApiError({ status: 500, code: "INTERNAL_ERROR" }))
        ?.title,
    ).toBe("Something went wrong");
  });
});
