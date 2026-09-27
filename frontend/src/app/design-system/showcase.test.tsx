import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "@/design-system/testing/axe";
import { ThemeProvider } from "@/design-system/theme/ThemeProvider";

import { isShowcaseEnabled, SHOWCASE_ENVIRONMENTS } from "./gate";
import { Showcase } from "./showcase";

// The page reads server configuration; "server-only" throws outside a React
// Server environment by design (see lib/env.test.ts).
vi.mock("server-only", () => ({}));

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

describe("design-system showcase gate", () => {
  it("is enabled only in development and test", () => {
    expect(SHOWCASE_ENVIRONMENTS).toEqual(["development", "test"]);
    for (const env of ["development", "test"])
      expect(isShowcaseEnabled(env)).toBe(true);
    for (const env of ["staging", "production", "", undefined, "DEVELOPMENT"]) {
      expect(isShowcaseEnabled(env)).toBe(false);
    }
  });

  it.each(["staging", "production"])("returns 404 in %s", async (appEnv) => {
    const { default: Page } = await loadPage(appEnv, {
      API_BASE_URL: "https://api.mti360.example",
    });
    expect(notFoundDigest(() => Page())).toMatch(/404/);
  });

  it("fails closed (404) when the configuration is invalid", async () => {
    // production without API_BASE_URL is a configuration error (T00-04)
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

describe("design-system showcase content", () => {
  it("shows every T00-07A component section and passes axe", async () => {
    const { container } = render(
      <ThemeProvider>
        <Showcase />
      </ThemeProvider>,
    );

    expect(
      screen.getByRole("heading", { level: 1, name: "Design system" }),
    ).toBeInTheDocument();
    for (const name of [
      "Button",
      "IconButton",
      "Badge",
      "KPI",
      "Card",
      "Tabs",
      "Timeline",
      "Alert",
      "Skeleton",
      "EmptyState",
      "ErrorState",
    ]) {
      expect(
        screen.getByRole("heading", { level: 2, name }),
      ).toBeInTheDocument();
    }
    await expectNoA11yViolations(container);
  });
});
