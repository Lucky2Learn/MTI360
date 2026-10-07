import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  expectHeadingOutline,
  expectNamedControls,
} from "@/design-system/testing/a11y";
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

// Whole-page render + axe over every component: ~2 s alone, but it exceeded
// Vitest's 5 s default under full-suite parallel load once the T00-08 shell
// tests were added, so these tests get an explicit budget — raised to 40 s
// when the T01-09B flow tests made the full suite heavier (~24 s observed
// under load; it still passes in ~2 s on its own).
const WHOLE_PAGE = { timeout: 40_000 };

describe("design-system showcase content", WHOLE_PAGE, () => {
  it("shows every T00-07A, T00-07B, T00-07C, T00-09 and T00-10A section and passes axe", async () => {
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
      "Input",
      "Textarea",
      "Checkbox",
      "Select",
      "Combobox",
      "DatePicker",
      "FileUpload",
      "Student enquiry form",
      "Dialog",
      "AlertDialog",
      "Popover",
      "Tooltip",
      "Drawer",
      "Validation in overlays",
      "Dropdown Menu",
      "Context Menu",
      "Toast",
      "DataTable",
      "Pagination",
      "FilterBar",
      "Search",
      "Radio",
      "Switch",
      "TimePicker",
      "Breakpoints",
      "Container",
      "Stack",
      "Inline",
      "Grid",
      "Section",
      "Two-column layout",
      "Responsive visibility",
    ]) {
      expect(
        screen.getByRole("heading", { level: 2, name }),
      ).toBeInTheDocument();
    }
    // T00-10: every control named; one h1 and no skipped heading levels.
    expectNamedControls(container);
    expectHeadingOutline(container);
    await expectNoA11yViolations(container);
  });
});
