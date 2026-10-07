import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { expectHeadingOutline } from "@/design-system/testing/a11y";
import { expectNoA11yViolations } from "@/design-system/testing/axe";
import { ThemeProvider } from "@/design-system/theme/ThemeProvider";
import type { SessionWire } from "@/lib/api/types";
import { installFetch } from "@/test/fetch-mock";
import { readySession } from "@/test/session-fixtures";

import { TenantFrame } from "../../tenant-frame";

import AccountSecurityPage, { metadata } from "./page";

vi.setConfig({ testTimeout: 30_000 });

// /app/account/security (T01-09C UI contract §3, D9C-1): the server gate runs
// first; the page is personal (any ready member, no permission needed by the
// session MFA endpoints) and reached from the account menu.

const state = vi.hoisted(() => ({
  session: null as SessionWire | null,
  push: vi.fn(),
}));

vi.mock("server-only", () => ({}));
vi.mock("next/navigation", () => ({
  usePathname: () => "/app/account/security",
  useRouter: () => ({ push: state.push, refresh: vi.fn() }),
  notFound: () => {
    throw new Error("NEXT_NOT_FOUND");
  },
  redirect: (url: string) => {
    throw new Error(`NEXT_REDIRECT ${url}`);
  },
}));
vi.mock("@/lib/session/server", () => ({
  readTenantSession: () => Promise.resolve(state.session),
  requireReadyTenantSession: (next: string) =>
    state.session
      ? Promise.resolve(state.session)
      : Promise.reject(
          new Error(
            `NEXT_REDIRECT /session-ended?reason=ended&next=${encodeURIComponent(next)}`,
          ),
        ),
}));

beforeEach(() => {
  state.session = readySession({ permissions: [] });
  state.push.mockReset();
});

async function renderPage() {
  const page = await AccountSecurityPage();
  document.documentElement.dataset.theme = "light";
  return render(
    <ThemeProvider>
      <TenantFrame session={state.session!} showUnreleased={false}>
        {page}
      </TenantFrame>
    </ThemeProvider>,
  );
}

describe("page gate", () => {
  it("no ready tenant session (none, expired, MFA pending, platform cookie only) → session-ended with next", async () => {
    state.session = null;
    await expect(AccountSecurityPage()).rejects.toThrow(
      "NEXT_REDIRECT /session-ended?reason=ended&next=%2Fapp%2Faccount%2Fsecurity",
    );
  });

  it("renders for any ready member, including one without permissions (personal page)", async () => {
    installFetch();
    const { container } = await renderPage();
    expect(
      screen.getByRole("heading", { level: 1, name: "Sign-in security" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("region", { name: "Two-step verification" }),
    ).toBeInTheDocument();
    expectHeadingOutline(container);
    await expectNoA11yViolations(container);
    expect(metadata.title).toBe(
      "Sign-in security · Tenant Application · MTI 360",
    );
  });
});

describe("account menu", () => {
  it("offers Sign-in security and navigates there", async () => {
    installFetch();
    const user = userEvent.setup();
    await renderPage();
    await user.click(screen.getByRole("button", { name: /account menu$/ }));
    const menu = await screen.findByRole("menu");
    await user.click(
      within(menu).getByRole("menuitem", { name: "Sign-in security" }),
    );
    expect(state.push).toHaveBeenCalledWith("/app/account/security");
  });
});

describe("source rules", () => {
  const SRC = path.resolve(
    path.dirname(fileURLToPath(import.meta.url)),
    "../../../..",
  );
  const FILES = [
    "features/identity/TenantSignInSecurity.tsx",
    "features/identity/AuthenticatorSetupSteps.tsx",
    "features/identity/RecoveryCodesPanel.tsx",
    "app/app/account/security/page.tsx",
  ];

  it("tenant MFA code: no role-name gating, no storage, no logging, tenant paths only", () => {
    for (const file of FILES) {
      const source = readFileSync(path.join(SRC, file), "utf8");
      expect(source, file).not.toMatch(/roles\.(includes|some|find|indexOf)\(/);
      expect(source, file).not.toMatch(/role(\.name)?\s*===/);
      expect(source, file).not.toMatch(
        /localStorage|sessionStorage|indexedDB|document\.cookie/,
      );
      expect(source, file).not.toMatch(
        /console\.(log|info|warn|error|debug|trace)\(/,
      );
      expect(source, file).not.toMatch(/["'`]\/platform/);
    }
  });
});
