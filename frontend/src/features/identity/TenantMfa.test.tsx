import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TenantSessionProvider } from "@/lib/session/SessionProvider";
import {
  apiError,
  inputUrl,
  installFetch,
  noContent,
  ok,
} from "@/test/fetch-mock";
import { renderScreen } from "@/test/render-screen";
import { readySession, sessionIn } from "@/test/session-fixtures";

import { LoginScreen } from "./LoginScreen";
import { TenantSignInSecurity } from "./TenantSignInSecurity";

vi.setConfig({ testTimeout: 30_000 });

// Tenant MFA (T01-09C UI contract §4-§7): the sign-in MFA step on the tenant
// endpoints only, and — across complete set-up and turn-off flows — no
// password, MFA or recovery code, setup key, otpauth URI or CSRF token in the
// console, browser storage, a request URL, the address bar, the title or the
// page once its step is over.

const navigation = vi.hoisted(() => ({
  assignLocation: vi.fn<(url: string) => void>(),
  reloadDocument: vi.fn(),
  currentPath: vi.fn(() => "/app/account/security"),
}));
vi.mock("@/lib/session/document", async (original) => ({
  ...(await original<typeof import("@/lib/session/document")>()),
  ...navigation,
}));

const SECRETS = {
  password: "Halyard-Mizzen-Leeward-8",
  totp: "481516",
  removal: "234234",
  recovery: "zyxwv-utsrq",
  pendingCsrf: "tenant-pending-csrf-secret",
  csrf: "tenant-full-csrf-secret",
  secret: "MFZWIZLTMFZWIZLTMFZWIZLTMFZWIZLT",
  uri: "otpauth://totp/MTI%20360:a%40x?secret=MFZWIZLTMFZWIZLTMFZWIZLTMFZWIZLT",
  code1: "tcoda-aaaaa",
  code2: "tcodb-bbbbb",
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

const urls = (api: ReturnType<typeof installFetch>) =>
  api.fetchMock.mock.calls.map(([url]) => inputUrl(url));

function expectNoLeak(fetchUrls: string[]) {
  const reported = JSON.stringify(consoleCalls);
  const stored = JSON.stringify(storageWrites);
  const page = document.documentElement.outerHTML;
  for (const [name, secret] of Object.entries(SECRETS)) {
    expect(reported, `${name} in console`).not.toContain(secret);
    expect(stored, `${name} in storage`).not.toContain(secret);
    expect(page, `${name} in the page`).not.toContain(secret);
    expect(document.title, `${name} in the title`).not.toContain(secret);
    expect(window.location.href, `${name} in the address bar`).not.toContain(
      secret,
    );
    for (const url of fetchUrls) {
      expect(url, `${name} in a URL`).not.toContain(secret);
    }
  }
  expect(storageWrites).toEqual([]);
  expect(storageReads.filter((key) => key !== "mti360.theme")).toEqual([]);
}

async function signInToMfa(api: ReturnType<typeof installFetch>) {
  api.on(
    "POST /auth/login",
    ok(sessionIn("mfa_required", { csrf_token: SECRETS.pendingCsrf })),
  );
  renderScreen(<LoginScreen reason={null} next="/app/finance" />);
  const user = userEvent.setup({ delay: null });
  await user.type(
    screen.getByRole("textbox", { name: /^Email/ }),
    "ananya.rao@coastal-maritime.example",
  );
  await user.type(screen.getByLabelText(/^Password/), SECRETS.password);
  await user.click(screen.getByRole("button", { name: "Sign in" }));
  await screen.findByRole("heading", {
    level: 1,
    name: "Enter your authentication code",
  });
  return user;
}

describe("tenant sign-in MFA step", () => {
  it("TOTP success: the rotated session decides the next step (full document navigation)", async () => {
    const api = installFetch();
    const user = await signInToMfa(api);
    api.on(
      "POST /auth/mfa/verify",
      ok(sessionIn("institute_selection_required")),
    );
    await user.type(
      screen.getByLabelText(/^Authentication code/),
      SECRETS.totp,
    );
    await user.click(screen.getByRole("button", { name: "Verify" }));
    await waitFor(() =>
      expect(navigation.assignLocation).toHaveBeenCalledWith(
        "/select-institute?next=%2Fapp%2Ffinance",
      ),
    );
    const [verify] = api.callsTo("POST /auth/mfa/verify");
    expect(verify!.headers["x-csrf-token"]).toBe(SECRETS.pendingCsrf);
    // Tenant endpoints only; nothing reads a pending session back.
    expect(api.calls.map((call) => call.path)).toEqual([
      "/auth/login",
      "/auth/mfa/verify",
    ]);
    expectNoLeak(urls(api));
  });

  it("a refused recovery code shows its own message and allows another try", async () => {
    const api = installFetch();
    const user = await signInToMfa(api);
    api.on(
      "POST /auth/mfa/recovery",
      apiError(422, "VALIDATION_ERROR", {
        details: [{ field: "recovery_code", code: "mfa_code_invalid" }],
      }),
      ok(readySession()),
    );
    await user.click(
      screen.getByRole("button", { name: "Use a recovery code instead" }),
    );
    const field = await screen.findByLabelText(/^Recovery code/);
    expect(field).toHaveAttribute("autocomplete", "off");
    await user.type(field, SECRETS.recovery);
    await user.click(screen.getByRole("button", { name: "Verify" }));
    expect(
      await screen.findByText(
        "That recovery code didn't work. Check it and try again.",
      ),
    ).toBeInTheDocument();
    expect(field).toHaveValue("");
    expect(field).toHaveFocus();
    await user.type(field, SECRETS.recovery);
    await user.click(screen.getByRole("button", { name: "Verify" }));
    await waitFor(() =>
      expect(navigation.assignLocation).toHaveBeenCalledWith("/app/finance"),
    );
    expectNoLeak(urls(api));
  });

  it("429 on the code step shows the generic rate-limit warning", async () => {
    const api = installFetch();
    const user = await signInToMfa(api);
    api.on("POST /auth/mfa/verify", apiError(429, "RATE_LIMITED"));
    await user.type(
      screen.getByLabelText(/^Authentication code/),
      SECRETS.totp,
    );
    await user.click(screen.getByRole("button", { name: "Verify" }));
    expect(await screen.findByText("Too many attempts")).toBeInTheDocument();
    expect(screen.queryByText(/SERVER-|locked/i)).toBeNull();
  });

  it("the step moves focus to its h1 and keeps the institute sign-in context", async () => {
    const api = installFetch();
    await signInToMfa(api);
    await waitFor(() =>
      expect(
        screen.getByRole("heading", {
          level: 1,
          name: "Enter your authentication code",
        }),
      ).toHaveFocus(),
    );
    expect(screen.getByRole("banner")).not.toHaveTextContent(
      "Platform administration",
    );
  });
});

describe("set-up and turn-off leave nothing behind", () => {
  it("set-up (wrong code, then success), recovery codes and acknowledgement", async () => {
    const api = installFetch();
    api.on(
      "POST /session/mfa/enrolment",
      ok({ secret: SECRETS.secret, otpauth_uri: SECRETS.uri }),
    );
    api.on(
      "POST /session/mfa/enrolment/confirm",
      apiError(422, "VALIDATION_ERROR", {
        details: [{ field: "code", code: "mfa_code_invalid" }],
      }),
      ok({ recovery_codes: [SECRETS.code1, SECRETS.code2] }),
    );
    api.on(
      "GET /session",
      ok(readySession({ mfa_enabled: true, csrf_token: SECRETS.csrf })),
    );
    renderScreen(
      <TenantSessionProvider
        initialSession={readySession({ csrf_token: SECRETS.csrf })}
      >
        <TenantSignInSecurity />
      </TenantSessionProvider>,
    );
    const user = userEvent.setup({ delay: null });
    await user.click(
      screen.getByRole("button", { name: "Set up two-step verification" }),
    );
    const field = await screen.findByLabelText(
      /^Code from your authenticator app/,
    );
    await user.type(field, SECRETS.totp);
    await user.click(
      screen.getByRole("button", { name: "Verify and turn on" }),
    );
    await screen.findByText(/That code didn't work/);
    await user.type(field, SECRETS.totp);
    await user.click(
      screen.getByRole("button", { name: "Verify and turn on" }),
    );
    await screen.findByRole("dialog", { name: "Save your recovery codes" });
    await user.click(
      screen.getByRole("checkbox", { name: "I've saved my recovery codes" }),
    );
    await user.click(screen.getByRole("button", { name: "Done" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await screen.findByText("On — authenticator app");
    expectNoLeak(urls(api));
  });

  it("turning off with a current code", async () => {
    const api = installFetch();
    api.on("POST /session/mfa/remove", noContent());
    api.on("GET /session", ok(readySession({ csrf_token: SECRETS.csrf })));
    renderScreen(
      <TenantSessionProvider
        initialSession={readySession({
          mfa_enabled: true,
          csrf_token: SECRETS.csrf,
        })}
      >
        <TenantSignInSecurity />
      </TenantSessionProvider>,
    );
    const user = userEvent.setup({ delay: null });
    await user.click(
      screen.getByRole("button", { name: "Turn off two-step verification" }),
    );
    await user.type(
      await screen.findByLabelText(/^Authentication code/),
      SECRETS.removal,
    );
    await user.click(screen.getByRole("button", { name: "Turn off" }));
    await screen.findByText("Two-step verification is off.");
    expect(
      api.callsTo("POST /session/mfa/remove")[0]!.headers["x-csrf-token"],
    ).toBe(SECRETS.csrf);
    expectNoLeak(urls(api));
  });
});
