import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ThemeProvider } from "@/design-system/theme/ThemeProvider";

import HomePage from "./page";

// Toolchain smoke test (T00-02): proves the Vitest + jsdom + Testing Library
// setup renders a React component. Not a product/business test. Since T00-06
// the page also exposes the theme control (the root layout provides the
// ThemeProvider).
describe("HomePage", () => {
  it("renders the MTI 360 level-one heading", () => {
    render(
      <ThemeProvider>
        <HomePage />
      </ThemeProvider>,
    );

    expect(
      screen.getByRole("heading", { level: 1, name: "MTI 360" }),
    ).toBeInTheDocument();
  });

  it("offers the Light / Dark / System theme control", () => {
    render(
      <ThemeProvider>
        <HomePage />
      </ThemeProvider>,
    );

    expect(screen.getByRole("group", { name: "Theme" })).toBeInTheDocument();
  });
});
