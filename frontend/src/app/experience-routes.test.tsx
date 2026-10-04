import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "@/design-system/testing/axe";
import { ThemeProvider } from "@/design-system/theme/ThemeProvider";
import {
  EXPERIENCE,
  EXPERIENCES,
  ExperienceFrame,
  experienceStaticParams,
  flattenNavigation,
  resolveExperiencePage,
  type ExperienceId,
} from "@/shells";

import TenantPage, {
  generateMetadata as tenantMetadata,
} from "./app/[[...slug]]/page";
import { metadata as tenantLayoutMetadata } from "./app/layout";
import { isShowcaseEnabled } from "./design-system/gate";
import PlatformPage from "./platform/[[...slug]]/page";
import PublicSitePage from "./site/[[...slug]]/page";
import StudentPage from "./student/[[...slug]]/page";

import type { ReactElement } from "react";

// Route boundaries (T00-08): /platform, /app, /student and /site are
// separate experiences whose pages are exactly their navigation
// configuration; "/" stays the neutral root page (INC-26) and /design-system
// stays development/test only.

const navigationState = vi.hoisted(() => ({
  pathname: "/platform",
  push: vi.fn(),
}));
vi.mock("next/navigation", () => ({
  usePathname: () => navigationState.pathname,
  useRouter: () => ({ push: navigationState.push, refresh: vi.fn() }),
  notFound: () => {
    throw new Error("NEXT_NOT_FOUND");
  },
  redirect: (url: string) => {
    throw new Error(`NEXT_REDIRECT ${url}`);
  },
}));

// /app is guarded since T01-09A: these structural tests run with a ready
// session holding the T01 tenant baseline (the guard has its own tests in
// lib/session and app/app).
vi.mock("server-only", () => ({}));
vi.mock("@/lib/session/server", async () => {
  const { readySession } = await import("@/test/session-fixtures");
  const session = readySession({
    permissions: [
      "audit.read",
      "campus.read",
      "member.read",
      "role.read",
      "tenant.profile.read",
    ],
  });
  return {
    readTenantSession: () => Promise.resolve(session),
    requireReadyTenantSession: () => Promise.resolve(session),
  };
});

const APP_DIR = path.dirname(fileURLToPath(import.meta.url));

const ROUTES: {
  id: ExperienceId;
  folder: string;
  basePath: string;
  Page: (props: {
    params: Promise<{ slug?: string[] }>;
  }) => Promise<ReactElement>;
}[] = [
  {
    id: EXPERIENCE.PLATFORM,
    folder: "platform",
    basePath: "/platform",
    Page: PlatformPage,
  },
  { id: EXPERIENCE.TENANT, folder: "app", basePath: "/app", Page: TenantPage },
  {
    id: EXPERIENCE.STUDENT,
    folder: "student",
    basePath: "/student",
    Page: StudentPage,
  },
  {
    id: EXPERIENCE.PUBLIC_SITE,
    folder: "site",
    basePath: "/site",
    Page: PublicSitePage,
  },
];

async function renderRoute(
  route: (typeof ROUTES)[number],
  slug: string[] | undefined,
) {
  navigationState.pathname = [route.basePath, ...(slug ?? [])].join("/");
  const page = await route.Page({ params: Promise.resolve({ slug }) });
  return render(
    <ThemeProvider>
      <ExperienceFrame experience={route.id}>{page}</ExperienceFrame>
    </ThemeProvider>,
  );
}

describe("experience configuration", () => {
  it.each(ROUTES)(
    "$basePath owns its navigation, with unique ids and paths",
    ({ id, basePath }) => {
      const experience = EXPERIENCES[id];
      expect(experience.basePath).toBe(basePath);
      const items = flattenNavigation(experience.navigation);
      expect(items.length).toBeGreaterThan(0);
      for (const item of items) {
        expect(
          item.href === basePath || item.href.startsWith(`${basePath}/`),
        ).toBe(true);
      }
      expect(new Set(items.map((item) => item.id)).size).toBe(items.length);
      expect(new Set(items.map((item) => item.href)).size).toBe(items.length);
    },
  );

  it("keeps the four experiences separate from each other and from the marketing root", () => {
    const bases = Object.values(EXPERIENCES).map((e) => e.basePath);
    expect(bases.sort()).toEqual(["/app", "/platform", "/site", "/student"]);
    expect(bases).not.toContain("/");
  });

  it("gives every top-level item of a rail navigation an icon", () => {
    for (const experience of Object.values(EXPERIENCES)) {
      if (experience.layout !== "application") continue;
      for (const section of experience.navigation) {
        for (const item of section.items) expect(item.icon).toBeDefined();
      }
    }
  });

  it("never places a tenant identifier in tenant routes", () => {
    const hrefs = flattenNavigation(EXPERIENCES.tenant.navigation).map(
      (item) => item.href,
    );
    expect(hrefs.every((href) => !/tenant|\[|:/.test(href))).toBe(true);
  });

  it("resolves configured pages and rejects everything else", () => {
    expect(resolveExperiencePage(EXPERIENCE.TENANT, undefined)?.isHome).toBe(
      true,
    );
    const leads = resolveExperiencePage(EXPERIENCE.TENANT, [
      "admissions",
      "leads",
    ]);
    expect(leads?.trail.map((item) => item.label)).toEqual([
      "Admissions",
      "Leads",
    ]);
    expect(
      resolveExperiencePage(EXPERIENCE.TENANT, ["admissions", "unknown"]),
    ).toBeNull();
    expect(resolveExperiencePage(EXPERIENCE.PLATFORM, ["app"])).toBeNull();
  });

  it("generates static params for every configured page, including the home page", () => {
    const params = experienceStaticParams(EXPERIENCE.PLATFORM);
    expect(params).toContainEqual({ slug: [] });
    expect(params).toContainEqual({ slug: ["tenants"] });
    expect(params).toHaveLength(
      flattenNavigation(EXPERIENCES.platform.navigation).length,
    );
    expect(experienceStaticParams(EXPERIENCE.TENANT)).toContainEqual({
      slug: ["ai", "sql-data-agent"],
    });
  });
});

describe("experience routes", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it.each(ROUTES)(
    "$basePath has a layout, loading and error boundary",
    ({ folder }) => {
      for (const file of [
        "layout.tsx",
        "loading.tsx",
        "error.tsx",
        "[[...slug]]/page.tsx",
      ]) {
        expect(existsSync(path.join(APP_DIR, folder, file))).toBe(true);
      }
    },
  );

  it.each(ROUTES.filter((route) => route.id !== EXPERIENCE.PUBLIC_SITE))(
    "$basePath renders the application shell with its home page",
    async (route) => {
      const { container } = await renderRoute(route, undefined);
      const experience = EXPERIENCES[route.id];
      expect(
        screen.getByRole("navigation", { name: experience.navigationLabel }),
      ).toBeInTheDocument();
      expect(
        within(screen.getByRole("main")).getByRole("heading", { level: 1 }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /account menu$/ }),
      ).toBeInTheDocument();
      await expectNoA11yViolations(container);
    },
  );

  it("renders the Tenant Public Website shell without account or search", async () => {
    const { container } = await renderRoute(ROUTES[3]!, undefined);
    expect(
      screen.getByRole("navigation", { name: "Website navigation" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("contentinfo")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /account menu/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "Search" })).toBeNull();
    expect(screen.queryByText("MTI 360")).toBeNull();
    await expectNoA11yViolations(container);
  });

  it("renders breadcrumbs and the current page for a nested tenant route", async () => {
    await renderRoute(ROUTES[1]!, ["finance", "fee-structure"]);
    const breadcrumb = screen.getByRole("navigation", { name: "Breadcrumb" });
    expect(
      within(breadcrumb).getByRole("link", { name: "Tenant Application" }),
    ).toHaveAttribute("href", "/app");
    expect(within(breadcrumb).getByText("Fee Structure")).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(
      screen.getByRole("heading", { level: 1, name: "Fee Structure" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Back to Tenant Application" }),
    ).toHaveAttribute("href", "/app");
  });

  it("navigates React Aria links client-side through the Next.js router", async () => {
    const user = userEvent.setup();
    navigationState.push.mockReset();
    await renderRoute(ROUTES[2]!, ["fees"]);
    await user.click(
      screen.getByRole("link", { name: "Back to Student Portal" }),
    );
    expect(navigationState.push).toHaveBeenCalledWith("/student");
  });

  it("returns 404 for paths outside the configuration", async () => {
    await expect(
      TenantPage({ params: Promise.resolve({ slug: ["unknown"] }) }),
    ).rejects.toThrow("NEXT_NOT_FOUND");
  });

  it("titles pages and keeps experience routes out of search indexes", async () => {
    await expect(
      tenantMetadata({ params: Promise.resolve({ slug: ["academics"] }) }),
    ).resolves.toEqual({
      title: "Academics · Tenant Application · MTI 360",
    });
    expect(tenantLayoutMetadata.robots).toEqual({
      index: false,
      follow: false,
    });
  });
});

describe("root and development routes", () => {
  it("keeps / as the neutral root page, not the showcase or an experience", () => {
    const source = readFileSync(path.join(APP_DIR, "page.tsx"), "utf8");
    expect(source).not.toMatch(/Showcase|ExperienceFrame/);
    expect(existsSync(path.join(APP_DIR, "route.ts"))).toBe(false);
  });

  it("keeps /design-system limited to development and test", () => {
    expect(isShowcaseEnabled("development")).toBe(true);
    expect(isShowcaseEnabled("test")).toBe(true);
    expect(isShowcaseEnabled("production")).toBe(false);
    expect(isShowcaseEnabled("staging")).toBe(false);
    expect(isShowcaseEnabled(undefined)).toBe(false);
  });
});
