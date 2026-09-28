import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "@/design-system/testing/axe";

import { AppNavigation } from "./AppNavigation";
import { TEST_NAVIGATION } from "./test-helpers";

function renderNavigation(
  pathname: string,
  props: Partial<Parameters<typeof AppNavigation>[0]> = {},
) {
  return render(
    <AppNavigation
      label="Tenant navigation"
      navigation={TEST_NAVIGATION}
      pathname={pathname}
      {...props}
    />,
  );
}

describe("AppNavigation", () => {
  it("renders a labelled navigation landmark with section lists and passes axe", async () => {
    const { container } = renderNavigation("/app");
    const nav = screen.getByRole("navigation", { name: "Tenant navigation" });
    expect(
      within(nav).getByRole("list", { name: "Operations" }),
    ).toBeInTheDocument();
    expect(
      within(nav).getByRole("link", { name: "Dashboard" }),
    ).toHaveAttribute("href", "/app");
    await expectNoA11yViolations(container);
  });

  it("marks only the current page with aria-current", () => {
    renderNavigation("/app/admissions/leads");
    expect(screen.getByRole("link", { name: "Leads" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(
      screen.getByRole("link", { name: /^Admissions/ }),
    ).not.toHaveAttribute("aria-current");
    expect(screen.getByRole("link", { name: "Dashboard" })).not.toHaveAttribute(
      "aria-current",
    );
  });

  it("opens the branch that contains the current page", () => {
    renderNavigation("/app/admissions/applications");
    expect(
      screen.getByRole("button", { name: "Admissions pages" }),
    ).toHaveAttribute("aria-expanded", "true");
    expect(
      screen.getByRole("button", { name: "Academics pages" }),
    ).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("link", { name: "Courses" })).toBeNull();
  });

  it("toggles nested items with the keyboard", async () => {
    const user = userEvent.setup();
    renderNavigation("/app");
    const toggle = screen.getByRole("button", { name: "Academics pages" });
    toggle.focus();
    await user.keyboard("{Enter}");
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("link", { name: "Courses" })).toBeVisible();
    await user.keyboard(" ");
    expect(toggle).toHaveAttribute("aria-expanded", "false");
  });

  it("follows the document order with Tab", async () => {
    const user = userEvent.setup();
    renderNavigation("/app");
    await user.tab();
    expect(screen.getByRole("link", { name: "Dashboard" })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("link", { name: /^Admissions/ })).toHaveFocus();
    await user.tab();
    expect(
      screen.getByRole("button", { name: "Admissions pages" }),
    ).toHaveFocus();
  });

  it("announces badge counts with their description", () => {
    renderNavigation("/app");
    expect(
      screen.getByRole("link", { name: "Admissions, 12 new enquiries" }),
    ).toBeInTheDocument();
  });

  it("keeps labels available to assistive technology in rail mode", async () => {
    const { container } = renderNavigation("/app", { display: "rail" });
    const link = screen.getByRole("link", { name: "Finance" });
    expect(within(link).getByText("Finance")).toHaveClass("sr-only");
    // Hidden by CSS in rail mode (jsdom does not apply the stylesheet).
    expect(
      screen.getByRole("button", { name: "Admissions pages" }),
    ).toHaveClass("hidden");
    await expectNoA11yViolations(container);
  });

  it("reports navigation so a drawer can close", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    renderNavigation("/app", { onNavigate });
    const link = screen.getByRole("link", { name: "Finance" });
    link.addEventListener("click", (event) => event.preventDefault());
    await user.click(link);
    expect(onNavigate).toHaveBeenCalledTimes(1);
  });
});
