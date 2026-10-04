import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { EmptyState, ErrorState } from "@/design-system/components";
import { expectHeadingOutline } from "@/design-system/testing/a11y";
import { expectNoA11yViolations } from "@/design-system/testing/axe";
import { ThemeProvider } from "@/design-system/theme/ThemeProvider";

import { AuthenticationTemplate } from "./AuthenticationTemplate";

import type { ReactNode } from "react";

// T16 AuthenticationTemplate (T01-04 UI contract §7).

const frame = (node: ReactNode, theme: "light" | "dark" = "light") => {
  document.documentElement.dataset.theme = theme;
  return render(<ThemeProvider>{node}</ThemeProvider>);
};

describe("AuthenticationTemplate", () => {
  it("has the T16 landmarks, one h1 (the card title) and the skip link first", async () => {
    const user = userEvent.setup();
    const { container } = frame(
      <AuthenticationTemplate
        title="Sign in to MTI 360"
        description="Use your email."
      >
        <p>Form</p>
      </AuthenticationTemplate>,
    );
    expect(screen.getByRole("banner")).toHaveTextContent("MTI 360");
    expect(within(screen.getByRole("banner")).queryByRole("link")).toBeNull();
    expect(screen.getByRole("main")).toHaveAttribute("id", "main-content");
    expect(screen.getByRole("contentinfo")).toHaveTextContent("© MTI 360");
    expect(screen.queryByRole("navigation")).toBeNull();
    expectHeadingOutline(container);
    await user.tab();
    expect(screen.getByRole("link", { name: "Skip to content" })).toHaveFocus();
    await expectNoA11yViolations(container);
  });

  it("puts the decorative brand panel after the form, hidden below desktop", () => {
    const { container } = frame(
      <AuthenticationTemplate title="Sign in to MTI 360">
        <p>Form</p>
      </AuthenticationTemplate>,
    );
    const main = screen.getByRole("main");
    const [form, panel] = [...main.children];
    expect(form).toHaveTextContent("Form");
    expect(panel).toHaveAttribute("aria-hidden", "true");
    expect(panel!.className).toMatch(/(^| )hidden( |$)/);
    expect(panel!.className).toContain("desktop:flex");
    expect(panel!.querySelector("a, button, input, h1, h2, h3")).toBeNull();
    expect(panel).toHaveTextContent(
      "Acquire Students. Simplify Operations. Grow Your Institute.",
    );
    // Tablet and wider: the form column is capped at max-w-md; 16px gutter on mobile.
    expect(container.querySelector(".max-w-md")).not.toBeNull();
    expect(form!.className).toContain("px-4");
    // No tenant branding before sign-in.
    expect(container.textContent).not.toMatch(/institute name|logo/i);
  });

  it("lets a replacing state own the h1", async () => {
    const { container } = frame(
      <AuthenticationTemplate>
        <ErrorState titleAs="h1" title="This reset link is incomplete" />
      </AuthenticationTemplate>,
      "dark",
    );
    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "This reset link is incomplete",
      }),
    ).toBeInTheDocument();
    expectHeadingOutline(container);
    await expectNoA11yViolations(container);
  });

  it("states expose a focusable title through titleRef", () => {
    const ref = { current: null as HTMLHeadingElement | null };
    frame(
      <EmptyState
        titleAs="h1"
        title="No institute available"
        description="x"
        titleRef={ref}
      />,
    );
    expect(ref.current).toHaveAttribute("tabindex", "-1");
    ref.current!.focus();
    expect(ref.current).toHaveFocus();
  });
});
