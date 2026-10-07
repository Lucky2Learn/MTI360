import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StrictMode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "@/design-system/testing/axe";
import type { SessionWire } from "@/lib/api/types";
import { TenantSessionProvider } from "@/lib/session/SessionProvider";
import { apiError, installFetch, noContent, ok } from "@/test/fetch-mock";
import { ENROLMENT, RECOVERY_CODES } from "@/test/platform-fixtures";
import { renderScreen } from "@/test/render-screen";
import { CSRF_TOKEN, readySession } from "@/test/session-fixtures";

import { TenantSignInSecurity } from "./TenantSignInSecurity";

vi.setConfig({ testTimeout: 30_000 });

// Tenant AUTH-04 Sign-in security (T01-09C UI contract §4-§6): opt-in set-up
// on POST /session/mfa/enrolment and /enrolment/confirm, recovery codes shown
// once, and turning it off with a current code on POST /session/mfa/remove —
// all through the tenant session provider (tenant cookie, CSRF, T01-05 §11).

const documentNav = vi.hoisted(() => ({
  assignLocation: vi.fn<(url: string) => void>(),
  reloadDocument: vi.fn(),
  currentPath: vi.fn(() => "/app/account/security"),
}));
vi.mock("@/lib/session/document", () => documentNav);

const START = "POST /session/mfa/enrolment";
const CONFIRM = "POST /session/mfa/enrolment/confirm";
const REMOVE = "POST /session/mfa/remove";

beforeEach(() => {
  documentNav.assignLocation.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderSecurity(
  session: SessionWire = readySession(),
  {
    strict = false,
    theme = "light",
  }: { strict?: boolean; theme?: "light" | "dark" } = {},
) {
  const tree = (
    <TenantSessionProvider initialSession={session}>
      <TenantSignInSecurity />
    </TenantSessionProvider>
  );
  return renderScreen(strict ? <StrictMode>{tree}</StrictMode> : tree, {
    theme,
  });
}

// `hidden`: while a modal is open the page behind it is aria-hidden.
const mfaRegion = () =>
  screen.getByRole("region", { name: "Two-step verification", hidden: true });

async function openKey(api: ReturnType<typeof installFetch>) {
  api.on(START, ok(ENROLMENT));
  const user = userEvent.setup({ delay: null });
  await user.click(
    screen.getByRole("button", { name: "Set up two-step verification" }),
  );
  const dialog = await screen.findByRole("dialog", {
    name: "Add MTI 360 to your authenticator app",
  });
  return { user, dialog };
}

describe("status", () => {
  it("off: explains the feature and offers set-up; account details are read-only", async () => {
    const api = installFetch();
    const { container } = renderSecurity();
    expect(mfaRegion()).toHaveTextContent("Status");
    expect(mfaRegion()).toHaveTextContent("Off");
    expect(mfaRegion()).toHaveTextContent(/authenticator app/);
    const account = screen.getByRole("region", { name: "Account" });
    expect(account).toHaveTextContent("Ananya Rao");
    expect(account).toHaveTextContent("Coastal Maritime Training Institute");
    expect(screen.queryByRole("textbox")).toBeNull();
    // No recovery-code count or regeneration exists for tenants (BG-T1).
    expect(screen.queryByText(/codes left|generate new/i)).toBeNull();
    expect(api.calls).toHaveLength(0);
    await expectNoA11yViolations(container);
  });

  it("on: shows the status and the turn-off action only", () => {
    installFetch();
    renderSecurity(readySession({ mfa_enabled: true }));
    expect(mfaRegion()).toHaveTextContent("On — authenticator app");
    expect(
      screen.getByRole("button", { name: "Turn off two-step verification" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Set up two-step verification" }),
    ).toBeNull();
  });
});

describe("set-up", () => {
  it("never starts on mount — not even under StrictMode", async () => {
    const api = installFetch();
    renderSecurity(readySession(), { strict: true });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 30));
    });
    expect(api.calls).toHaveLength(0);
  });

  it("starts once on the explicit press, with the tenant CSRF token on a tenant path", async () => {
    const api = installFetch();
    renderSecurity(readySession(), { strict: true });
    const { dialog } = await openKey(api);
    const [call] = api.callsTo(START);
    expect(api.callsTo(START)).toHaveLength(1);
    expect(call!.headers["x-csrf-token"]).toBe(CSRF_TOKEN);
    expect(api.calls.every((c) => !c.path.startsWith("/platform"))).toBe(true);
    expect(within(dialog).getByLabelText("Setup key")).toHaveTextContent(
      "JBSW Y3DP EHPK 3PXP JBSW Y3DP EHPK 3PXP",
    );
    expect(
      within(dialog).getByRole("link", { name: "Open in authenticator app" }),
    ).toHaveAttribute("href", ENROLMENT.otpauth_uri);
    expect(within(dialog).getByText("30 seconds")).toBeInTheDocument();
    expect(dialog.querySelector("img, canvas")).toBeNull();
    expect(document.title).not.toContain(ENROLMENT.secret);
    await expectNoA11yViolations(dialog);
  });

  it("copies the key only on press", async () => {
    const api = installFetch();
    renderSecurity();
    const { user, dialog } = await openKey(api);
    const writeText = vi.fn(() => Promise.resolve());
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    expect(writeText).not.toHaveBeenCalled();
    await user.click(within(dialog).getByRole("button", { name: "Copy key" }));
    expect(writeText).toHaveBeenCalledWith(ENROLMENT.secret);
  });

  it("a wrong code keeps the key with a field error and clears the field", async () => {
    const api = installFetch();
    api.on(
      CONFIRM,
      apiError(422, "VALIDATION_ERROR", {
        details: [{ field: "code", code: "mfa_code_invalid" }],
      }),
    );
    renderSecurity();
    const { user, dialog } = await openKey(api);
    const field = within(dialog).getByLabelText(
      /^Code from your authenticator app/,
    );
    expect(field).toHaveAttribute("autocomplete", "one-time-code");
    expect(field).toHaveAttribute("inputmode", "numeric");
    expect(dialog).toHaveTextContent(
      "Each wrong code counts toward locking your account.",
    );
    await user.type(field, "111111");
    await user.click(
      within(dialog).getByRole("button", { name: "Verify and turn on" }),
    );
    expect(
      await within(dialog).findByText(
        "That code didn't work. Check your authenticator app and try again.",
      ),
    ).toBeInTheDocument();
    expect(field).toHaveValue("");
    expect(field).toHaveFocus();
    expect(within(dialog).getByLabelText("Setup key")).toBeInTheDocument();
    expect(screen.queryByText(/SERVER-/)).toBeNull();
  });

  it("success: drops the key, shows the codes once with a required acknowledgement, then re-reads the session", async () => {
    const api = installFetch();
    api.on(CONFIRM, ok({ recovery_codes: RECOVERY_CODES }));
    api.on("GET /session", ok(readySession({ mfa_enabled: true })));
    renderSecurity();
    const { user, dialog } = await openKey(api);
    await user.type(
      within(dialog).getByLabelText(/^Code from your authenticator app/),
      "123456",
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Verify and turn on" }),
    );
    const codes = await screen.findByRole("dialog", {
      name: "Save your recovery codes",
    });
    expect(api.callsTo(CONFIRM)[0]!.body).toEqual({ code: "123456" });
    expect(api.callsTo(CONFIRM)[0]!.headers["x-csrf-token"]).toBe(CSRF_TOKEN);
    expect(document.body.textContent).not.toContain("JBSW");
    expect(document.querySelector('a[href^="otpauth:"]')).toBeNull();
    expect(within(codes).getAllByRole("listitem")).toHaveLength(10);
    expect(codes).toHaveTextContent(/can't be retrieved later/);
    expect(codes).toHaveTextContent(
      /turn two-step verification off and on again/,
    );
    expect(
      within(codes).queryByRole("button", { name: /download|print/i }),
    ).toBeNull();

    // Escape does not dismiss the codes.
    await user.keyboard("{Escape}");
    expect(
      screen.getByRole("dialog", { name: "Save your recovery codes" }),
    ).toBeInTheDocument();

    // The leave-page guard is armed while the codes are shown.
    const guarded = new Event("beforeunload", { cancelable: true });
    act(() => {
      window.dispatchEvent(guarded);
    });
    expect(guarded.defaultPrevented).toBe(true);

    await user.click(within(codes).getByRole("button", { name: "Done" }));
    expect(
      await within(codes).findByText(
        "Confirm that you've saved your recovery codes.",
      ),
    ).toBeInTheDocument();
    await user.click(
      within(codes).getByRole("checkbox", {
        name: "I've saved my recovery codes",
      }),
    );
    await user.click(within(codes).getByRole("button", { name: "Done" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(document.body.textContent).not.toContain("abcde-fghij");
    const released = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(released);
    expect(released.defaultPrevented).toBe(false);

    // The server, not the UI, says MFA is now on.
    await waitFor(() =>
      expect(mfaRegion()).toHaveTextContent("On — authenticator app"),
    );
    expect(api.callsTo("GET /session")).toHaveLength(1);
    const outcome = screen.getByText("Two-step verification is on.");
    await waitFor(() =>
      expect(outcome.closest("[tabindex='-1']")).toHaveFocus(),
    );
  });

  it("cancel (or Escape) drops the key and confirms nothing", async () => {
    const api = installFetch();
    renderSecurity();
    const { user } = await openKey(api);
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(document.body.textContent).not.toContain("JBSW");
    expect(
      screen.getByText(/Set-up cancelled\. If you added an MTI 360 entry/),
    ).toBeInTheDocument();
    expect(api.callsTo(CONFIRM)).toHaveLength(0);
  });

  it("409 (already on elsewhere) re-reads the session instead of guessing", async () => {
    const api = installFetch();
    api.on(START, apiError(409, "CONFLICT"));
    api.on("GET /session", ok(readySession({ mfa_enabled: true })));
    renderSecurity();
    await userEvent
      .setup()
      .click(
        screen.getByRole("button", { name: "Set up two-step verification" }),
      );
    expect(
      await screen.findByText("Two-step verification is already on."),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(mfaRegion()).toHaveTextContent("On — authenticator app"),
    );
  });

  it("SESSION_REFRESH_REQUIRED: re-reads, never resends the start, and asks to try again", async () => {
    const api = installFetch();
    api.on(START, apiError(403, "SESSION_REFRESH_REQUIRED"));
    api.on("GET /session", ok(readySession({ csrf_token: "fresh" })));
    renderSecurity();
    await userEvent
      .setup()
      .click(
        screen.getByRole("button", { name: "Set up two-step verification" }),
      );
    expect(
      await screen.findByText("Your session was refreshed. Try again."),
    ).toBeInTheDocument();
    expect(api.callsTo(START)).toHaveLength(1);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("PERMISSION_DENIED shows the fixed denial (the server blocks the action)", async () => {
    const api = installFetch();
    api.on(START, apiError(403, "PERMISSION_DENIED"));
    api.on("GET /session", ok(readySession()));
    renderSecurity();
    await userEvent
      .setup()
      .click(
        screen.getByRole("button", { name: "Set up two-step verification" }),
      );
    expect(await screen.findByText("You can't do this")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("401 during confirmation (session ended, e.g. too many codes) goes to session-ended", async () => {
    const api = installFetch();
    api.on(CONFIRM, apiError(401, "AUTHENTICATION_REQUIRED"));
    api.on("GET /session", apiError(401, "AUTHENTICATION_REQUIRED"));
    renderSecurity();
    const { user, dialog } = await openKey(api);
    await user.type(
      within(dialog).getByLabelText(/^Code from your authenticator app/),
      "123456",
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Verify and turn on" }),
    );
    await waitFor(() =>
      expect(documentNav.assignLocation).toHaveBeenCalledWith(
        "/session-ended?reason=ended&next=%2Fapp%2Faccount%2Fsecurity",
      ),
    );
  });

  it("429 during confirmation shows the rate-limit message in the dialog", async () => {
    const api = installFetch();
    api.on(CONFIRM, apiError(429, "RATE_LIMITED"));
    renderSecurity();
    const { user, dialog } = await openKey(api);
    await user.type(
      within(dialog).getByLabelText(/^Code from your authenticator app/),
      "123456",
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Verify and turn on" }),
    );
    expect(
      await within(dialog).findByText("Too many attempts"),
    ).toBeInTheDocument();
  });
});

describe("turning it off", () => {
  async function openRemove() {
    const user = userEvent.setup({ delay: null });
    await user.click(
      screen.getByRole("button", { name: "Turn off two-step verification" }),
    );
    const dialog = await screen.findByRole("dialog", {
      name: "Turn off two-step verification?",
    });
    return { user, dialog };
  }

  it("needs a current code: a wrong code is a field error and nothing changes", async () => {
    const api = installFetch();
    api.on(
      REMOVE,
      apiError(422, "VALIDATION_ERROR", {
        details: [{ field: "code", code: "mfa_code_invalid" }],
      }),
    );
    renderSecurity(readySession({ mfa_enabled: true }));
    const { user, dialog } = await openRemove();
    expect(dialog).toHaveTextContent(/recovery codes stop working/);
    const field = within(dialog).getByLabelText(/^Authentication code/);
    await user.type(field, "000000");
    await user.click(within(dialog).getByRole("button", { name: "Turn off" }));
    expect(
      await within(dialog).findByText(
        "That code didn't work. Check your authenticator app and try again.",
      ),
    ).toBeInTheDocument();
    expect(field).toHaveValue("");
    expect(mfaRegion()).toHaveTextContent("On — authenticator app");
    await expectNoA11yViolations(dialog);
  });

  it("success: re-reads the session and announces the change", async () => {
    const api = installFetch();
    api.on(REMOVE, noContent());
    api.on("GET /session", ok(readySession({ mfa_enabled: false })));
    renderSecurity(readySession({ mfa_enabled: true }));
    const { user, dialog } = await openRemove();
    await user.type(
      within(dialog).getByLabelText(/^Authentication code/),
      "654321",
    );
    await user.click(within(dialog).getByRole("button", { name: "Turn off" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(api.callsTo(REMOVE)[0]!.body).toEqual({ code: "654321" });
    expect(api.callsTo(REMOVE)[0]!.headers["x-csrf-token"]).toBe(CSRF_TOKEN);
    await waitFor(() => expect(mfaRegion()).toHaveTextContent("Off"));
    expect(
      screen.getByText("Two-step verification is off."),
    ).toBeInTheDocument();
  });

  it("cancel performs nothing", async () => {
    const api = installFetch();
    renderSecurity(readySession({ mfa_enabled: true }));
    const { user, dialog } = await openRemove();
    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(api.calls).toHaveLength(0);
  });
});

describe("theme and accessibility", () => {
  it("passes axe in Dark", async () => {
    installFetch();
    const { container } = renderSecurity(readySession({ mfa_enabled: true }), {
      theme: "dark",
    });
    await expectNoA11yViolations(container);
  });
});
