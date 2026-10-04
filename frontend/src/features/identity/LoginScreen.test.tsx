import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "@/design-system/testing/axe";
import { apiError, installFetch, noContent, ok } from "@/test/fetch-mock";
import { normalizedHtml, renderScreen } from "@/test/render-screen";
import { readySession, sessionIn } from "@/test/session-fixtures";

import { LoginScreen } from "./LoginScreen";

// Whole flows typed key by key through React Aria: allow for a loaded CI host.
vi.setConfig({ testTimeout: 20_000 });

// AUTH-01 Sign in and the tenant MFA step (T01-04 UI contract §8.1; T01-09A).

const documentNav = vi.hoisted(() => ({
  assignLocation: vi.fn<(url: string) => void>(),
  reloadDocument: vi.fn(),
  currentPath: vi.fn(() => "/login"),
  takeFragmentToken: vi.fn(() => null),
}));
vi.mock("@/lib/session/document", () => documentNav);

const EMAIL = "ananya.rao@coastal-maritime.example";
const PASSWORD = "Sextant-Bearing-2026";

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

describe("AUTH-01 sign in", () => {
  it("renders the T16 frame with the contract copy and no autofocus", async () => {
    const { container } = renderScreen(
      <LoginScreen reason={null} next={null} />,
    );
    expect(
      screen.getByRole("heading", { level: 1, name: "Sign in to MTI 360" }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(screen.getByRole("contentinfo")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Forgot password?" }),
    ).toHaveAttribute("href", "/forgot-password");
    const email = screen.getByRole("textbox", { name: /^Email/ });
    expect(email).toHaveAttribute("autocomplete", "username");
    expect(email).toHaveAttribute("autocapitalize", "none");
    expect(screen.getByLabelText(/^Password/)).toHaveAttribute(
      "autocomplete",
      "current-password",
    );
    expect(document.body).toHaveFocus();
    expect(container.textContent).not.toMatch(/tenant/i);
    await expectNoA11yViolations(container);
  });

  it.each([
    ["signed-out", "You've signed out."],
    [
      "password-reset",
      "Your password has been changed. Sign in with your new password.",
    ],
    ["invitation-accepted", "Invitation accepted. Sign in to continue."],
  ] as const)("shows the %s notice", (reason, text) => {
    renderScreen(<LoginScreen reason={reason} next={null} />);
    expect(screen.getByRole("status")).toHaveTextContent(text);
  });

  it("sends the trimmed email and the password in the POST body only", async () => {
    const api = installFetch();
    api.on("POST /auth/login", ok(readySession()));
    renderScreen(<LoginScreen reason={null} next={null} />);
    const user = userEvent.setup({ delay: null });
    await user.type(
      screen.getByRole("textbox", { name: /^Email/ }),
      `  ${EMAIL} `,
    );
    await user.type(screen.getByLabelText(/^Password/), PASSWORD);
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(documentNav.assignLocation).toHaveBeenCalled());
    expect(api.calls[0]).toMatchObject({
      method: "POST",
      path: "/auth/login",
      body: { email: EMAIL, password: PASSWORD },
    });
    expect(api.fetchMock.mock.calls[0]![0]).toBe("/api/v1/auth/login");
  });

  it.each([
    ["ready", "/app/administration/users", "/app/administration/users"],
    ["ready", null, "/app"],
    [
      "institute_selection_required",
      "/app/administration/users",
      "/select-institute?next=%2Fapp%2Fadministration%2Fusers",
    ],
    ["campus_selection_required", null, "/select-campus"],
  ] as const)(
    "after %s (next=%s) goes to %s with a full document navigation",
    async (status, next, destination) => {
      const api = installFetch();
      api.on("POST /auth/login", ok(sessionIn(status)));
      renderScreen(<LoginScreen reason={null} next={next} />);
      await signIn();
      await waitFor(() =>
        expect(documentNav.assignLocation).toHaveBeenCalledWith(destination),
      );
    },
  );

  it("renders IDENTICAL DOM for every refused sign-in (no account enumeration)", async () => {
    // Unknown email, wrong password, locked account, disabled user and no
    // usable institute all reach the browser as the same 401; only the
    // request ID and the (never shown) server text differ.
    const api = installFetch();
    api.on(
      "POST /auth/login",
      apiError(401, "AUTHENTICATION_REQUIRED", {
        requestId: "req-unknown-email",
      }),
      apiError(401, "AUTHENTICATION_REQUIRED", {
        requestId: "req-wrong-password",
        message: "Invalid credentials",
      }),
      apiError(401, "AUTHENTICATION_REQUIRED", {
        requestId: "req-locked",
        message: "Account locked",
      }),
      apiError(401, "AUTHENTICATION_REQUIRED", {
        requestId: "req-no-institute",
        message: "No membership",
      }),
    );
    const { container } = renderScreen(
      <LoginScreen reason={null} next={null} />,
    );
    const user = userEvent.setup({ delay: null });
    await user.type(screen.getByRole("textbox", { name: /^Email/ }), EMAIL);
    const snapshots: string[] = [];
    for (let attempt = 0; attempt < 4; attempt += 1) {
      await user.type(screen.getByLabelText(/^Password/), PASSWORD);
      await user.click(screen.getByRole("button", { name: "Sign in" }));
      await screen.findByRole("alert");
      snapshots.push(normalizedHtml(container));
    }
    expect(new Set(snapshots).size).toBe(1);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("We couldn't sign you in");
    expect(alert).toHaveTextContent(
      "Check your email and password and try again. If the problem continues, contact your institute administrator.",
    );
    expect(container.textContent).not.toMatch(
      /req-|Invalid credentials|locked|membership|SERVER-MESSAGE|401/i,
    );
  });

  it("after a refusal clears the password, keeps the email and focuses the password", async () => {
    const api = installFetch();
    api.on("POST /auth/login", apiError(401, "AUTHENTICATION_REQUIRED"));
    renderScreen(<LoginScreen reason={null} next={null} />);
    await signIn();
    await screen.findByRole("alert");
    const password = screen.getByLabelText(/^Password/);
    expect(password).toHaveValue("");
    expect(password).toHaveFocus();
    expect(screen.getByRole("textbox", { name: /^Email/ })).toHaveValue(EMAIL);
  });

  it("rate limited: warning with a rounded retry time, button stays enabled", async () => {
    const api = installFetch();
    api.on(
      "POST /auth/login",
      apiError(429, "RATE_LIMITED", { headers: { "retry-after": "170" } }),
    );
    renderScreen(<LoginScreen reason={null} next={null} />);
    await signIn();
    const status = await screen.findByText("Too many attempts");
    expect(status.closest("[role=status]")).toHaveTextContent(
      "Try again in about 3 minutes.",
    );
    expect(screen.getByRole("button", { name: "Sign in" })).toBeEnabled();
  });

  it("security check failure: 'Reload page' recovery", async () => {
    const api = installFetch();
    api.on("POST /auth/login", apiError(403, "SESSION_REFRESH_REQUIRED"));
    renderScreen(<LoginScreen reason={null} next={null} />);
    const user = await signIn();
    await screen.findByText(
      "Your sign-in page has expired. Reload the page and try again.",
    );
    await user.click(screen.getByRole("button", { name: "Reload page" }));
    expect(documentNav.reloadDocument).toHaveBeenCalled();
  });

  it.each([
    [
      new TypeError("offline"),
      "We couldn't reach MTI 360. Check your connection and try again.",
    ],
    [
      apiError(500, "INTERNAL_ERROR", {
        message: "Traceback: KeyError 'user'",
      }),
      "Something went wrong on our side. Try again in a moment.",
    ],
  ])("network and server failures use fixed copy", async (response, copy) => {
    const api = installFetch();
    api.on("POST /auth/login", response);
    const { container } = renderScreen(
      <LoginScreen reason={null} next={null} />,
    );
    await signIn();
    expect(await screen.findByRole("alert")).toHaveTextContent(copy);
    expect(container.textContent).not.toMatch(/Traceback|KeyError|offline/);
  });

  it("blocks duplicate submits while pending", async () => {
    const api = installFetch();
    let release!: () => void;
    api.on("POST /auth/login", () => ok(readySession()));
    api.fetchMock.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          release = () => resolve(ok(readySession()));
        }),
    );
    renderScreen(<LoginScreen reason={null} next={null} />);
    const user = await signIn();
    const pending = screen.getByRole("button", { name: /Signing in/ });
    await user.click(pending);
    expect(api.fetchMock).toHaveBeenCalledTimes(1);
    release();
    await waitFor(() => expect(documentNav.assignLocation).toHaveBeenCalled());
  });

  it("shows field errors without contacting the API", async () => {
    const api = installFetch();
    renderScreen(<LoginScreen reason={null} next={null} />);
    const user = userEvent.setup({ delay: null });
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(
      await screen.findByText("Enter your email address."),
    ).toBeInTheDocument();
    expect(screen.getByText("Enter your password.")).toBeInTheDocument();
    expect(api.fetchMock).not.toHaveBeenCalled();
  });

  it("passes axe in Dark", async () => {
    const { container } = renderScreen(
      <LoginScreen reason="signed-out" next={null} />,
      {
        theme: "dark",
      },
    );
    await expectNoA11yViolations(container);
  });
});

describe("tenant MFA verify and recovery", () => {
  async function reachMfa() {
    const api = installFetch();
    api.on(
      "POST /auth/login",
      ok(sessionIn("mfa_required", { csrf_token: "pending-csrf" })),
    );
    const { container } = renderScreen(
      <LoginScreen reason={null} next="/app/administration/roles" />,
    );
    const user = await signIn();
    await screen.findByRole("heading", {
      level: 1,
      name: "Enter your authentication code",
    });
    return { api, user, container };
  }

  it("asks for the authenticator code after mfa_required", async () => {
    const { api } = await reachMfa();
    const code = screen.getByRole("textbox", { name: /Authentication code/ });
    expect(code).toHaveAttribute("autocomplete", "one-time-code");
    expect(code).toHaveAttribute("inputmode", "numeric");
    expect(api.calls).toHaveLength(1);
    expect(documentNav.assignLocation).not.toHaveBeenCalled();
  });

  it("verifies the TOTP code with the pending session's CSRF token and continues", async () => {
    const { api, user } = await reachMfa();
    api.on("POST /auth/mfa/verify", ok(readySession()));
    await user.type(
      screen.getByRole("textbox", { name: /Authentication code/ }),
      "492 817",
    );
    await user.click(screen.getByRole("button", { name: "Verify" }));
    await waitFor(() =>
      expect(documentNav.assignLocation).toHaveBeenCalledWith(
        "/app/administration/roles",
      ),
    );
    const [verify] = api.callsTo("POST /auth/mfa/verify");
    expect(verify!.body).toEqual({ code: "492 817" });
    expect(verify!.headers["x-csrf-token"]).toBe("pending-csrf");
  });

  it("an invalid code shows the field error, clears the field and allows another try", async () => {
    const { api, user } = await reachMfa();
    api.on(
      "POST /auth/mfa/verify",
      apiError(422, "VALIDATION_ERROR", {
        details: [{ field: "code", code: "mfa_code_invalid" }],
      }),
    );
    const code = screen.getByRole("textbox", { name: /Authentication code/ });
    await user.type(code, "000000");
    await user.click(screen.getByRole("button", { name: "Verify" }));
    expect(
      await screen.findByText(
        "That code didn't work. Check your authenticator app and try again.",
      ),
    ).toBeInTheDocument();
    expect(code).toHaveValue("");
    expect(code).toHaveFocus();
    expect(code).toHaveAttribute("aria-invalid", "true");
  });

  it("uses a recovery code through POST /auth/mfa/recovery", async () => {
    const { api, user } = await reachMfa();
    api.on(
      "POST /auth/mfa/recovery",
      ok(sessionIn("institute_selection_required")),
    );
    await user.click(
      screen.getByRole("button", { name: "Use a recovery code instead" }),
    );
    expect(
      screen.getByRole("heading", { level: 1, name: "Enter a recovery code" }),
    ).toBeInTheDocument();
    await user.type(
      screen.getByRole("textbox", { name: /Recovery code/ }),
      "abcde-fgh23",
    );
    await user.click(screen.getByRole("button", { name: "Verify" }));
    await waitFor(() =>
      expect(documentNav.assignLocation).toHaveBeenCalledWith(
        "/select-institute?next=%2Fapp%2Fadministration%2Froles",
      ),
    );
    const [recovery] = api.callsTo("POST /auth/mfa/recovery");
    expect(recovery!.body).toEqual({ recovery_code: "abcde-fgh23" });
    expect(recovery!.headers["x-csrf-token"]).toBe("pending-csrf");
  });

  it("an ended verification step returns to sign-in with a notice", async () => {
    const { api, user } = await reachMfa();
    api.on("POST /auth/mfa/verify", apiError(401, "AUTHENTICATION_REQUIRED"));
    await user.type(
      screen.getByRole("textbox", { name: /Authentication code/ }),
      "123456",
    );
    await user.click(screen.getByRole("button", { name: "Verify" }));
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "Sign in to MTI 360",
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Sign in again");
    // The password was not kept for the second attempt.
    expect(screen.getByLabelText(/^Password/)).toHaveValue("");
  });

  it("'Back to sign in' ends the pending session", async () => {
    const { api, user } = await reachMfa();
    api.on("POST /auth/logout", noContent());
    await user.click(screen.getByRole("button", { name: "Back to sign in" }));
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "Sign in to MTI 360",
      }),
    ).toBeInTheDocument();
    expect(api.callsTo("POST /auth/logout")).toHaveLength(1);
  });

  it("offers no trusted device, remember-device or resend option", async () => {
    await reachMfa();
    const main = screen.getByRole("main");
    expect(
      within(main).queryByText(/remember|trust|resend|sms|email me/i),
    ).toBeNull();
    expect(within(main).queryByRole("checkbox")).toBeNull();
  });

  it("passes axe in Light and Dark", async () => {
    const { container } = await reachMfa();
    await expectNoA11yViolations(container);
    document.documentElement.dataset.theme = "dark";
    await expectNoA11yViolations(container);
  });
});
