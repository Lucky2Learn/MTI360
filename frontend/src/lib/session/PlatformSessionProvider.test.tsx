import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useEffect } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { StepUpDialog } from "@/features/platform-identity/StepUpDialog";
import {
  ApiError,
  SessionRefreshedError,
  StepUpCancelledError,
  StepUpFailedError,
} from "@/lib/api/errors";
import type { PlatformSessionWire } from "@/lib/api/types";
import { apiError, installFetch, ok } from "@/test/fetch-mock";
import { PLATFORM_CSRF, platformSession } from "@/test/platform-fixtures";

import {
  PlatformSessionProvider,
  PlatformSessionSync,
  usePlatformSession,
  type PlatformSessionValue,
} from "./PlatformSessionProvider";

// Platform session context (T01-09B UI contract §8, §9): the T01-05 §11
// matrix on /api/v1/platform/*, reactive step-up with exactly one resend,
// visibility re-reads, and no authority kept anywhere but the server's
// latest answer.

vi.setConfig({ testTimeout: 20_000 });

const documentNav = vi.hoisted(() => ({
  assignLocation: vi.fn<(url: string) => void>(),
  reloadDocument: vi.fn(),
  currentPath: vi.fn(() => "/platform/profile"),
}));
vi.mock("./document", () => documentNav);

let context: PlatformSessionValue;
function Probe() {
  const value = usePlatformSession();
  useEffect(() => {
    context = value;
  });
  return (
    <p data-testid="probe">
      {[...value.session.permissions].join(",")}|{value.session.csrfToken}
    </p>
  );
}

function renderProvider(session: PlatformSessionWire = platformSession()) {
  return render(
    <PlatformSessionProvider initialSession={session}>
      <Probe />
      <StepUpDialog />
    </PlatformSessionProvider>,
  );
}

const setVisibility = (state: DocumentVisibilityState) => {
  Object.defineProperty(document, "visibilityState", {
    configurable: true,
    get: () => state,
  });
  document.dispatchEvent(new Event("visibilitychange"));
};

/** Settles at once, so a rejection is never unhandled while the test acts. */
function capture<T>(promise: Promise<T>) {
  return promise.then(
    (value) => ({ value, error: undefined as unknown }),
    (error: unknown) => ({ value: undefined, error }),
  );
}

const REGENERATE = "POST /platform/session/mfa/recovery-codes";
const STEP_UP = "POST /platform/session/step-up";
const CODES = { recovery_codes: ["abcde-fghij"] };

beforeEach(() => {
  documentNav.assignLocation.mockReset();
  documentNav.currentPath.mockReturnValue("/platform/profile");
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("platform requests", () => {
  it("prefixes /platform and sends the session's CSRF token on unsafe methods", async () => {
    const api = installFetch();
    api.on(REGENERATE, ok(CODES));
    renderProvider();
    await expect(
      context.request("/session/mfa/recovery-codes", { method: "POST" }),
    ).resolves.toEqual(CODES);
    expect(api.callsTo(REGENERATE)[0]!.headers["x-csrf-token"]).toBe(
      PLATFORM_CSRF,
    );
  });

  it("401: re-reads the platform session; none → /platform/session-ended with next", async () => {
    const api = installFetch();
    api.on("GET /platform/tenants", apiError(401, "AUTHENTICATION_REQUIRED"));
    api.on("GET /platform/session", apiError(401, "AUTHENTICATION_REQUIRED"));
    renderProvider();
    await expect(context.request("/tenants")).rejects.toBeInstanceOf(ApiError);
    expect(documentNav.assignLocation).toHaveBeenCalledWith(
      "/platform/session-ended?reason=ended&next=%2Fplatform%2Fprofile",
    );
  });

  it("SESSION_REFRESH_REQUIRED: re-reads, then retries a GET exactly once", async () => {
    const api = installFetch();
    api.on(
      "GET /platform/tenants",
      apiError(403, "SESSION_REFRESH_REQUIRED"),
      ok([]),
    );
    api.on("GET /platform/session", ok(platformSession({ csrf_token: "new" })));
    renderProvider();
    await expect(context.request("/tenants")).resolves.toEqual([]);
    expect(api.callsTo("GET /platform/tenants")).toHaveLength(2);
    await waitFor(() =>
      expect(screen.getByTestId("probe")).toHaveTextContent("|new"),
    );
  });

  it("SESSION_REFRESH_REQUIRED: an unsafe request is never resent", async () => {
    const api = installFetch();
    api.on(REGENERATE, apiError(403, "SESSION_REFRESH_REQUIRED"));
    api.on("GET /platform/session", ok(platformSession({ csrf_token: "new" })));
    renderProvider();
    await expect(
      context.request("/session/mfa/recovery-codes", { method: "POST" }),
    ).rejects.toBeInstanceOf(SessionRefreshedError);
    expect(api.callsTo(REGENERATE)).toHaveLength(1);
  });

  it("PERMISSION_DENIED: re-reads in the background and rethrows", async () => {
    const api = installFetch();
    api.on("GET /platform/audit-events", apiError(403, "PERMISSION_DENIED"));
    api.on(
      "GET /platform/session",
      ok(platformSession({ permissions: ["tenant.read"] })),
    );
    renderProvider();
    await expect(context.request("/audit-events")).rejects.toMatchObject({
      code: "PERMISSION_DENIED",
    });
    await waitFor(() =>
      expect(screen.getByTestId("probe")).toHaveTextContent(/^tenant\.read\|/),
    );
  });

  it("re-reads on tab visibility; an ended session navigates", async () => {
    const api = installFetch();
    api.on("GET /platform/session", apiError(401, "AUTHENTICATION_REQUIRED"));
    renderProvider();
    act(() => setVisibility("visible"));
    await waitFor(() =>
      expect(documentNav.assignLocation).toHaveBeenCalledWith(
        "/platform/session-ended?reason=ended&next=%2Fplatform%2Fprofile",
      ),
    );
  });

  it("never polls: no request without a trigger", async () => {
    const api = installFetch();
    renderProvider();
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(api.calls).toHaveLength(0);
  });

  it("PlatformSessionSync replaces the session; a pending answer is ignored", async () => {
    installFetch();
    const { rerender } = renderProvider();
    rerender(
      <PlatformSessionProvider initialSession={platformSession()}>
        <PlatformSessionSync
          session={platformSession({ permissions: ["audit.read"] })}
        />
        <Probe />
      </PlatformSessionProvider>,
    );
    await waitFor(() =>
      expect(screen.getByTestId("probe")).toHaveTextContent(/^audit\.read\|/),
    );
  });
});

describe("step-up (PAUTH-07, D9B-6)", () => {
  it("opens on STEP_UP_REQUIRED, verifies the code and resends the original request exactly once", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on(REGENERATE, apiError(403, "STEP_UP_REQUIRED"), ok(CODES));
    api.on(STEP_UP, ok(platformSession({ csrf_token: "after-step-up" })));
    renderProvider();

    const result = capture(
      context.request("/session/mfa/recovery-codes", { method: "POST" }),
    );
    const dialog = await screen.findByRole("dialog", {
      name: "Confirm it's you",
    });
    expect(dialog).toHaveTextContent(
      "Lost your authenticator? Ask another Super Admin to reset your two-step verification.",
    );
    // TOTP only: no recovery-code option in step-up.
    expect(screen.queryByText(/recovery code/i)).toBeNull();
    const field = screen.getByLabelText(/Authentication code/);
    expect(field).toHaveFocus();
    expect(field).toHaveAttribute("autocomplete", "one-time-code");
    await user.type(field, "123456");
    await user.click(
      screen.getByRole("button", { name: "Verify and continue" }),
    );

    expect((await result).value).toEqual(CODES);
    const [stepUp] = api.callsTo(STEP_UP);
    expect(stepUp!.body).toEqual({ code: "123456" });
    expect(stepUp!.headers["x-csrf-token"]).toBe(PLATFORM_CSRF);
    const regenerations = api.callsTo(REGENERATE);
    expect(regenerations).toHaveLength(2);
    // The resend carries the (unchanged by step-up) session CSRF token.
    expect(regenerations[1]!.headers["x-csrf-token"]).toBe("after-step-up");
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
  });

  it("cancel performs nothing: no resend, StepUpCancelledError, no step-up call", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on(REGENERATE, apiError(403, "STEP_UP_REQUIRED"));
    renderProvider();
    const result = capture(
      context.request("/session/mfa/recovery-codes", { method: "POST" }),
    );
    await screen.findByRole("dialog", { name: "Confirm it's you" });
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect((await result).error).toBeInstanceOf(StepUpCancelledError);
    expect(api.callsTo(REGENERATE)).toHaveLength(1);
    expect(api.callsTo(STEP_UP)).toHaveLength(0);
  });

  it("Escape cancels", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on(REGENERATE, apiError(403, "STEP_UP_REQUIRED"));
    renderProvider();
    const result = capture(
      context.request("/session/mfa/recovery-codes", { method: "POST" }),
    );
    await screen.findByRole("dialog", { name: "Confirm it's you" });
    await user.keyboard("{Escape}");
    expect((await result).error).toBeInstanceOf(StepUpCancelledError);
    expect(api.callsTo(REGENERATE)).toHaveLength(1);
  });

  it("a repeated STEP_UP_REQUIRED stops: StepUpFailedError and no loop", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on(
      REGENERATE,
      apiError(403, "STEP_UP_REQUIRED"),
      apiError(403, "STEP_UP_REQUIRED"),
    );
    api.on(STEP_UP, ok(platformSession()));
    renderProvider();
    const result = capture(
      context.request("/session/mfa/recovery-codes", { method: "POST" }),
    );
    await screen.findByRole("dialog", { name: "Confirm it's you" });
    await user.type(screen.getByLabelText(/Authentication code/), "123456");
    await user.click(
      screen.getByRole("button", { name: "Verify and continue" }),
    );
    expect((await result).error).toBeInstanceOf(StepUpFailedError);
    expect(api.callsTo(REGENERATE)).toHaveLength(2);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("a wrong code keeps the dialog open with a field error and clears the code", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on(REGENERATE, apiError(403, "STEP_UP_REQUIRED"));
    api.on(
      STEP_UP,
      apiError(422, "VALIDATION_ERROR", {
        details: [{ field: "code", code: "mfa_code_invalid" }],
      }),
    );
    renderProvider();
    void context
      .request("/session/mfa/recovery-codes", { method: "POST" })
      .catch(() => undefined);
    await screen.findByRole("dialog", { name: "Confirm it's you" });
    const field = screen.getByLabelText(/Authentication code/);
    await user.type(field, "000000");
    await user.click(
      screen.getByRole("button", { name: "Verify and continue" }),
    );
    expect(
      await screen.findByText(
        "That code didn't work. Check your authenticator app and try again.",
      ),
    ).toBeInTheDocument();
    expect(field).toHaveValue("");
    expect(api.callsTo(REGENERATE)).toHaveLength(1);
    expect(screen.queryByText(/SERVER-MESSAGE/)).toBeNull();
  });

  it("429 in the dialog shows the rate-limit Alert", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on(REGENERATE, apiError(403, "STEP_UP_REQUIRED"));
    api.on(
      STEP_UP,
      apiError(429, "RATE_LIMITED", { headers: { "retry-after": "120" } }),
    );
    renderProvider();
    void context
      .request("/session/mfa/recovery-codes", { method: "POST" })
      .catch(() => undefined);
    await screen.findByRole("dialog", { name: "Confirm it's you" });
    await user.type(screen.getByLabelText(/Authentication code/), "123456");
    await user.click(
      screen.getByRole("button", { name: "Verify and continue" }),
    );
    expect(await screen.findByText("Too many attempts")).toBeInTheDocument();
    expect(
      screen.getByText("Try again in about 2 minutes."),
    ).toBeInTheDocument();
  });

  it("401 in the dialog ends the session: navigation, and the action is not performed", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on(REGENERATE, apiError(403, "STEP_UP_REQUIRED"));
    api.on(STEP_UP, apiError(401, "AUTHENTICATION_REQUIRED"));
    api.on("GET /platform/session", apiError(401, "AUTHENTICATION_REQUIRED"));
    renderProvider();
    const result = capture(
      context.request("/session/mfa/recovery-codes", { method: "POST" }),
    );
    await screen.findByRole("dialog", { name: "Confirm it's you" });
    await user.type(screen.getByLabelText(/Authentication code/), "123456");
    await user.click(
      screen.getByRole("button", { name: "Verify and continue" }),
    );
    expect((await result).error).toBeInstanceOf(StepUpCancelledError);
    await waitFor(() =>
      expect(documentNav.assignLocation).toHaveBeenCalledWith(
        "/platform/session-ended?reason=ended&next=%2Fplatform%2Fprofile",
      ),
    );
    expect(api.callsTo(REGENERATE)).toHaveLength(1);
  });

  it("SESSION_REFRESH_REQUIRED in the dialog re-reads and keeps it open; nothing is resent", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on(REGENERATE, apiError(403, "STEP_UP_REQUIRED"));
    api.on(STEP_UP, apiError(403, "SESSION_REFRESH_REQUIRED"));
    api.on(
      "GET /platform/session",
      ok(platformSession({ csrf_token: "fresh" })),
    );
    renderProvider();
    void context
      .request("/session/mfa/recovery-codes", { method: "POST" })
      .catch(() => undefined);
    await screen.findByRole("dialog", { name: "Confirm it's you" });
    await user.type(screen.getByLabelText(/Authentication code/), "123456");
    await user.click(
      screen.getByRole("button", { name: "Verify and continue" }),
    );
    expect(
      await screen.findByText("Your session was refreshed. Try again."),
    ).toBeInTheDocument();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(api.callsTo(STEP_UP)).toHaveLength(1);
    expect(api.callsTo(REGENERATE)).toHaveLength(1);
    expect(screen.getByTestId("probe")).toHaveTextContent("|fresh");
  });

  it("never resends after 5xx or a network error on the original request", async () => {
    const api = installFetch();
    api.on(REGENERATE, apiError(500, "INTERNAL_ERROR"), new TypeError("down"));
    renderProvider();
    await expect(
      context.request("/session/mfa/recovery-codes", { method: "POST" }),
    ).rejects.toMatchObject({ code: "INTERNAL_ERROR" });
    await expect(
      context.request("/session/mfa/recovery-codes", { method: "POST" }),
    ).rejects.toThrow();
    expect(api.callsTo(REGENERATE)).toHaveLength(2);
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
