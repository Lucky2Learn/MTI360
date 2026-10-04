import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "@/design-system/testing/axe";
import {
  apiError,
  inputUrl,
  installFetch,
  noContent,
  ok,
} from "@/test/fetch-mock";
import { renderScreen } from "@/test/render-screen";
import { readySession } from "@/test/session-fixtures";

import { AcceptInvitationScreen } from "./AcceptInvitationScreen";

// Whole flows typed key by key through React Aria: allow for a loaded CI host.
vi.setConfig({ testTimeout: 20_000 });

// AUTH-06 Accept invitation (T01-04 UI contract §8.4; D19).

const navigation = vi.hoisted(() => ({
  assignLocation: vi.fn<(url: string) => void>(),
  reloadDocument: vi.fn(),
}));
vi.mock("@/lib/session/document", async (original) => ({
  ...(await original<typeof import("@/lib/session/document")>()),
  ...navigation,
}));

const TOKEN = "fake-invitation-token-xxxxxxxxxxxxxxxxxxxxx";
const PREVIEW_NEW = {
  institute_name: "Harbour Nautical Academy",
  email_masked: "d***t@harbour.example",
  account: "new",
};
const PREVIEW_EXISTING = { ...PREVIEW_NEW, account: "existing" };

function open(fragment = `#token=${TOKEN}`) {
  window.history.replaceState(null, "", `/accept-invitation${fragment}`);
  return renderScreen(<AcceptInvitationScreen />);
}

function scripted(
  preview: unknown,
  session: Response = apiError(401, "AUTHENTICATION_REQUIRED"),
) {
  const api = installFetch();
  api.on("POST /auth/invitations/preview", ok(preview));
  api.on("GET /session", session);
  return api;
}

beforeEach(() => {
  navigation.assignLocation.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.replaceState(null, "", "/");
});

describe("token handling", () => {
  it("reads the token from the fragment, removes it and previews once in a POST body", async () => {
    const api = scripted(PREVIEW_NEW);
    open();
    await screen.findByRole("heading", {
      level: 1,
      name: "Join Harbour Nautical Academy on MTI 360",
    });
    expect(window.location.hash).toBe("");
    expect(window.location.href).not.toContain(TOKEN);
    expect(document.body.innerHTML).not.toContain(TOKEN);
    const previews = api.callsTo("POST /auth/invitations/preview");
    expect(previews).toHaveLength(1);
    expect(previews[0]!.body).toEqual({ token: TOKEN });
    expect(
      api.fetchMock.mock.calls.every(([url]) => !inputUrl(url).includes(TOKEN)),
    ).toBe(true);
  });

  it("without a token: 'incomplete', and no request is sent", async () => {
    const api = installFetch();
    open("");
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "This invitation link is incomplete",
      }),
    ).toBeInTheDocument();
    expect(api.fetchMock).not.toHaveBeenCalled();
  });

  it("never stores the token", async () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    scripted(PREVIEW_NEW);
    open();
    await screen.findByLabelText(/^Your name/);
    expect(setItem).not.toHaveBeenCalled();
  });
});

describe("preview", () => {
  it("shows the loading state with the generic title first", async () => {
    scripted(PREVIEW_NEW);
    open();
    expect(
      screen.getByRole("heading", { level: 1, name: "Accept your invitation" }),
    ).toBeInTheDocument();
    await screen.findByLabelText(/^Your name/);
  });

  it("new account: name and password fields, masked email exactly as returned", async () => {
    scripted(PREVIEW_NEW);
    const { container } = open();
    expect(
      await screen.findByText("Invitation for d***t@harbour.example"),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/^Your name/)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Create password/)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Confirm password/)).toBeInTheDocument();
    await expectNoA11yViolations(container);
  });

  it("existing account: NO password or name field", async () => {
    scripted(PREVIEW_EXISTING);
    const { container } = open();
    await screen.findByRole("button", { name: "Accept invitation" });
    expect(container.querySelector("input[type=password]")).toBeNull();
    expect(screen.queryByLabelText(/name/i)).toBeNull();
    expect(container.textContent).not.toMatch(/reset|change your password/i);
  });

  it.each([
    [
      "unknown, expired, withdrawn or accepted (404)",
      apiError(404, "NOT_FOUND"),
    ],
    [
      "malformed (422 on token)",
      apiError(422, "VALIDATION_ERROR", {
        details: [{ field: "token", code: "string_pattern_mismatch" }],
      }),
    ],
  ])("%s → one 'can't be used' message", async (_, response) => {
    const api = installFetch();
    api.on("POST /auth/invitations/preview", response);
    api.on("GET /session", apiError(401, "AUTHENTICATION_REQUIRED"));
    open();
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "This invitation can't be used",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "It may have expired, been withdrawn or already been accepted. Ask your institute administrator to send a new invitation.",
      ),
    ).toBeInTheDocument();
  });

  it("network failure: 'Try again' repeats the preview with the in-memory token", async () => {
    const api = installFetch();
    api.on(
      "POST /auth/invitations/preview",
      new TypeError("offline"),
      ok(PREVIEW_NEW),
    );
    api.on("GET /session", apiError(401, "AUTHENTICATION_REQUIRED"));
    open();
    const user = userEvent.setup({ delay: null });
    await user.click(await screen.findByRole("button", { name: "Try again" }));
    await screen.findByLabelText(/^Your name/);
    const previews = api.callsTo("POST /auth/invitations/preview");
    expect(previews.map((call) => call.body)).toEqual([
      { token: TOKEN },
      { token: TOKEN },
    ]);
  });

  it("rate limited on the preview: warning and no form", async () => {
    const api = installFetch();
    api.on("POST /auth/invitations/preview", apiError(429, "RATE_LIMITED"));
    api.on("GET /session", apiError(401, "AUTHENTICATION_REQUIRED"));
    open();
    expect(
      await screen.findByText(
        "Too many requests. Wait a few minutes, then reload this page.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).toBeNull();
  });
});

describe("accept", () => {
  async function fillNewAccount() {
    const user = userEvent.setup({ delay: null });
    await user.type(
      await screen.findByLabelText(/^Your name/),
      "  Deck Cadet Rao ",
    );
    await user.type(
      screen.getByLabelText(/^Create password/),
      "Spring-Tide-Harbour",
    );
    await user.type(
      screen.getByLabelText(/^Confirm password/),
      "Spring-Tide-Harbour",
    );
    await user.click(
      screen.getByRole("button", { name: "Create account and join" }),
    );
    return user;
  }

  it("new account: sends token, trimmed name and password; never signs in", async () => {
    const api = scripted(PREVIEW_NEW);
    api.on("POST /auth/invitations/accept", noContent());
    open();
    await fillNewAccount();
    await waitFor(() =>
      expect(navigation.assignLocation).toHaveBeenCalledWith(
        "/login?reason=invitation-accepted",
      ),
    );
    expect(api.callsTo("POST /auth/invitations/accept")[0]!.body).toEqual({
      token: TOKEN,
      display_name: "Deck Cadet Rao",
      password: "Spring-Tide-Harbour",
    });
  });

  it("existing account: sends the token only", async () => {
    const api = scripted(PREVIEW_EXISTING);
    api.on("POST /auth/invitations/accept", noContent());
    open();
    const user = userEvent.setup({ delay: null });
    await user.click(
      await screen.findByRole("button", { name: "Accept invitation" }),
    );
    await waitFor(() => expect(navigation.assignLocation).toHaveBeenCalled());
    expect(api.callsTo("POST /auth/invitations/accept")[0]!.body).toEqual({
      token: TOKEN,
    });
  });

  it("a 404 on accept shows the same 'can't be used' state, with focus on it", async () => {
    const api = scripted(PREVIEW_EXISTING);
    api.on("POST /auth/invitations/accept", apiError(404, "NOT_FOUND"));
    open();
    const user = userEvent.setup({ delay: null });
    await user.click(
      await screen.findByRole("button", { name: "Accept invitation" }),
    );
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "This invitation can't be used",
      }),
    ).toHaveFocus();
  });

  it("a common password: field error and both passwords cleared", async () => {
    const api = scripted(PREVIEW_NEW);
    api.on(
      "POST /auth/invitations/accept",
      apiError(422, "VALIDATION_ERROR", {
        details: [{ field: "password", code: "password_too_common" }],
      }),
    );
    open();
    await fillNewAccount();
    expect(
      await screen.findByText(
        "This password is too common. Choose a different one.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/^Create password/)).toHaveValue("");
    expect(screen.getByLabelText(/^Confirm password/)).toHaveValue("");
    expect(screen.getByLabelText(/^Your name/)).toHaveValue(
      "  Deck Cadet Rao ",
    );
  });

  it("already signed in: notice, then 'Switch institute' and 'Sign out' after accepting", async () => {
    const api = scripted(PREVIEW_EXISTING, ok(readySession()));
    api.on("POST /auth/invitations/accept", noContent());
    api.on("POST /auth/logout", noContent());
    open();
    expect(
      await screen.findByText(
        "You're signed in as Ananya Rao. Accepting this invitation doesn't change who is signed in.",
      ),
    ).toBeInTheDocument();
    const user = userEvent.setup({ delay: null });
    await user.click(screen.getByRole("button", { name: "Accept invitation" }));
    const done = await screen.findByText(
      "Invitation accepted. You can now open Harbour Nautical Academy.",
    );
    expect(navigation.assignLocation).not.toHaveBeenCalled();
    const actions = done.closest("[tabindex='-1']") as HTMLElement;
    expect(actions).toHaveFocus();
    await user.click(
      within(actions).getByRole("button", { name: "Switch institute" }),
    );
    expect(navigation.assignLocation).toHaveBeenCalledWith("/select-institute");
    await user.click(within(actions).getByRole("button", { name: "Sign out" }));
    await waitFor(() =>
      expect(navigation.assignLocation).toHaveBeenLastCalledWith(
        "/login?reason=invitation-accepted",
      ),
    );
    expect(api.callsTo("POST /auth/logout")).toHaveLength(1);
  });

  it("passes axe in Dark", async () => {
    scripted(PREVIEW_NEW);
    const { container } = open();
    await screen.findByLabelText(/^Your name/);
    document.documentElement.dataset.theme = "dark";
    await expectNoA11yViolations(container);
  });
});
