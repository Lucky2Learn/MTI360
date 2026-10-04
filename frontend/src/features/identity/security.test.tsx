import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  apiError,
  inputUrl,
  installFetch,
  noContent,
  ok,
} from "@/test/fetch-mock";
import { renderScreen } from "@/test/render-screen";
import { readySession, sessionIn } from "@/test/session-fixtures";

import { AcceptInvitationScreen } from "./AcceptInvitationScreen";
import { LoginScreen } from "./LoginScreen";
import { ResetPasswordScreen } from "./ResetPasswordScreen";

// Whole flows typed key by key through React Aria: allow for a loaded CI host.
vi.setConfig({ testTimeout: 20_000 });

// Telemetry and storage (T01-04 UI contract S9-S11, acceptance item 11;
// T01-09A): during complete authentication flows, no password, token, MFA or
// recovery code, CSRF token or session value reaches the console (the only
// frontend reporter), browser storage, a request URL or the rendered page.

const navigation = vi.hoisted(() => ({
  assignLocation: vi.fn<(url: string) => void>(),
  reloadDocument: vi.fn(),
}));
vi.mock("@/lib/session/document", async (original) => ({
  ...(await original<typeof import("@/lib/session/document")>()),
  ...navigation,
}));

const SECRETS = {
  password: "Binnacle-Lamp-Starboard-9",
  resetToken: "fake-security-reset-token-xxxxxxxxxxxxxxxxx",
  invitationToken: "fake-security-invite-token-xxxxxxxxxxxxxxxx",
  totp: "771204",
  recovery: "qwert-yuiop",
  csrf: "pending-csrf-secret-value",
};

const CONSOLE_METHODS = [
  "log",
  "info",
  "warn",
  "error",
  "debug",
  "trace",
] as const;
let consoleCalls: unknown[][];
let storageWrites: unknown[][];

beforeEach(() => {
  consoleCalls = [];
  storageWrites = [];
  for (const method of CONSOLE_METHODS) {
    vi.spyOn(console, method).mockImplementation((...args: unknown[]) => {
      consoleCalls.push(args);
    });
  }
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(
    (...args: unknown[]) => {
      storageWrites.push(args);
    },
  );
  navigation.assignLocation.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.replaceState(null, "", "/");
});

function expectNoLeak(fetchUrls: string[]) {
  const reported = JSON.stringify(consoleCalls);
  const stored = JSON.stringify(storageWrites);
  const page = document.documentElement.outerHTML;
  for (const [name, secret] of Object.entries(SECRETS)) {
    expect(reported, `${name} in console`).not.toContain(secret);
    expect(stored, `${name} in storage`).not.toContain(secret);
    expect(page, `${name} in the page`).not.toContain(secret);
    expect(window.location.href, `${name} in the address bar`).not.toContain(
      secret,
    );
    for (const url of fetchUrls)
      expect(url, `${name} in a URL`).not.toContain(secret);
  }
  expect(storageWrites).toEqual([]);
}

const urls = (api: ReturnType<typeof installFetch>) =>
  api.fetchMock.mock.calls.map(([url]) => inputUrl(url));

it("sign-in with a wrong password, then MFA with a wrong code, a recovery code and success", async () => {
  const api = installFetch();
  api.on(
    "POST /auth/login",
    apiError(401, "AUTHENTICATION_REQUIRED"),
    ok(sessionIn("mfa_required", { csrf_token: SECRETS.csrf })),
  );
  api.on(
    "POST /auth/mfa/verify",
    apiError(422, "VALIDATION_ERROR", {
      details: [{ field: "code", code: "mfa_code_invalid" }],
    }),
  );
  api.on("POST /auth/mfa/recovery", ok(readySession()));
  renderScreen(<LoginScreen reason={null} next={null} />);
  const user = userEvent.setup({ delay: null });
  await user.type(
    screen.getByRole("textbox", { name: /^Email/ }),
    "ananya.rao@coastal-maritime.example",
  );
  await user.type(screen.getByLabelText(/^Password/), SECRETS.password);
  await user.click(screen.getByRole("button", { name: "Show password" }));
  await user.click(screen.getByRole("button", { name: "Sign in" }));
  await screen.findByRole("alert");
  await user.type(screen.getByLabelText(/^Password/), SECRETS.password);
  await user.click(screen.getByRole("button", { name: "Sign in" }));
  await user.type(
    await screen.findByRole("textbox", { name: /Authentication code/ }),
    SECRETS.totp,
  );
  await user.click(screen.getByRole("button", { name: "Verify" }));
  await screen.findByText(/That code didn't work/);
  await user.click(
    screen.getByRole("button", { name: "Use a recovery code instead" }),
  );
  await user.type(
    screen.getByRole("textbox", { name: /Recovery code/ }),
    SECRETS.recovery,
  );
  await user.click(screen.getByRole("button", { name: "Verify" }));
  await waitFor(() =>
    expect(navigation.assignLocation).toHaveBeenCalledWith("/app"),
  );
  expectNoLeak(urls(api));
});

it("password reset through the fragment link", async () => {
  const api = installFetch();
  api.on(
    "POST /auth/password-reset/confirm",
    apiError(500, "INTERNAL_ERROR"),
    noContent(),
  );
  window.history.replaceState(
    null,
    "",
    `/reset-password#token=${SECRETS.resetToken}`,
  );
  renderScreen(<ResetPasswordScreen />);
  const user = userEvent.setup({ delay: null });
  const fill = async () => {
    await user.type(
      await screen.findByLabelText(/^New password/),
      SECRETS.password,
    );
    await user.type(
      screen.getByLabelText(/^Confirm new password/),
      SECRETS.password,
    );
    await user.click(screen.getByRole("button", { name: "Change password" }));
  };
  await fill();
  await screen.findByRole("alert");
  await fill();
  await waitFor(() => expect(navigation.assignLocation).toHaveBeenCalled());
  expectNoLeak(urls(api));
});

it("invitation acceptance through the fragment link", async () => {
  const api = installFetch();
  api.on(
    "POST /auth/invitations/preview",
    ok({
      institute_name: "Harbour Nautical Academy",
      email_masked: "d***t@harbour.example",
      account: "new",
    }),
  );
  api.on("GET /session", apiError(401, "AUTHENTICATION_REQUIRED"));
  api.on(
    "POST /auth/invitations/accept",
    new TypeError("offline"),
    noContent(),
  );
  window.history.replaceState(
    null,
    "",
    `/accept-invitation#token=${SECRETS.invitationToken}`,
  );
  renderScreen(<AcceptInvitationScreen />);
  const user = userEvent.setup({ delay: null });
  await user.type(await screen.findByLabelText(/^Your name/), "Deck Cadet Rao");
  const fill = async () => {
    await user.type(
      screen.getByLabelText(/^Create password/),
      SECRETS.password,
    );
    await user.type(
      screen.getByLabelText(/^Confirm password/),
      SECRETS.password,
    );
    await user.click(
      screen.getByRole("button", { name: "Create account and join" }),
    );
  };
  await fill();
  await screen.findByRole("alert");
  await fill();
  await waitFor(() => expect(navigation.assignLocation).toHaveBeenCalled());
  expectNoLeak(urls(api));
});

describe("source rules", () => {
  it("authentication code never logs request bodies", async () => {
    const { readdirSync, readFileSync } = await import("node:fs");
    const path = await import("node:path");
    const { fileURLToPath } = await import("node:url");
    const here = path.dirname(fileURLToPath(import.meta.url));
    const roots = [
      here,
      path.resolve(here, "../../lib/session"),
      path.resolve(here, "../../lib/api"),
    ];
    const offenders = roots.flatMap((root) =>
      readdirSync(root)
        .filter((name) => /\.tsx?$/.test(name) && !/\.test\.tsx?$/.test(name))
        .filter((name) =>
          /console\.(log|info|warn|debug|trace)\(/.test(
            readFileSync(path.join(root, name), "utf8"),
          ),
        )
        .map((name) => name),
    );
    expect(offenders).toEqual([]);
  });
});
