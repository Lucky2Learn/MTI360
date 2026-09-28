import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { expectNoA11yViolations } from "@/design-system/testing/axe";

import { MobileNavigation } from "./MobileNavigation";
import { TEST_NAVIGATION } from "./test-helpers";

function renderMobileNavigation() {
  return render(
    <MobileNavigation
      experienceLabel="Tenant Application"
      navigationLabel="Tenant navigation"
      navigation={TEST_NAVIGATION}
      pathname="/app/admissions/leads"
    />,
  );
}

describe("MobileNavigation", () => {
  it("opens the navigation in a labelled drawer and passes axe", async () => {
    const user = userEvent.setup();
    renderMobileNavigation();
    const trigger = screen.getByRole("button", { name: "Open navigation" });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    await user.click(trigger);
    const drawer = screen.getByRole("dialog", { name: "Tenant Application" });
    expect(
      within(drawer).getByRole("navigation", { name: "Tenant navigation" }),
    ).toBeInTheDocument();
    expect(within(drawer).getByRole("link", { name: "Leads" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    await expectNoA11yViolations(document.body);
  });

  it("moves focus into the drawer, closes with Escape and restores focus", async () => {
    const user = userEvent.setup();
    renderMobileNavigation();
    const trigger = screen.getByRole("button", { name: "Open navigation" });
    await user.click(trigger);
    const drawer = screen.getByRole("dialog");
    await waitFor(() =>
      expect(drawer.contains(document.activeElement)).toBe(true),
    );
    await user.tab();
    expect(drawer.contains(document.activeElement)).toBe(true);
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it("closes after a link is followed", async () => {
    const user = userEvent.setup();
    renderMobileNavigation();
    await user.click(screen.getByRole("button", { name: "Open navigation" }));
    const link = within(screen.getByRole("dialog")).getByRole("link", {
      name: "Finance",
    });
    link.addEventListener("click", (event) => event.preventDefault());
    await user.click(link);
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("closes with its close button", async () => {
    const user = userEvent.setup();
    renderMobileNavigation();
    await user.click(screen.getByRole("button", { name: "Open navigation" }));
    await user.click(screen.getByRole("button", { name: "Close navigation" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });
});
