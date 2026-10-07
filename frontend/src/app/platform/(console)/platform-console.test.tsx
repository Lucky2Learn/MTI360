import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "@/design-system/testing/axe";
import type { PlatformSessionWire } from "@/lib/api/types";
import { apiError, installFetch, noContent, ok } from "@/test/fetch-mock";
import { platformSession, RECOVERY_CODES } from "@/test/platform-fixtures";
import { renderScreen } from "@/test/render-screen";

import PlatformPage from "./[[...slug]]/page";
import { PlatformFrame } from "./platform-frame";
import PlatformProfilePage from "./profile/page";

vi.setConfig({ testTimeout: 30_000 });

// The platform console (T01-09B UI contract §8, §10): the server page gate,
// the requirement map, permission-aware navigation, the zero-permission
// state, the account menu (display-only roles), sign-out, the low
// recovery-codes warning and the partial PLAT-52 with step-up.

const navigation = vi.hoisted(() => ({ pathname: "/platform", push: vi.fn() }));
vi.mock("next/navigation", () => ({
  usePathname: () => navigation.pathname,
  useRouter: () => ({ push: navigation.push, refresh: vi.fn() }),
  notFound: () => {
    throw new Error("NEXT_NOT_FOUND");
  },
  redirect: (url: string) => {
    throw new Error(`NEXT_REDIRECT ${url}`);
  },
}));

const server = vi.hoisted(() => ({
  session: null as PlatformSessionWire | null,
}));
vi.mock("@/lib/session/platform-server", () => ({
  readPlatformSession: () => Promise.resolve(server.session),
  requirePlatformSession: (next: string) =>
    server.session
      ? Promise.resolve(server.session)
      : Promise.reject(
          new Error(
            `NEXT_REDIRECT /platform/session-ended?reason=ended${
              next === "/platform" ? "" : `&next=${encodeURIComponent(next)}`
            }`,
          ),
        ),
  SessionReadError: class extends Error {},
}));

const env = vi.hoisted(() => ({ appEnv: "production" }));
vi.mock("@/lib/env", () => ({
  getServerEnv: () => ({ appEnv: env.appEnv }),
}));

const documentNav = vi.hoisted(() => ({
  assignLocation: vi.fn<(url: string) => void>(),
  reloadDocument: vi.fn(),
  currentPath: vi.fn(() => "/platform"),
}));
vi.mock("@/lib/session/document", () => documentNav);

beforeEach(() => {
  server.session = platformSession();
  env.appEnv = "production";
  navigation.push.mockReset();
  documentNav.assignLocation.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

async function renderPage(slug?: string[], session = server.session!) {
  navigation.pathname = ["/platform", ...(slug ?? [])].join("/");
  const page = await PlatformPage({ params: Promise.resolve({ slug }) });
  return renderScreen(
    <PlatformFrame
      session={session}
      showUnreleased={env.appEnv === "development"}
    >
      {page}
    </PlatformFrame>,
  );
}

const platformNav = () =>
  screen.getByRole("navigation", { name: "Platform navigation" });

describe("page gate", () => {
  it("no full platform session (none, expired, pending, tenant cookie only) → session-ended with next", async () => {
    server.session = null;
    await expect(
      PlatformPage({ params: Promise.resolve({ slug: ["users"] }) }),
    ).rejects.toThrow(
      "NEXT_REDIRECT /platform/session-ended?reason=ended&next=%2Fplatform%2Fusers",
    );
    await expect(PlatformProfilePage()).rejects.toThrow("NEXT_REDIRECT");
  });

  it("unknown paths and UNRELEASED pages outside development are not found", async () => {
    await expect(
      PlatformPage({ params: Promise.resolve({ slug: ["nope"] }) }),
    ).rejects.toThrow("NEXT_NOT_FOUND");
    await expect(
      PlatformPage({ params: Promise.resolve({ slug: ["system-health"] }) }),
    ).rejects.toThrow("NEXT_NOT_FOUND");
  });

  it("a missing permission is access denied at the same URL, without naming permissions or roles", async () => {
    server.session = platformSession({
      permissions: ["audit.read"],
      roles: ["SECURITY_AUDIT_ADMIN"],
    });
    const { container } = await renderPage(["tenants"]);
    expect(
      screen.getByRole("heading", {
        name: "You don't have access to this page",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText(/ask a Super Admin/)).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/tenant\.read|institute/i);
    await expectNoA11yViolations(container);
  });

  it("decides by permission, never by role name", async () => {
    // A role named SUPER_ADMIN without the permission is still denied.
    server.session = platformSession({
      permissions: [],
      roles: ["SUPER_ADMIN"],
    });
    await renderPage(["users"]);
    expect(
      screen.getByRole("heading", {
        name: "You don't have access to this page",
      }),
    ).toBeInTheDocument();
  });
});

describe("navigation and Overview", () => {
  it("Super Admin: Overview, Tenants, Platform Users and Audit; UNRELEASED hidden outside development", async () => {
    const { container } = await renderPage();
    const nav = platformNav();
    for (const label of ["Overview", "Tenants", "Platform Users", "Audit"]) {
      expect(
        within(nav).getByRole("link", { name: label }),
      ).toBeInTheDocument();
    }
    for (const label of ["System Health", "Integrations", "Settings"]) {
      expect(within(nav).queryByRole("link", { name: label })).toBeNull();
    }
    expect(
      screen.getByRole("heading", {
        name: "Your platform overview is empty for now",
      }),
    ).toBeInTheDocument();
    // No tenant controls in the platform shell.
    expect(
      screen.queryByRole("button", { name: /Institute:|Campus:/ }),
    ).toBeNull();
    await expectNoA11yViolations(container);
  });

  it("Security / Audit Admin sees Overview and Audit only", async () => {
    server.session = platformSession({
      permissions: ["audit.read"],
      roles: ["SECURITY_AUDIT_ADMIN"],
    });
    await renderPage();
    const links = within(platformNav())
      .getAllByRole("link")
      .map((link) => link.textContent);
    expect(links).toEqual(["Overview", "Audit"]);
  });

  it("zero effective permissions: the 'nothing assigned' empty state and Overview only", async () => {
    server.session = platformSession({
      permissions: [],
      roles: ["SUPPORT_ADMIN"],
    });
    const { container } = await renderPage();
    expect(
      screen.getByRole("heading", {
        name: "No platform areas are assigned to your role yet",
      }),
    ).toBeInTheDocument();
    expect(
      within(platformNav())
        .getAllByRole("link")
        .map((link) => link.textContent),
    ).toEqual(["Overview"]);
    await expectNoA11yViolations(container);
  });

  it("development shows UNRELEASED items", async () => {
    env.appEnv = "development";
    await renderPage();
    expect(
      within(platformNav()).getByRole("link", { name: "System Health" }),
    ).toBeInTheDocument();
  });

  it.each([
    [3, "You're running low on recovery codes (3 codes left)"],
    [1, "You're running low on recovery codes (1 code left)"],
    [0, "You have no recovery codes left"],
  ])(
    "warns at %i remaining codes, with a link to Sign-in security",
    async (remaining, title) => {
      server.session = platformSession({
        mfa: {
          enrolled: true,
          verified_at: null,
          step_up_expires_at: null,
          recovery_codes_remaining: remaining,
        },
      });
      await renderPage();
      expect(screen.getByText(title)).toBeInTheDocument();
      expect(
        screen.getByRole("link", { name: "Generate new codes" }),
      ).toHaveAttribute("href", "/platform/profile");
      expect(window.location.search).not.toContain(String(remaining));
    },
  );

  it("no warning above 3 remaining codes", async () => {
    await renderPage();
    expect(screen.queryByText(/recovery codes left|running low/)).toBeNull();
  });
});

describe("account menu and sign-out", () => {
  it("shows name, email and role labels; items are Sign-in security, Preferences and Sign out", async () => {
    const user = userEvent.setup();
    await renderPage();
    await user.click(screen.getByRole("button", { name: /account menu$/ }));
    const menu = await screen.findByRole("menu");
    expect(
      screen.getByText("Meera Iyer", { selector: "p" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Roles: Super Admin")).toBeInTheDocument();
    expect(
      within(menu)
        .getAllByRole("menuitem")
        .map((item) => item.textContent?.trim()),
    ).toEqual(["Sign-in security", "Preferences", "Sign out"]);
    await user.click(
      within(menu).getByRole("menuitem", { name: "Sign-in security" }),
    );
    expect(navigation.push).toHaveBeenCalledWith("/platform/profile");
  });

  it("signs out through the platform API only and lands on the platform session-ended page", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on("POST /platform/auth/logout", noContent());
    await renderPage();
    await user.click(screen.getByRole("button", { name: /account menu$/ }));
    await user.click(await screen.findByRole("menuitem", { name: "Sign out" }));
    await waitFor(() =>
      expect(documentNav.assignLocation).toHaveBeenCalledWith(
        "/platform/session-ended?reason=signed-out",
      ),
    );
    expect(api.calls.map((call) => call.path)).toEqual([
      "/platform/auth/logout",
    ]);
    // The tenant session is never touched.
    expect(api.callsTo("POST /auth/logout")).toHaveLength(0);
  });

  it("sign-out still navigates when the API fails (idempotent)", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on("POST /platform/auth/logout", new TypeError("offline"));
    await renderPage();
    await user.click(screen.getByRole("button", { name: /account menu$/ }));
    await user.click(await screen.findByRole("menuitem", { name: "Sign out" }));
    await waitFor(() =>
      expect(documentNav.assignLocation).toHaveBeenCalledWith(
        "/platform/session-ended?reason=signed-out",
      ),
    );
  });
});

describe("partial PLAT-52 Sign-in security", () => {
  // The page's server read (PlatformSessionSync) is the session shown.
  async function renderProfile(session = server.session!) {
    navigation.pathname = "/platform/profile";
    const page = await PlatformProfilePage();
    return renderScreen(
      <PlatformFrame session={session} showUnreleased={false}>
        {page}
      </PlatformFrame>,
    );
  }

  it("shows identity, MFA status and codes remaining; nothing else of the profile", async () => {
    const { container } = await renderProfile();
    expect(
      screen.getByRole("heading", { level: 1, name: "Sign-in security" }),
    ).toBeInTheDocument();
    const account = screen.getByRole("region", { name: "Account" });
    expect(account).toHaveTextContent("Meera Iyer");
    expect(account).toHaveTextContent("meera.iyer@mti360.example");
    expect(account).toHaveTextContent("Super Admin");
    const mfa = screen.getByRole("region", { name: "Two-step verification" });
    expect(mfa).toHaveTextContent("On — authenticator app");
    expect(mfa).toHaveTextContent("10 codes left");
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(
      screen.queryByRole("button", { name: /password|remove|disable/i }),
    ).toBeNull();
    await expectNoA11yViolations(container);
  });

  it("shows the low-codes warning without a self-link", async () => {
    server.session = platformSession({
      mfa: {
        enrolled: true,
        verified_at: null,
        step_up_expires_at: null,
        recovery_codes_remaining: 2,
      },
    });
    await renderProfile();
    expect(
      screen.getByText("You're running low on recovery codes (2 codes left)"),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Generate new codes" }),
    ).toBeNull();
  });

  it("generate: confirm → STEP_UP_REQUIRED → step-up → one resend → codes once → Done re-reads the session", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on(
      "POST /platform/session/mfa/recovery-codes",
      apiError(403, "STEP_UP_REQUIRED"),
      ok({ recovery_codes: RECOVERY_CODES }),
    );
    api.on("POST /platform/session/step-up", ok(platformSession()));
    api.on("GET /platform/session", ok(platformSession()));
    await renderProfile();

    await user.click(
      screen.getByRole("button", { name: "Generate new recovery codes" }),
    );
    const confirm = await screen.findByRole("alertdialog", {
      name: "Generate new recovery codes?",
    });
    expect(confirm).toHaveTextContent(/stop working/);
    expect(api.calls).toHaveLength(0);
    await user.click(
      within(confirm).getByRole("button", { name: "Generate new codes" }),
    );

    await screen.findByRole("dialog", { name: "Confirm it's you" });
    await user.type(screen.getByLabelText(/Authentication code/), "654321");
    await user.click(
      screen.getByRole("button", { name: "Verify and continue" }),
    );

    const codes = await screen.findByRole("dialog", {
      name: "Save your recovery codes",
    });
    expect(within(codes).getAllByRole("listitem")).toHaveLength(10);
    expect(
      api.callsTo("POST /platform/session/mfa/recovery-codes"),
    ).toHaveLength(2);

    // Escape does not dismiss the codes; only the acknowledgement does.
    await user.keyboard("{Escape}");
    expect(
      screen.getByRole("dialog", { name: "Save your recovery codes" }),
    ).toBeInTheDocument();

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
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
    expect(document.body.textContent).not.toContain("abcde-fghij");
    await waitFor(() =>
      expect(api.callsTo("GET /platform/session")).toHaveLength(1),
    );
  });

  it("cancelling step-up performs nothing and shows nothing", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on(
      "POST /platform/session/mfa/recovery-codes",
      apiError(403, "STEP_UP_REQUIRED"),
    );
    await renderProfile();
    await user.click(
      screen.getByRole("button", { name: "Generate new recovery codes" }),
    );
    await user.click(
      await screen.findByRole("button", { name: "Generate new codes" }),
    );
    await screen.findByRole("dialog", { name: "Confirm it's you" });
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryByText(/couldn't|wrong/i)).toBeNull();
    expect(
      api.callsTo("POST /platform/session/mfa/recovery-codes"),
    ).toHaveLength(1);
  });

  it("a repeated STEP_UP_REQUIRED shows an error and stops", async () => {
    const user = userEvent.setup();
    const api = installFetch();
    api.on(
      "POST /platform/session/mfa/recovery-codes",
      apiError(403, "STEP_UP_REQUIRED"),
      apiError(403, "STEP_UP_REQUIRED"),
    );
    api.on("POST /platform/session/step-up", ok(platformSession()));
    await renderProfile();
    await user.click(
      screen.getByRole("button", { name: "Generate new recovery codes" }),
    );
    await user.click(
      await screen.findByRole("button", { name: "Generate new codes" }),
    );
    await screen.findByRole("dialog", { name: "Confirm it's you" });
    await user.type(screen.getByLabelText(/Authentication code/), "654321");
    await user.click(
      screen.getByRole("button", { name: "Verify and continue" }),
    );
    expect(
      await screen.findByText("We couldn't confirm it's you. Try again."),
    ).toBeInTheDocument();
    expect(
      api.callsTo("POST /platform/session/mfa/recovery-codes"),
    ).toHaveLength(2);
  });
});

describe("source rules", () => {
  const ROOT = path.resolve(
    path.dirname(fileURLToPath(import.meta.url)),
    "../../..",
  );
  const read = (file: string) => readFileSync(path.join(ROOT, file), "utf8");

  it("the platform console decides by permission, never by role name", () => {
    for (const file of [
      "app/platform/(console)/[[...slug]]/page.tsx",
      "app/platform/(console)/platform-frame.tsx",
      "app/platform/(console)/overview.tsx",
      "features/platform-identity/SignInSecurity.tsx",
      "lib/session/PlatformSessionProvider.tsx",
    ]) {
      const source = read(file);
      expect(source).not.toMatch(/roles\.(includes|some|find|indexOf)\(/);
      expect(source).not.toMatch(/===\s*"SUPER_ADMIN"|"SUPER_ADMIN"\s*===/);
    }
  });
});
