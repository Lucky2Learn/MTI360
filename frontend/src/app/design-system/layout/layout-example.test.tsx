import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "@/design-system/testing/axe";
import { ThemeProvider } from "@/design-system/theme/ThemeProvider";

import { LayoutExample } from "./layout-example";

// /design-system/layout: same fail-closed gate as the showcase (T00-09).

vi.mock("server-only", () => ({}));
vi.mock("next/navigation", async (importOriginal) => ({
  ...(await importOriginal<typeof import("next/navigation")>()),
  usePathname: () => "/design-system/layout",
  useRouter: () => ({ push: vi.fn() }),
}));

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

async function loadPage(appEnv: string, extra: Record<string, string> = {}) {
  vi.stubEnv("APP_ENV", appEnv);
  for (const [key, value] of Object.entries(extra)) vi.stubEnv(key, value);
  return import("./page");
}

function notFoundDigest(render: () => unknown): string | undefined {
  try {
    render();
  } catch (error) {
    return (error as { digest?: string }).digest;
  }
  return undefined;
}

describe("layout example gate", () => {
  it.each(["staging", "production"])("returns 404 in %s", async (appEnv) => {
    const { default: Page } = await loadPage(appEnv, {
      API_BASE_URL: "https://api.mti360.example",
    });
    expect(notFoundDigest(() => Page())).toMatch(/404/);
  });

  it("fails closed (404) when the configuration is invalid", async () => {
    const { default: Page } = await loadPage("production");
    expect(notFoundDigest(() => Page())).toMatch(/404/);
  });

  it.each(["development", "test"])("renders in %s", async (appEnv) => {
    const { default: Page } = await loadPage(appEnv);
    expect(notFoundDigest(() => Page())).toBeUndefined();
  });

  it("is never indexed and always rendered at request time", async () => {
    const page = await loadPage("test");
    expect(page.metadata.robots).toEqual({ index: false, follow: false });
    expect(page.dynamic).toBe("force-dynamic");
  });
});

describe("layout example content", { timeout: 20_000 }, () => {
  it("renders one page inside the shell with every generic layout and passes axe", async () => {
    const { container } = render(
      <ThemeProvider>
        <LayoutExample />
      </ThemeProvider>,
    );
    expect(screen.getAllByRole("main")).toHaveLength(1);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    for (const name of [
      "Dashboard layout",
      "Data layout",
      "Detail layout",
      "Form layout",
    ]) {
      expect(screen.getByRole("region", { name })).toBeInTheDocument();
    }
    const kpis = screen.getByRole("list", { name: "Key figures" });
    expect(within(kpis).getAllByRole("listitem")).toHaveLength(4);
    expect(
      screen.getByRole("table", { name: "Enrolments (sample)" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("group", { name: "Form actions" }),
    ).toBeInTheDocument();
    await expectNoA11yViolations(container);
  });
});
