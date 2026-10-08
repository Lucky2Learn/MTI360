import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { expectHeadingOutline } from "@/design-system/testing/a11y";
import { expectNoA11yViolations } from "@/design-system/testing/axe";
import type { SessionWire } from "@/lib/api/types";
import { ShellAccessDenied } from "@/shells";
import { normalizedHtml } from "@/test/render-screen";
import { readySession } from "@/test/session-fixtures";

import TenantPage, { generateMetadata } from "./[[...slug]]/page";
import TenantNotFound, { metadata as notFoundMetadata } from "./not-found";

// Page access for /app/* (T01-05 UI contract §7, §8.1, §8.2, §16 "Routes"):
// decided on the server before any protected content renders.

const state = vi.hoisted(() => ({
  appEnv: "development",
  session: null as SessionWire | null,
}));

vi.mock("server-only", () => ({}));
vi.mock("next/navigation", () => ({
  usePathname: () => "/app",
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
  notFound: () => {
    throw new Error("NEXT_NOT_FOUND");
  },
  redirect: (url: string) => {
    throw new Error(`NEXT_REDIRECT ${url}`);
  },
}));
vi.mock("@/lib/env", () => ({
  getServerEnv: () => ({ appEnv: state.appEnv, apiBaseUrl: "http://api:8000" }),
}));
vi.mock("@/lib/session/server", () => ({
  readTenantSession: () => Promise.resolve(state.session),
  requireReadyTenantSession: (path: string) =>
    state.session
      ? Promise.resolve(state.session)
      : Promise.reject(new Error(`NEXT_REDIRECT /session-ended?next=${path}`)),
}));

const page = async (slug?: string[]) => {
  const element = await TenantPage({ params: Promise.resolve({ slug }) });
  return render(element);
};

beforeEach(() => {
  state.appEnv = "development";
  state.session = readySession({ permissions: ["campus.read"] });
});

describe("allowed pages", () => {
  it("renders a page whose permission the session has", async () => {
    await page(["administration", "campuses"]);
    expect(
      screen.getByRole("heading", { level: 1, name: "Campuses" }),
    ).toBeInTheDocument();
    await expect(
      generateMetadata({
        params: Promise.resolve({ slug: ["administration", "campuses"] }),
      }),
    ).resolves.toEqual({ title: "Campuses · Tenant Application · MTI 360" });
  });

  it("renders DASH-01 for /app: the empty dashboard with no action", async () => {
    state.session = readySession({ permissions: [] });
    const { container } = await page(undefined);
    expect(
      screen.getByRole("heading", { level: 1, name: "Dashboard" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        level: 2,
        name: "Your dashboard is empty for now",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Sections appear here as your institute uses MTI 360 and your access includes them.",
      ),
    ).toBeInTheDocument();
    expect(container.querySelector("main button, button")).toBeNull();
  });
});

describe("AUTHZ-01 access denied", () => {
  it("renders at the requested URL with no protected content", async () => {
    const { container } = await page(["administration", "users"]);
    expect(
      screen.getByRole("heading", { level: 1, name: "Access denied" }),
    ).toHaveClass("sr-only");
    expect(
      screen.getByRole("heading", {
        level: 2,
        name: "You don't have access to this page",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Your access in this institute doesn't include this page. If you need it, ask your institute administrator.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Go to dashboard" }),
    ).toHaveAttribute("href", "/app");
    expect(container.textContent).not.toMatch(
      /Users is not built yet|member\.read|role/i,
    );
    expectHeadingOutline(container);
    await expect(
      generateMetadata({
        params: Promise.resolve({ slug: ["administration", "users"] }),
      }),
    ).resolves.toEqual({
      title: "Access denied · Tenant Application · MTI 360",
    });
  });

  it("is identical for every denied page", async () => {
    const users = normalizedHtml(
      (await page(["administration", "users"])).container,
    );
    const roles = normalizedHtml(
      (await page(["administration", "roles"])).container,
    );
    const audit = normalizedHtml(
      (await page(["administration", "audit-logs"])).container,
    );
    expect(roles).toBe(users);
    expect(audit).toBe(users);
  });

  it("moves focus to its h1 after a client-side navigation only", () => {
    const { unmount } = render(<ShellAccessDenied homeHref="/app" />);
    expect(screen.getByRole("heading", { level: 1 })).not.toHaveFocus();
    unmount();
    const link = document.createElement("a");
    link.href = "/app/administration/users";
    document.body.append(link);
    link.focus();
    render(<ShellAccessDenied homeHref="/app" />);
    expect(
      screen.getByRole("heading", { level: 1, name: "Access denied" }),
    ).toHaveFocus();
    link.remove();
  });

  it("passes axe", async () => {
    const { container } = await page(["administration", "roles"]);
    await expectNoA11yViolations(container);
    document.documentElement.dataset.theme = "dark";
    await expectNoA11yViolations(container);
    document.documentElement.dataset.theme = "light";
  });
});

describe("RESOURCE-02 not found", () => {
  it("an unknown route is a 404", async () => {
    await expect(page(["administration", "ships"])).rejects.toThrow(
      "NEXT_NOT_FOUND",
    );
  });

  it("an UNRELEASED page is a 404 in staging and production, a page in development", async () => {
    for (const appEnv of ["staging", "production"]) {
      state.appEnv = appEnv;
      await expect(page(["admissions", "applications"])).rejects.toThrow(
        "NEXT_NOT_FOUND",
      );
    }
    state.appEnv = "development";
    await page(["admissions", "applications"]);
    expect(
      screen.getByRole("heading", { level: 1, name: "Applications" }),
    ).toBeInTheDocument();
  });

  it("checks the session before anything else (no route discovery without a session)", async () => {
    state.session = null;
    await expect(page(["administration", "ships"])).rejects.toThrow(
      "NEXT_REDIRECT /session-ended?next=/app/administration/ships",
    );
  });

  it("renders one view for every cause, inside the shell, with its own title", async () => {
    const { container } = render(<TenantNotFound />);
    expect(
      screen.getByRole("heading", { level: 1, name: "Not found" }),
    ).toHaveClass("sr-only");
    expect(
      screen.getByRole("heading", { level: 2, name: "Page not found" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "This page or item doesn't exist, or it's no longer available.",
      ),
    ).toBeInTheDocument();
    expect(container.textContent).not.toMatch(
      /access|another institute|campus/i,
    );
    expect(notFoundMetadata.title).toBe(
      "Not found · Tenant Application · MTI 360",
    );
    expectHeadingOutline(container);
    await expectNoA11yViolations(container);
  });
});

describe("no authority from the URL or storage", () => {
  it("ignores permission-like query parameters and storage", async () => {
    state.session = readySession({ permissions: [] });
    window.localStorage.setItem("permissions", '["member.read"]');
    window.history.replaceState(
      null,
      "",
      "/app/administration/users?permission=member.read",
    );
    await page(["administration", "users"]);
    expect(
      screen.getByRole("heading", { level: 1, name: "Access denied" }),
    ).toBeInTheDocument();
    window.localStorage.clear();
    window.history.replaceState(null, "", "/");
  });
});
