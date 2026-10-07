import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StrictMode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "@/design-system/testing/axe";
import { apiError, installFetch, noContent, ok } from "@/test/fetch-mock";
import {
  ENROLMENT,
  pendingPlatformSession,
  platformSession,
  RECOVERY_CODES,
} from "@/test/platform-fixtures";
import { normalizedHtml, renderScreen } from "@/test/render-screen";

import { PlatformLoginScreen } from "./PlatformLoginScreen";

vi.setConfig({ testTimeout: 30_000 });

// PLAT-01 sign-in, PLAT-02 verification, PAUTH-04 enrolment and PAUTH-05
// recovery codes (T01-09B UI contract §6).

const documentNav = vi.hoisted(() => ({
  assignLocation: vi.fn<(url: string) => void>(),
  reloadDocument: vi.fn(),
  currentPath: vi.fn(() => "/platform/login"),
  takeFragmentToken: vi.fn(() => null),
}));
vi.mock("@/lib/session/document", () => documentNav);

const EMAIL = "meera.iyer@mti360.example";
const PASSWORD = "Bosun-Lantern-Harbour-7";

beforeEach(() => {
  documentNav.assignLocation.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

async function signIn(user = userEvent.setup({ delay: null })) {
  await user.type(screen.getByRole("textbox", { name: /^Email/ }), EMAIL);
  await user.type(screen.getByLabelText(/^Password/), PASSWORD);
  await user.click(screen.getByRole("button", { name: "Sign in" }));
  return user;
}

const LOGIN = "POST /platform/auth/login";

describe("PLAT-01 platform sign-in", () => {
  it("renders the T16 frame with the platform context, contract copy and no tenant cross-link", async () => {
    const { container } = renderScreen(
      <PlatformLoginScreen reason={null} next={null} />,
    );
    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Sign in to platform administration",
      }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("banner")).toHaveTextContent(
      "Platform administration",
    );
    expect(
      screen.getByRole("link", { name: "Forgot password?" }),
    ).toHaveAttribute("href", "/platform/forgot-password");
    expect(screen.getByRole("textbox", { name: /^Email/ })).toHaveAttribute(
      "autocomplete",
      "username",
    );
    expect(screen.getByLabelText(/^Password/)).toHaveAttribute(
      "autocomplete",
      "current-password",
    );
    expect(
      screen.getByRole("button", { name: "Show password" }),
    ).toBeInTheDocument();
    // No cross-link to the institute sign-in, no deferred options (D6-4).
    for (const link of screen.getAllByRole("link")) {
      expect(link.getAttribute("href")).not.toBe("/login");
    }
    expect(container.textContent).not.toMatch(
      /remember|trusted device|resend|institute administrator/i,
    );
    await expectNoA11yViolations(container);
  });

  it.each([
    ["signed-out", "You've signed out."],
    [
      "password-reset",
      "Your password has been changed. Sign in with your new password and your authenticator app.",
    ],
    [
      "invitation-accepted",
      "Your password is set. Sign in to set up two-step verification.",
    ],
  ] as const)("shows the %s notice", (reason, text) => {
    renderScreen(<PlatformLoginScreen reason={reason} next={null} />);
    expect(screen.getByText(text)).toBeInTheDocument();
  });

  it("sends the trimmed email and the password to the platform API only", async () => {
    const api = installFetch();
    api.on(LOGIN, ok(pendingPlatformSession("mfa_required")));
    renderScreen(<PlatformLoginScreen reason={null} next={null} />);
    const user = userEvent.setup({ delay: null });
    await user.type(
      screen.getByRole("textbox", { name: /^Email/ }),
      `  ${EMAIL} `,
    );
    await user.type(screen.getByLabelText(/^Password/), PASSWORD);
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    await screen.findByRole("heading", {
      level: 1,
      name: "Enter your authentication code",
    });
    expect(api.calls).toHaveLength(1);
    expect(api.calls[0]!.path).toBe("/platform/auth/login");
    expect(api.calls[0]!.body).toEqual({ email: EMAIL, password: PASSWORD });
  });

  it("renders IDENTICAL DOM for every refused sign-in (no enumeration, no locked/suspended wording)", async () => {
    const outcomes: string[] = [];
    // Unknown account, wrong password, locked and suspended all answer 401.
    for (let attempt = 0; attempt < 3; attempt += 1) {
      const api = installFetch();
      api.on(
        LOGIN,
        apiError(401, "AUTHENTICATION_REQUIRED", {
          message: `SERVER-${attempt}`,
        }),
      );
      const { container, unmount } = renderScreen(
        <PlatformLoginScreen reason={null} next={null} />,
      );
      await signIn();
      await screen.findByText("We couldn't sign you in");
      outcomes.push(normalizedHtml(container));
      expect(container.textContent).not.toMatch(
        /locked|suspended|not found|unknown|SERVER-/i,
      );
      unmount();
    }
    expect(new Set(outcomes).size).toBe(1);
  });

  it("clears the password after a refusal and focuses it", async () => {
    const api = installFetch();
    api.on(LOGIN, apiError(401, "AUTHENTICATION_REQUIRED"));
    renderScreen(<PlatformLoginScreen reason={null} next={null} />);
    await signIn();
    await screen.findByText("We couldn't sign you in");
    expect(screen.getByLabelText(/^Password/)).toHaveValue("");
    expect(screen.getByLabelText(/^Password/)).toHaveFocus();
    expect(screen.getByRole("textbox", { name: /^Email/ })).toHaveValue(EMAIL);
  });

  it.each([
    [
      apiError(429, "RATE_LIMITED", { headers: { "retry-after": "90" } }),
      "Too many attempts",
    ],
    [
      apiError(403, "SESSION_REFRESH_REQUIRED"),
      "Your sign-in page has expired",
    ],
    [apiError(500, "INTERNAL_ERROR"), "Something went wrong on our side"],
    [new TypeError("offline"), "We couldn't reach MTI 360"],
  ])("maps failures to fixed copy (%#)", async (response, text) => {
    const api = installFetch();
    api.on(LOGIN, response);
    renderScreen(<PlatformLoginScreen reason={null} next={null} />);
    await signIn();
    expect(await screen.findByText(new RegExp(text))).toBeInTheDocument();
    expect(screen.queryByText(/SERVER-MESSAGE/)).toBeNull();
  });

  it("422 shows client field errors only, without the server text", async () => {
    const api = installFetch();
    renderScreen(<PlatformLoginScreen reason={null} next={null} />);
    await userEvent
      .setup()
      .click(screen.getByRole("button", { name: "Sign in" }));
    expect(screen.getByText("Enter your email address.")).toBeInTheDocument();
    expect(api.calls).toHaveLength(0);
  });

  it("never reads GET /platform/session to restore a pending state", async () => {
    const api = installFetch();
    api.on(LOGIN, ok(pendingPlatformSession("mfa_required")));
    renderScreen(<PlatformLoginScreen reason={null} next={null} />);
    await signIn();
    await screen.findByRole("heading", {
      name: "Enter your authentication code",
    });
    expect(api.calls.map((call) => call.path)).toEqual([
      "/platform/auth/login",
    ]);
  });

  it("a reload (fresh mount) restarts at the password step (D9B-2)", async () => {
    const api = installFetch();
    api.on(LOGIN, ok(pendingPlatformSession("mfa_required")));
    const { unmount } = renderScreen(
      <PlatformLoginScreen reason={null} next={null} />,
    );
    await signIn();
    await screen.findByRole("heading", {
      name: "Enter your authentication code",
    });
    unmount();
    renderScreen(<PlatformLoginScreen reason={null} next={null} />);
    expect(
      screen.getByRole("heading", {
        name: "Sign in to platform administration",
      }),
    ).toBeInTheDocument();
    expect(api.calls).toHaveLength(1);
  });
});

describe("PLAT-02 two-step verification", () => {
  async function toVerify(next: string | null = null) {
    const api = installFetch();
    api.on(LOGIN, ok(pendingPlatformSession("mfa_required", "pending-csrf")));
    renderScreen(<PlatformLoginScreen reason={null} next={next} />);
    const user = await signIn();
    const heading = await screen.findByRole("heading", {
      level: 1,
      name: "Enter your authentication code",
    });
    return { api, user, heading };
  }

  it("moves focus to the step's h1 and uses one-time-code, numeric, no auto-submit", async () => {
    const { api, user, heading } = await toVerify();
    await waitFor(() => expect(heading).toHaveFocus());
    const field = screen.getByLabelText(/^Authentication code/);
    expect(field).toHaveAttribute("autocomplete", "one-time-code");
    expect(field).toHaveAttribute("inputmode", "numeric");
    await user.type(field, "492817");
    // Six digits typed: nothing is sent until the person submits.
    expect(api.calls).toHaveLength(1);
    expect(screen.getByRole("banner")).toHaveTextContent(
      "Platform administration",
    );
  });

  it("verifies with the pending CSRF token and goes to a valid next", async () => {
    const { api, user } = await toVerify("/platform/users");
    api.on("POST /platform/auth/mfa/verify", ok(platformSession()));
    await user.type(screen.getByLabelText(/^Authentication code/), "492817");
    await user.click(screen.getByRole("button", { name: "Verify" }));
    await waitFor(() =>
      expect(documentNav.assignLocation).toHaveBeenCalledWith(
        "/platform/users",
      ),
    );
    const [verify] = api.callsTo("POST /platform/auth/mfa/verify");
    expect(verify!.body).toEqual({ code: "492817" });
    expect(verify!.headers["x-csrf-token"]).toBe("pending-csrf");
  });

  it("422: field error, the code is cleared, another try is allowed", async () => {
    const { api, user } = await toVerify();
    api.on(
      "POST /platform/auth/mfa/verify",
      apiError(422, "VALIDATION_ERROR", {
        details: [{ field: "code", code: "mfa_code_invalid" }],
      }),
    );
    const field = screen.getByLabelText(/^Authentication code/);
    await user.type(field, "000000");
    await user.click(screen.getByRole("button", { name: "Verify" }));
    expect(
      await screen.findByText(
        "That code didn't work. Check your authenticator app and try again.",
      ),
    ).toBeInTheDocument();
    expect(field).toHaveValue("");
    expect(screen.queryByText(/SERVER-/)).toBeNull();
  });

  it("recovery-code mode posts to /platform/auth/mfa/recovery with autocomplete off", async () => {
    const { api, user } = await toVerify();
    api.on("POST /platform/auth/mfa/recovery", ok(platformSession()));
    await user.click(
      screen.getByRole("button", { name: "Use a recovery code instead" }),
    );
    const field = await screen.findByLabelText(/^Recovery code/);
    expect(field).toHaveAttribute("autocomplete", "off");
    await user.type(field, "abcde-fghij");
    await user.click(screen.getByRole("button", { name: "Verify" }));
    await waitFor(() =>
      expect(documentNav.assignLocation).toHaveBeenCalledWith("/platform"),
    );
    expect(api.callsTo("POST /platform/auth/mfa/recovery")[0]!.body).toEqual({
      recovery_code: "abcde-fghij",
    });
  });

  it("401: back to sign-in with a notice", async () => {
    const { api, user } = await toVerify();
    api.on(
      "POST /platform/auth/mfa/verify",
      apiError(401, "AUTHENTICATION_REQUIRED"),
    );
    await user.type(screen.getByLabelText(/^Authentication code/), "492817");
    await user.click(screen.getByRole("button", { name: "Verify" }));
    expect(await screen.findByText("Sign in again")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        name: "Sign in to platform administration",
      }),
    ).toBeInTheDocument();
  });

  it("429: rate-limit feedback", async () => {
    const { api, user } = await toVerify();
    api.on("POST /platform/auth/mfa/verify", apiError(429, "RATE_LIMITED"));
    await user.type(screen.getByLabelText(/^Authentication code/), "492817");
    await user.click(screen.getByRole("button", { name: "Verify" }));
    expect(await screen.findByText("Too many attempts")).toBeInTheDocument();
  });

  it("'Back to sign in' ends the pending session through the platform API", async () => {
    const { api, user } = await toVerify();
    api.on("POST /platform/auth/logout", noContent());
    await user.click(screen.getByRole("button", { name: "Back to sign in" }));
    await waitFor(() =>
      expect(api.callsTo("POST /platform/auth/logout")).toHaveLength(1),
    );
    expect(api.callsTo("POST /auth/logout")).toHaveLength(0);
  });

  it("passes axe in Light and Dark", async () => {
    for (const theme of ["light", "dark"] as const) {
      const api = installFetch();
      api.on(LOGIN, ok(pendingPlatformSession("mfa_required")));
      const { container, unmount } = renderScreen(
        <PlatformLoginScreen reason={null} next={null} />,
        { theme },
      );
      await signIn();
      await screen.findByRole("heading", {
        name: "Enter your authentication code",
      });
      await expectNoA11yViolations(container);
      unmount();
    }
  });
});

describe("PAUTH-04 enrolment and PAUTH-05 recovery codes", () => {
  async function toIntro(next: string | null = null, strict = false) {
    const api = installFetch();
    api.on(
      LOGIN,
      ok(pendingPlatformSession("mfa_enrolment_required", "pending-csrf")),
    );
    const element = <PlatformLoginScreen reason={null} next={next} />;
    renderScreen(strict ? <StrictMode>{element}</StrictMode> : element);
    const user = await signIn();
    await screen.findByRole("heading", {
      level: 1,
      name: "Set up two-step verification",
    });
    return { api, user };
  }

  async function toKey(next: string | null = null) {
    const context = await toIntro(next);
    context.api.on("POST /platform/auth/mfa/enrolment", ok(ENROLMENT));
    await context.user.click(
      screen.getByRole("button", { name: "Set up authenticator app" }),
    );
    await screen.findByRole("heading", {
      level: 1,
      name: "Add MTI 360 to your authenticator app",
    });
    return context;
  }

  it("never starts enrolment on mount — not even under StrictMode", async () => {
    const { api } = await toIntro(null, true);
    expect(api.callsTo("POST /platform/auth/mfa/enrolment")).toHaveLength(0);
    expect(
      screen.getByText(
        "Finish within 5 minutes of signing in, or you'll need to sign in again.",
      ),
    ).toBeInTheDocument();
  });

  it("starts once on the explicit press (StrictMode) with the pending CSRF token", async () => {
    const { api, user } = await toIntro(null, true);
    api.on("POST /platform/auth/mfa/enrolment", ok(ENROLMENT));
    await user.click(
      screen.getByRole("button", { name: "Set up authenticator app" }),
    );
    await screen.findByRole("heading", {
      name: "Add MTI 360 to your authenticator app",
    });
    const calls = api.callsTo("POST /platform/auth/mfa/enrolment");
    expect(calls).toHaveLength(1);
    expect(calls[0]!.headers["x-csrf-token"]).toBe("pending-csrf");
  });

  it("shows the grouped setup key, the otpauth link, Copy key and the TOTP settings — no QR code", async () => {
    const { user } = await toKey();
    const key = screen.getByLabelText("Setup key");
    expect(key).toHaveTextContent("JBSW Y3DP EHPK 3PXP JBSW Y3DP EHPK 3PXP");
    expect(
      screen.getByRole("link", { name: "Open in authenticator app" }),
    ).toHaveAttribute("href", ENROLMENT.otpauth_uri);
    expect(screen.getByText("Time-based")).toBeInTheDocument();
    expect(screen.getByText("30 seconds")).toBeInTheDocument();
    expect(document.querySelector("img, canvas, svg[data-qr]")).toBeNull();
    expect(document.title).not.toContain(ENROLMENT.secret);

    const writeText = vi.fn(() => Promise.resolve());
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    // Nothing is copied until the button is pressed.
    expect(writeText).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Copy key" }));
    expect(writeText).toHaveBeenCalledWith(ENROLMENT.secret);
    expect(
      await screen.findByText("Copied to the clipboard."),
    ).toBeInTheDocument();
  });

  it("422 keeps the key visible with a field error", async () => {
    const { api, user } = await toKey();
    api.on(
      "POST /platform/auth/mfa/enrolment/confirm",
      apiError(422, "VALIDATION_ERROR", {
        details: [{ field: "code", code: "mfa_code_invalid" }],
      }),
    );
    const field = screen.getByLabelText(/^Code from your authenticator app/);
    await user.type(field, "111111");
    await user.click(
      screen.getByRole("button", { name: "Verify and turn on" }),
    );
    expect(
      await screen.findByText(
        "That code didn't work. Check the entry you just added and try again.",
      ),
    ).toBeInTheDocument();
    expect(field).toHaveValue("");
    expect(screen.getByLabelText("Setup key")).toBeInTheDocument();
  });

  it("401 restarts with the enrolment-ended message", async () => {
    const { api, user } = await toKey();
    api.on(
      "POST /platform/auth/mfa/enrolment/confirm",
      apiError(401, "AUTHENTICATION_REQUIRED"),
    );
    await user.type(
      screen.getByLabelText(/^Code from your authenticator app/),
      "111111",
    );
    await user.click(
      screen.getByRole("button", { name: "Verify and turn on" }),
    );
    expect(
      await screen.findByText("Set-up ended. Sign in again."),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Remove the MTI 360 entry you added/),
    ).toBeInTheDocument();
    expect(screen.queryByText(/JBSW/)).toBeNull();
  });

  it("confirms, drops the key, shows the 10 codes once and requires the acknowledgement", async () => {
    const { api, user } = await toKey("/platform/tenants");
    api.on(
      "POST /platform/auth/mfa/enrolment/confirm",
      ok({ recovery_codes: RECOVERY_CODES, session: platformSession() }),
    );
    await user.type(
      screen.getByLabelText(/^Code from your authenticator app/),
      "123456",
    );
    await user.click(
      screen.getByRole("button", { name: "Verify and turn on" }),
    );
    const heading = await screen.findByRole("heading", {
      level: 1,
      name: "Save your recovery codes",
    });
    await waitFor(() => expect(heading).toHaveFocus());
    expect(
      api.callsTo("POST /platform/auth/mfa/enrolment/confirm")[0]!.body,
    ).toEqual({ code: "123456" });
    // The key and the URI are gone.
    expect(document.body.textContent).not.toContain("JBSW");
    expect(document.querySelector(`a[href^="otpauth:"]`)).toBeNull();

    const list = screen.getByRole("list", { name: "Recovery codes" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(10);
    expect(list).toHaveTextContent("abcde-fghij");
    expect(screen.getByText(/can't be retrieved later/)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /download|print/i }),
    ).toBeNull();

    // Continue is enabled; an unchecked box is a validation error.
    const continueButton = screen.getByRole("button", { name: "Continue" });
    expect(continueButton).toBeEnabled();
    await user.click(continueButton);
    expect(
      await screen.findByText("Confirm that you've saved your recovery codes."),
    ).toBeInTheDocument();
    expect(documentNav.assignLocation).not.toHaveBeenCalled();
    expect(
      screen.getByRole("checkbox", { name: "I've saved my recovery codes" }),
    ).toHaveFocus();

    await user.click(
      screen.getByRole("checkbox", { name: "I've saved my recovery codes" }),
    );
    await user.click(continueButton);
    expect(documentNav.assignLocation).toHaveBeenCalledWith(
      "/platform/tenants",
    );
    // The codes are dropped from the page before the navigation completes.
    await waitFor(() =>
      expect(document.body.textContent).not.toContain("abcde-fghij"),
    );
  });

  it("guards accidental navigation while the codes are shown, and releases it on Continue", async () => {
    const { api, user } = await toKey();
    api.on(
      "POST /platform/auth/mfa/enrolment/confirm",
      ok({ recovery_codes: RECOVERY_CODES, session: platformSession() }),
    );
    await user.type(
      screen.getByLabelText(/^Code from your authenticator app/),
      "123456",
    );
    await user.click(
      screen.getByRole("button", { name: "Verify and turn on" }),
    );
    await screen.findByRole("heading", { name: "Save your recovery codes" });

    const guarded = new Event("beforeunload", { cancelable: true });
    act(() => {
      window.dispatchEvent(guarded);
    });
    expect(guarded.defaultPrevented).toBe(true);

    await user.click(
      screen.getByRole("checkbox", { name: "I've saved my recovery codes" }),
    );
    await user.click(screen.getByRole("button", { name: "Continue" }));
    const released = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(released);
    expect(released.defaultPrevented).toBe(false);
  });

  it("409 (already set up elsewhere) returns to sign-in", async () => {
    const { api, user } = await toIntro();
    api.on("POST /platform/auth/mfa/enrolment", apiError(409, "CONFLICT"));
    await user.click(
      screen.getByRole("button", { name: "Set up authenticator app" }),
    );
    expect(await screen.findByText("Sign in again")).toBeInTheDocument();
  });

  it("passes axe on the key and the codes steps in Light and Dark", async () => {
    for (const theme of ["light", "dark"] as const) {
      const api = installFetch();
      api.on(LOGIN, ok(pendingPlatformSession("mfa_enrolment_required")));
      api.on("POST /platform/auth/mfa/enrolment", ok(ENROLMENT));
      api.on(
        "POST /platform/auth/mfa/enrolment/confirm",
        ok({ recovery_codes: RECOVERY_CODES, session: platformSession() }),
      );
      const { container, unmount } = renderScreen(
        <PlatformLoginScreen reason={null} next={null} />,
        { theme },
      );
      const user = await signIn();
      await user.click(
        await screen.findByRole("button", { name: "Set up authenticator app" }),
      );
      await screen.findByRole("heading", {
        name: "Add MTI 360 to your authenticator app",
      });
      await expectNoA11yViolations(container);
      await user.type(
        screen.getByLabelText(/^Code from your authenticator app/),
        "123456",
      );
      await user.click(
        screen.getByRole("button", { name: "Verify and turn on" }),
      );
      await screen.findByRole("heading", { name: "Save your recovery codes" });
      await expectNoA11yViolations(container);
      unmount();
    }
  });
});
