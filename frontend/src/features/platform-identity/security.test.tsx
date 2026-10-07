import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ResetPasswordScreen } from "@/features/identity/ResetPasswordScreen";
import { PlatformSessionProvider } from "@/lib/session/PlatformSessionProvider";
import {
  apiError,
  inputUrl,
  installFetch,
  noContent,
  ok,
} from "@/test/fetch-mock";
import {
  pendingPlatformSession,
  platformSession,
} from "@/test/platform-fixtures";
import { renderScreen } from "@/test/render-screen";

import { PlatformAcceptInvitationScreen } from "./PlatformAcceptInvitationScreen";
import { PlatformLoginScreen } from "./PlatformLoginScreen";
import { SignInSecurity } from "./SignInSecurity";
import { StepUpDialog } from "./StepUpDialog";

vi.setConfig({ testTimeout: 30_000 });

// Telemetry, storage, URL and title (T01-09B UI contract §11; S9-S11):
// during complete platform flows no password, token, MFA or recovery code,
// TOTP secret, otpauth URI or CSRF token reaches the console (the only
// frontend reporter), browser storage, a request URL, the address bar, the
// page title, or the rendered page once its step is over.

const navigation = vi.hoisted(() => ({
  assignLocation: vi.fn<(url: string) => void>(),
  reloadDocument: vi.fn(),
  currentPath: vi.fn(() => "/platform/profile"),
}));
vi.mock("@/lib/session/document", async (original) => ({
  ...(await original<typeof import("@/lib/session/document")>()),
  ...navigation,
}));

const SECRETS = {
  password: "Gangway-Watch-Starboard-3",
  resetToken: "fake-platform-reset-token-xxxxxxxxxxxxxxxxx",
  invitationToken: "fake-platform-invite-token-xxxxxxxxxxxxxxx",
  totp: "771204",
  stepUp: "602915",
  recovery: "qwert-yuiop",
  pendingCsrf: "pending-platform-csrf-secret",
  csrf: "full-platform-csrf-secret",
  secret: "KRSXG5CTMVRXEZLUKRSXG5CTMVRXEZLU",
  uri: "otpauth://totp/MTI%20360:m%40x?secret=KRSXG5CTMVRXEZLUKRSXG5CTMVRXEZLU",
  code1: "secra-codea",
  code2: "secrb-codeb",
};

const CODES = [SECRETS.code1, SECRETS.code2];

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
let storageReads: string[];

beforeEach(() => {
  consoleCalls = [];
  storageWrites = [];
  storageReads = [];
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
  // Reads go to the real localStorage (the theme preference lives there).
  const read = window.localStorage.getItem.bind(window.localStorage);
  vi.spyOn(Storage.prototype, "getItem").mockImplementation((key: string) => {
    storageReads.push(key);
    return read(key);
  });
  navigation.assignLocation.mockReset();
  document.title = "MTI 360";
});

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.replaceState(null, "", "/");
});

/** `onPage`: secrets that must also be gone from the rendered page. */
function expectNoLeak(
  fetchUrls: string[],
  onPage: (keyof typeof SECRETS)[] = Object.keys(
    SECRETS,
  ) as (keyof typeof SECRETS)[],
) {
  const reported = JSON.stringify(consoleCalls);
  const stored = JSON.stringify(storageWrites);
  const page = document.documentElement.outerHTML;
  for (const [name, secret] of Object.entries(SECRETS)) {
    expect(reported, `${name} in console`).not.toContain(secret);
    expect(stored, `${name} in storage`).not.toContain(secret);
    expect(window.location.href, `${name} in the address bar`).not.toContain(
      secret,
    );
    expect(document.title, `${name} in the title`).not.toContain(secret);
    for (const url of fetchUrls)
      expect(url, `${name} in a URL`).not.toContain(secret);
    if (onPage.includes(name as keyof typeof SECRETS)) {
      expect(page, `${name} in the page`).not.toContain(secret);
    }
  }
  expect(storageWrites).toEqual([]);
  // The only storage read is the theme preference (no session authority).
  expect(storageReads.filter((key) => key !== "mti360.theme")).toEqual([]);
}

const urls = (api: ReturnType<typeof installFetch>) =>
  api.fetchMock.mock.calls.map(([url]) => inputUrl(url));

it("sign-in, enrolment (wrong code, then success), recovery codes and acknowledgement", async () => {
  const api = installFetch();
  api.on(
    "POST /platform/auth/login",
    apiError(401, "AUTHENTICATION_REQUIRED"),
    ok(pendingPlatformSession("mfa_enrolment_required", SECRETS.pendingCsrf)),
  );
  api.on(
    "POST /platform/auth/mfa/enrolment",
    ok({ secret: SECRETS.secret, otpauth_uri: SECRETS.uri }),
  );
  api.on(
    "POST /platform/auth/mfa/enrolment/confirm",
    apiError(422, "VALIDATION_ERROR", {
      details: [{ field: "code", code: "mfa_code_invalid" }],
    }),
    ok({
      recovery_codes: CODES,
      session: platformSession({ csrf_token: SECRETS.csrf }),
    }),
  );
  renderScreen(<PlatformLoginScreen reason={null} next={null} />);
  const user = userEvent.setup({ delay: null });
  await user.type(
    screen.getByRole("textbox", { name: /^Email/ }),
    "meera.iyer@mti360.example",
  );
  await user.type(screen.getByLabelText(/^Password/), SECRETS.password);
  await user.click(screen.getByRole("button", { name: "Show password" }));
  await user.click(screen.getByRole("button", { name: "Sign in" }));
  await screen.findByRole("alert");
  await user.type(screen.getByLabelText(/^Password/), SECRETS.password);
  await user.click(screen.getByRole("button", { name: "Sign in" }));
  await user.click(
    await screen.findByRole("button", { name: "Set up authenticator app" }),
  );
  const field = await screen.findByLabelText(
    /^Code from your authenticator app/,
  );
  await user.type(field, SECRETS.totp);
  await user.click(screen.getByRole("button", { name: "Verify and turn on" }));
  await screen.findByText(/That code didn't work/);
  await user.type(field, SECRETS.totp);
  await user.click(screen.getByRole("button", { name: "Verify and turn on" }));
  await screen.findByRole("heading", { name: "Save your recovery codes" });
  // While shown the codes are on the page — but the key and URI are gone.
  expectNoLeak(urls(api), ["password", "secret", "uri", "totp", "pendingCsrf"]);
  await user.click(
    screen.getByRole("checkbox", { name: "I've saved my recovery codes" }),
  );
  await user.click(screen.getByRole("button", { name: "Continue" }));
  await waitFor(() => expect(navigation.assignLocation).toHaveBeenCalled());
  expectNoLeak(urls(api), ["password", "secret", "uri", "totp", "pendingCsrf"]);
});

it("sign-in, a wrong TOTP code, then a recovery code", async () => {
  const api = installFetch();
  api.on(
    "POST /platform/auth/login",
    ok(pendingPlatformSession("mfa_required", SECRETS.pendingCsrf)),
  );
  api.on(
    "POST /platform/auth/mfa/verify",
    apiError(422, "VALIDATION_ERROR", {
      details: [{ field: "code", code: "mfa_code_invalid" }],
    }),
  );
  api.on("POST /platform/auth/mfa/recovery", ok(platformSession()));
  renderScreen(<PlatformLoginScreen reason={null} next={null} />);
  const user = userEvent.setup({ delay: null });
  await user.type(
    screen.getByRole("textbox", { name: /^Email/ }),
    "meera.iyer@mti360.example",
  );
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
  await waitFor(() => expect(navigation.assignLocation).toHaveBeenCalled());
  expectNoLeak(urls(api));
});

it("password reset: the fragment is removed at once and the token stays in POST bodies", async () => {
  const api = installFetch();
  api.on("POST /platform/auth/password-reset/confirm", noContent());
  window.history.replaceState(
    null,
    "",
    `/platform/reset-password#token=${SECRETS.resetToken}`,
  );
  renderScreen(<ResetPasswordScreen realm="platform" />);
  const user = userEvent.setup({ delay: null });
  await user.type(
    await screen.findByLabelText(/^New password/),
    SECRETS.password,
  );
  expect(window.location.hash).toBe("");
  expect(window.location.pathname).toBe("/platform/reset-password");
  await user.type(
    screen.getByLabelText(/^Confirm new password/),
    SECRETS.password,
  );
  await user.click(screen.getByRole("button", { name: "Change password" }));
  await waitFor(() => expect(navigation.assignLocation).toHaveBeenCalled());
  expect(
    api.callsTo("POST /platform/auth/password-reset/confirm")[0]!.body,
  ).toMatchObject({ token: SECRETS.resetToken });
  expectNoLeak(urls(api));
});

it("invitation acceptance: the fragment is removed at once", async () => {
  const api = installFetch();
  api.on(
    "POST /platform/auth/invitations/preview",
    ok({ email: "m…@mti360.example" }),
  );
  api.on(
    "POST /platform/auth/invitations/accept",
    new TypeError("offline"),
    noContent(),
  );
  window.history.replaceState(
    null,
    "",
    `/platform/accept-invitation#token=${SECRETS.invitationToken}`,
  );
  renderScreen(<PlatformAcceptInvitationScreen />);
  const user = userEvent.setup({ delay: null });
  const fill = async () => {
    await user.type(
      await screen.findByLabelText(/^Create password/),
      SECRETS.password,
    );
    await user.type(
      screen.getByLabelText(/^Confirm password/),
      SECRETS.password,
    );
    await user.click(screen.getByRole("button", { name: "Accept invitation" }));
  };
  await fill();
  expect(window.location.hash).toBe("");
  await screen.findByRole("alert");
  await fill();
  await waitFor(() => expect(navigation.assignLocation).toHaveBeenCalled());
  expectNoLeak(urls(api));
});

it("step-up and regeneration: the step-up code and the new codes leave nothing behind", async () => {
  const api = installFetch();
  api.on(
    "POST /platform/session/mfa/recovery-codes",
    apiError(403, "STEP_UP_REQUIRED"),
    ok({ recovery_codes: CODES }),
  );
  api.on(
    "POST /platform/session/step-up",
    ok(platformSession({ csrf_token: SECRETS.csrf })),
  );
  api.on(
    "GET /platform/session",
    ok(platformSession({ csrf_token: SECRETS.csrf })),
  );
  renderScreen(
    <PlatformSessionProvider
      initialSession={platformSession({ csrf_token: SECRETS.csrf })}
    >
      <SignInSecurity />
      <StepUpDialog />
    </PlatformSessionProvider>,
  );
  const user = userEvent.setup({ delay: null });
  await user.click(
    screen.getByRole("button", { name: "Generate new recovery codes" }),
  );
  await user.click(
    await screen.findByRole("button", { name: "Generate new codes" }),
  );
  await user.type(
    await screen.findByLabelText(/Authentication code/),
    SECRETS.stepUp,
  );
  await user.click(screen.getByRole("button", { name: "Verify and continue" }));
  await screen.findByRole("dialog", { name: "Save your recovery codes" });
  await user.click(
    screen.getByRole("checkbox", { name: "I've saved my recovery codes" }),
  );
  await user.click(screen.getByRole("button", { name: "Done" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  await act(async () => {
    await Promise.resolve();
  });
  // The CSRF token travels only in headers (never a URL or the page).
  expect(
    api.callsTo("POST /platform/session/step-up")[0]!.headers["x-csrf-token"],
  ).toBe(SECRETS.csrf);
  expectNoLeak(urls(api));
});

describe("source rules", () => {
  const SRC = path.resolve(
    path.dirname(fileURLToPath(import.meta.url)),
    "../..",
  );
  const sources = (dir: string) =>
    readdirSync(path.join(SRC, dir))
      .filter((name) => /\.tsx?$/.test(name) && !/\.test\.tsx?$/.test(name))
      .map((name) => ({
        name: `${dir}/${name}`,
        text: readFileSync(path.join(SRC, dir, name), "utf8"),
      }));
  const platformCode = [
    ...sources("features/platform-identity"),
    ...sources("lib/session").filter(({ name }) => /platform/i.test(name)),
  ];

  it("platform identity code never logs", () => {
    const offenders = platformCode
      .filter(({ text }) =>
        /console\.(log|info|warn|error|debug|trace)\(/.test(text),
      )
      .map(({ name }) => name);
    expect(offenders).toEqual([]);
  });

  it("platform identity code never uses browser storage or readable cookies", () => {
    const offenders = platformCode
      .filter(({ text }) =>
        /localStorage|sessionStorage|indexedDB|document\.cookie/.test(text),
      )
      .map(({ name }) => name);
    expect(offenders).toEqual([]);
  });

  it("the platform client only calls /api/v1/platform paths (never the tenant cookie's realm)", () => {
    let checked = 0;
    for (const { name, text } of platformCode) {
      for (const match of text.matchAll(
        /apiRequest<[^>]*>\(\s*`?"?([^`",)]+)/g,
      )) {
        const target = match[1]!;
        checked += 1;
        expect(
          target.startsWith("/platform") || target.startsWith("${PLATFORM"),
          `${name}: ${target}`,
        ).toBe(true);
      }
    }
    expect(checked).toBeGreaterThanOrEqual(4);
  });
});
