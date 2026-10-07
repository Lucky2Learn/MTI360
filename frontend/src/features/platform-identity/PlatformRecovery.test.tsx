import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "@/design-system/testing/axe";
import { ForgotPasswordScreen } from "@/features/identity/ForgotPasswordScreen";
import { ResetPasswordScreen } from "@/features/identity/ResetPasswordScreen";
import { SessionEndedScreen } from "@/features/identity/SessionEndedScreen";
import { apiError, installFetch, noContent, ok } from "@/test/fetch-mock";
import { renderScreen } from "@/test/render-screen";

import { PlatformAcceptInvitationScreen } from "./PlatformAcceptInvitationScreen";

vi.setConfig({ testTimeout: 30_000 });

// PAUTH-01 forgot password, PAUTH-02 reset password, PAUTH-03 accept
// invitation and PAUTH-06 session ended (T01-09B UI contract §7): the
// platform API, the platform routes, the fragment-token pattern, and fixed
// copy only.

const documentNav = vi.hoisted(() => ({
  assignLocation: vi.fn<(url: string) => void>(),
  reloadDocument: vi.fn(),
  currentPath: vi.fn(() => "/platform/reset-password"),
  takeFragmentToken: vi.fn<() => string | null>(() => null),
}));
vi.mock("@/lib/session/document", () => documentNav);

const TOKEN = "platform-reset-token-AAAAAAAAAAAAAAAAAAAAAAAAAAAA";
const NEW_PASSWORD = "Mooring-Line-Capstan-42";

beforeEach(() => {
  documentNav.assignLocation.mockReset();
  documentNav.takeFragmentToken.mockReset();
  documentNav.takeFragmentToken.mockReturnValue(null);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("PAUTH-01 platform forgot password", () => {
  it("posts to /platform/auth/password-reset and confirms generically", async () => {
    const api = installFetch();
    api.on("POST /platform/auth/password-reset", noContent());
    const { container } = renderScreen(
      <ForgotPasswordScreen realm="platform" />,
    );
    expect(screen.getByRole("banner")).toHaveTextContent(
      "Platform administration",
    );
    expect(
      screen.getByRole("link", { name: "Back to sign in" }),
    ).toHaveAttribute("href", "/platform/login");
    const user = userEvent.setup({ delay: null });
    await user.type(
      screen.getByRole("textbox", { name: /^Email/ }),
      "meera.iyer@mti360.example",
    );
    await user.click(screen.getByRole("button", { name: "Send reset link" }));
    expect(await screen.findByText("Check your email")).toBeInTheDocument();
    expect(screen.getByText(/If a platform account uses/)).toBeInTheDocument();
    expect(api.calls.map((call) => call.path)).toEqual([
      "/platform/auth/password-reset",
    ]);
    await expectNoA11yViolations(container);
  });
});

describe("PAUTH-02 platform reset password", () => {
  it("takes the token from the fragment, posts it in the body only, and goes to platform sign-in", async () => {
    documentNav.takeFragmentToken.mockReturnValue(TOKEN);
    const api = installFetch();
    api.on("POST /platform/auth/password-reset/confirm", noContent());
    renderScreen(<ResetPasswordScreen realm="platform" />);
    expect(
      await screen.findByText(/Your authenticator app is still required/),
    ).toBeInTheDocument();
    const user = userEvent.setup({ delay: null });
    await user.type(screen.getByLabelText(/^New password/), NEW_PASSWORD);
    await user.type(
      screen.getByLabelText(/^Confirm new password/),
      NEW_PASSWORD,
    );
    await user.click(screen.getByRole("button", { name: "Change password" }));
    await waitFor(() =>
      expect(documentNav.assignLocation).toHaveBeenCalledWith(
        "/platform/login?reason=password-reset",
      ),
    );
    const [call] = api.calls;
    expect(call!.path).toBe("/platform/auth/password-reset/confirm");
    expect(call!.body).toEqual({ token: TOKEN, new_password: NEW_PASSWORD });
    expect(api.calls.every((c) => !c.path.includes(TOKEN))).toBe(true);
    expect(document.body.textContent).not.toContain(TOKEN);
  });

  it("an unusable link (404) offers a new platform link", async () => {
    documentNav.takeFragmentToken.mockReturnValue(TOKEN);
    const api = installFetch();
    api.on(
      "POST /platform/auth/password-reset/confirm",
      apiError(404, "NOT_FOUND"),
    );
    renderScreen(<ResetPasswordScreen realm="platform" />);
    const user = userEvent.setup({ delay: null });
    await user.type(
      await screen.findByLabelText(/^New password/),
      NEW_PASSWORD,
    );
    await user.type(
      screen.getByLabelText(/^Confirm new password/),
      NEW_PASSWORD,
    );
    await user.click(screen.getByRole("button", { name: "Change password" }));
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "This reset link can't be used",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Request a new link" }),
    ).toHaveAttribute("href", "/platform/forgot-password");
  });

  it("a missing token shows the incomplete-link state", async () => {
    installFetch();
    renderScreen(<ResetPasswordScreen realm="platform" />);
    expect(
      await screen.findByRole("heading", {
        name: "This reset link is incomplete",
      }),
    ).toBeInTheDocument();
  });
});

describe("PAUTH-03 platform invitation acceptance", () => {
  const INVITE = "platform-invite-token-BBBBBBBBBBBBBBBBBBBBBBBBBBBB";

  it("previews the masked email only, accepts with token + password, no automatic sign-in", async () => {
    documentNav.takeFragmentToken.mockReturnValue(INVITE);
    const api = installFetch();
    api.on(
      "POST /platform/auth/invitations/preview",
      ok({ email: "m…@mti360.example" }),
    );
    api.on("POST /platform/auth/invitations/accept", noContent());
    const { container } = renderScreen(<PlatformAcceptInvitationScreen />);
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "Join MTI 360 platform administration",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Invitation for m…@mti360.example"),
    ).toBeInTheDocument();
    // No name field: the platform accept takes token and password only.
    expect(screen.queryByLabelText(/name/i)).toBeNull();
    await expectNoA11yViolations(container);

    const user = userEvent.setup({ delay: null });
    await user.type(screen.getByLabelText(/^Create password/), NEW_PASSWORD);
    await user.type(screen.getByLabelText(/^Confirm password/), NEW_PASSWORD);
    await user.click(screen.getByRole("button", { name: "Accept invitation" }));
    await waitFor(() =>
      expect(documentNav.assignLocation).toHaveBeenCalledWith(
        "/platform/login?reason=invitation-accepted",
      ),
    );
    expect(
      api.callsTo("POST /platform/auth/invitations/preview")[0]!.body,
    ).toEqual({ token: INVITE });
    expect(
      api.callsTo("POST /platform/auth/invitations/accept")[0]!.body,
    ).toEqual({
      token: INVITE,
      password: NEW_PASSWORD,
    });
    // Never a session call: accepting does not sign in.
    expect(api.calls.some((call) => call.path.endsWith("/session"))).toBe(
      false,
    );
  });

  it("one message for every unusable invitation (404)", async () => {
    documentNav.takeFragmentToken.mockReturnValue(INVITE);
    const api = installFetch();
    api.on(
      "POST /platform/auth/invitations/preview",
      apiError(404, "NOT_FOUND", { message: "expired" }),
    );
    renderScreen(<PlatformAcceptInvitationScreen />);
    expect(
      await screen.findByRole("heading", {
        name: "This invitation can't be used",
      }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/expired"|SERVER-/)).toBeNull();
  });

  it("a password rejected by the server shows the field rule", async () => {
    documentNav.takeFragmentToken.mockReturnValue(INVITE);
    const api = installFetch();
    api.on(
      "POST /platform/auth/invitations/preview",
      ok({ email: "m…@x.example" }),
    );
    api.on(
      "POST /platform/auth/invitations/accept",
      apiError(422, "VALIDATION_ERROR", {
        details: [{ field: "password", code: "password_too_common" }],
      }),
    );
    renderScreen(<PlatformAcceptInvitationScreen />);
    const user = userEvent.setup({ delay: null });
    await user.type(
      await screen.findByLabelText(/^Create password/),
      NEW_PASSWORD,
    );
    await user.type(screen.getByLabelText(/^Confirm password/), NEW_PASSWORD);
    await user.click(screen.getByRole("button", { name: "Accept invitation" }));
    expect(
      await screen.findByText(
        "This password is too common. Choose a different one.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/^Create password/)).toHaveValue("");
  });

  it("a missing token shows the incomplete-link state without calling the API", async () => {
    const api = installFetch();
    renderScreen(<PlatformAcceptInvitationScreen />);
    expect(
      await screen.findByRole("heading", {
        name: "This invitation link is incomplete",
      }),
    ).toBeInTheDocument();
    expect(api.calls).toHaveLength(0);
  });
});

describe("PAUTH-06 platform session ended", () => {
  it.each([
    ["signed-out", "You've signed out"],
    ["ended", "Your session has ended"],
  ] as const)(
    "%s: platform sign-in with the platform next",
    async (reason, title) => {
      const { container } = renderScreen(
        <SessionEndedScreen
          realm="platform"
          reason={reason}
          next="/platform/users"
        />,
        { theme: "dark" },
      );
      expect(
        screen.getByRole("heading", { level: 1, name: title }),
      ).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute(
        "href",
        "/platform/login?next=%2Fplatform%2Fusers",
      );
      expect(screen.getByRole("banner")).toHaveTextContent(
        "Platform administration",
      );
      await expectNoA11yViolations(container);
    },
  );
});
