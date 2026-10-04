import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "@/design-system/testing/axe";
import { apiError, installFetch, jsonResponse } from "@/test/fetch-mock";
import { normalizedHtml, renderScreen } from "@/test/render-screen";

import { ForgotPasswordScreen } from "./ForgotPasswordScreen";
import { ResetPasswordScreen } from "./ResetPasswordScreen";

// Whole flows typed key by key through React Aria: allow for a loaded CI host.
vi.setConfig({ testTimeout: 20_000 });

// AUTH-02 Forgot password and AUTH-03 Reset password (T01-04 UI contract
// §8.2, §8.3): generic outcomes, the token only from the fragment, removed
// from the address bar, sent only in the POST body, never stored or shown.

const navigation = vi.hoisted(() => ({
  assignLocation: vi.fn<(url: string) => void>(),
  reloadDocument: vi.fn(),
}));
vi.mock("@/lib/session/document", async (original) => ({
  ...(await original<typeof import("@/lib/session/document")>()),
  ...navigation,
}));

const TOKEN = "fake-reset-token-xxxxxxxxxxxxxxxxxxxxxxxxxx";
const NEW_PASSWORD = "fake-new-password-xxxx";

beforeEach(() => {
  navigation.assignLocation.mockReset();
  window.history.replaceState(null, "", "/");
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("AUTH-02 forgot password", () => {
  async function request(email: string) {
    const user = userEvent.setup({ delay: null });
    await user.type(screen.getByRole("textbox", { name: /^Email/ }), email);
    await user.click(screen.getByRole("button", { name: "Send reset link" }));
    return user;
  }

  it("shows the same confirmation for an existing and an unknown email", async () => {
    const api = installFetch();
    api.on(
      "POST /auth/password-reset",
      jsonResponse(202, null),
      jsonResponse(202, null),
    );
    const first = renderScreen(<ForgotPasswordScreen />);
    await request("ananya.rao@coastal-maritime.example");
    await screen.findByText("Check your email");
    const known = normalizedHtml(first.container).replace(
      "ananya.rao@coastal-maritime.example",
      "EMAIL",
    );
    first.unmount();

    const second = renderScreen(<ForgotPasswordScreen />);
    await request("nobody@unknown-academy.example");
    await screen.findByText("Check your email");
    const unknown = normalizedHtml(second.container).replace(
      "nobody@unknown-academy.example",
      "EMAIL",
    );
    expect(unknown).toBe(known);
    expect(api.calls.map((call) => call.body)).toEqual([
      { email: "ananya.rao@coastal-maritime.example" },
      { email: "nobody@unknown-academy.example" },
    ]);
  });

  it("replaces the form, echoes the typed email as text and moves focus there", async () => {
    const api = installFetch();
    api.on("POST /auth/password-reset", jsonResponse(202, null));
    renderScreen(<ForgotPasswordScreen />);
    const user = await request("deck.cadet@harbour.example");
    const status = await screen.findByRole("status");
    expect(status).toHaveTextContent(
      "If an account uses deck.cadet@harbour.example, we've sent a link to reset the password. The link expires in 30 minutes.",
    );
    expect(status.parentElement).toHaveFocus();
    expect(screen.queryByRole("textbox", { name: /^Email/ })).toBeNull();
    expect(window.location.search).toBe("");

    await user.click(
      screen.getByRole("button", { name: "Use a different email" }),
    );
    expect(screen.getByRole("textbox", { name: /^Email/ })).toHaveValue("");
  });

  it("rate limited: generic warning, the form stays", async () => {
    const api = installFetch();
    api.on("POST /auth/password-reset", apiError(429, "RATE_LIMITED"));
    renderScreen(<ForgotPasswordScreen />);
    await request("ananya.rao@coastal-maritime.example");
    expect(
      await screen.findByText(
        "Too many requests. Wait a few minutes before trying again.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /^Email/ })).toBeInTheDocument();
  });

  it("passes axe in Light and Dark", async () => {
    const { container } = renderScreen(<ForgotPasswordScreen />, {
      theme: "dark",
    });
    await expectNoA11yViolations(container);
  });
});

describe("AUTH-03 reset password", () => {
  const openLink = (fragment: string) =>
    window.history.replaceState(null, "", `/reset-password${fragment}`);

  async function choose(password: string, confirmation = password) {
    const user = userEvent.setup({ delay: null });
    await user.type(screen.getByLabelText(/^New password/), password);
    await user.type(
      screen.getByLabelText(/^Confirm new password/),
      confirmation,
    );
    await user.click(screen.getByRole("button", { name: "Change password" }));
    return user;
  }

  it("reads the token from the fragment and removes it from the address bar at once", async () => {
    const replaceState = vi.spyOn(window.history, "replaceState");
    openLink(`#token=${TOKEN}`);
    renderScreen(<ResetPasswordScreen />);
    await screen.findByRole("heading", {
      level: 1,
      name: "Choose a new password",
    });
    expect(window.location.hash).toBe("");
    expect(window.location.href).not.toContain(TOKEN);
    expect(replaceState).toHaveBeenLastCalledWith(null, "", "/reset-password");
    expect(document.body.innerHTML).not.toContain(TOKEN);
    expect(document.title).not.toContain(TOKEN);
  });

  it("sends the token only in the POST body and goes to sign-in on success", async () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    const api = installFetch();
    api.on("POST /auth/password-reset/confirm", jsonResponse(204, null));
    openLink(`#token=${TOKEN}`);
    renderScreen(<ResetPasswordScreen />);
    await screen.findByLabelText(/^New password/);
    await choose(NEW_PASSWORD);
    await waitFor(() =>
      expect(navigation.assignLocation).toHaveBeenCalledWith(
        "/login?reason=password-reset",
      ),
    );
    const [call] = api.calls;
    expect(call!.body).toEqual({ token: TOKEN, new_password: NEW_PASSWORD });
    expect(api.fetchMock.mock.calls[0]![0]).toBe(
      "/api/v1/auth/password-reset/confirm",
    );
    expect(JSON.stringify(call!.headers)).not.toContain(TOKEN);
    expect(setItem).not.toHaveBeenCalled();
  });

  it("without a token shows 'incomplete' and sends nothing", async () => {
    const api = installFetch();
    openLink("");
    renderScreen(<ResetPasswordScreen />);
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "This reset link is incomplete",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Request a new link" }),
    ).toHaveAttribute("href", "/forgot-password");
    expect(api.fetchMock).not.toHaveBeenCalled();
  });

  it("ignores a token in the query string", async () => {
    openLink(`?token=${TOKEN}`);
    renderScreen(<ResetPasswordScreen />);
    expect(
      await screen.findByText("This reset link is incomplete"),
    ).toBeInTheDocument();
  });

  it.each([
    ["invalid, expired or used (404)", apiError(404, "NOT_FOUND")],
    [
      "malformed (422 on token)",
      apiError(422, "VALIDATION_ERROR", {
        details: [{ field: "token", code: "string_pattern_mismatch" }],
      }),
    ],
  ])(
    "%s: one 'can't be used' state with focus on its title",
    async (_, response) => {
      const api = installFetch();
      api.on("POST /auth/password-reset/confirm", response);
      openLink(`#token=${TOKEN}`);
      renderScreen(<ResetPasswordScreen />);
      await screen.findByLabelText(/^New password/);
      await choose(NEW_PASSWORD);
      const title = await screen.findByRole("heading", {
        level: 1,
        name: "This reset link can't be used",
      });
      expect(title).toHaveFocus();
      expect(
        screen.getByText(
          "It may have expired or already been used. Reset links work once and expire after 30 minutes.",
        ),
      ).toBeInTheDocument();
    },
  );

  it("a common password: field error, both fields cleared, focus on New password", async () => {
    const api = installFetch();
    api.on(
      "POST /auth/password-reset/confirm",
      apiError(422, "VALIDATION_ERROR", {
        details: [{ field: "new_password", code: "password_too_common" }],
      }),
    );
    openLink(`#token=${TOKEN}`);
    renderScreen(<ResetPasswordScreen />);
    await screen.findByLabelText(/^New password/);
    await choose("passwordpassword");
    expect(
      await screen.findByText(
        "This password is too common. Choose a different one.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/^New password/)).toHaveValue("");
    expect(screen.getByLabelText(/^Confirm new password/)).toHaveValue("");
    expect(screen.getByLabelText(/^New password/)).toHaveFocus();
  });

  it("validates length and confirmation on the client first", async () => {
    const api = installFetch();
    openLink(`#token=${TOKEN}`);
    renderScreen(<ResetPasswordScreen />);
    await screen.findByLabelText(/^New password/);
    await choose("short", "different");
    expect(
      await screen.findByText("Use at least 12 characters."),
    ).toBeInTheDocument();
    expect(screen.getByText("The passwords don't match.")).toBeInTheDocument();
    expect(api.fetchMock).not.toHaveBeenCalled();
  });

  it("links the password requirements to the new password field", async () => {
    openLink(`#token=${TOKEN}`);
    const { container } = renderScreen(<ResetPasswordScreen />);
    const field = await screen.findByLabelText(/^New password/);
    const described = field.getAttribute("aria-describedby") ?? "";
    const list = screen.getByText("Use 12 to 128 characters.").closest("ul")!;
    expect(described.split(" ")).toContain(list.id);
    await expectNoA11yViolations(container);
    document.documentElement.dataset.theme = "dark";
    await expectNoA11yViolations(container);
  });
});
