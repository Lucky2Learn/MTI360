import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { expectNoA11yViolations } from "@/design-system/testing/axe";

import { Tab, TabList, TabPanel, Tabs } from "./Tabs";

function StudentTabs({ disabled = false }: { disabled?: boolean }) {
  return (
    <Tabs defaultSelectedKey="profile">
      <TabList aria-label="Student record">
        <Tab id="profile">Profile</Tab>
        <Tab id="documents">Documents</Tab>
        <Tab id="fees" isDisabled={disabled}>
          Fees
        </Tab>
        <Tab id="certificates">Certificates</Tab>
      </TabList>
      <TabPanel id="profile">Deck Cadet · DNS 2026-B</TabPanel>
      <TabPanel id="documents">CDC, passport, medical fitness</TabPanel>
      <TabPanel id="fees">Fee schedule</TabPanel>
      <TabPanel id="certificates">STCW basic safety</TabPanel>
    </Tabs>
  );
}

describe("Tabs", () => {
  it("exposes a labelled tablist with associated panels", async () => {
    const { container } = render(<StudentTabs />);

    expect(
      screen.getByRole("tablist", { name: "Student record" }),
    ).toBeInTheDocument();
    const profile = screen.getByRole("tab", { name: "Profile" });
    expect(profile).toHaveAttribute("aria-selected", "true");
    const panel = screen.getByRole("tabpanel");
    expect(panel).toHaveAttribute("aria-labelledby", profile.id);
    expect(panel).toHaveTextContent("Deck Cadet");
    await expectNoA11yViolations(container);
  });

  it("moves with arrow keys, Home and End", async () => {
    const user = userEvent.setup();
    render(<StudentTabs />);

    await user.tab();
    expect(screen.getByRole("tab", { name: "Profile" })).toHaveFocus();

    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Documents" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("tabpanel")).toHaveTextContent("CDC");

    await user.keyboard("{End}");
    expect(screen.getByRole("tab", { name: "Certificates" })).toHaveAttribute(
      "aria-selected",
      "true",
    );

    await user.keyboard("{Home}");
    expect(screen.getByRole("tab", { name: "Profile" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("skips disabled tabs", async () => {
    const user = userEvent.setup();
    render(<StudentTabs disabled />);

    await user.click(screen.getByRole("tab", { name: "Documents" }));
    await user.keyboard("{ArrowRight}");

    expect(screen.getByRole("tab", { name: "Certificates" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("tab", { name: "Fees" })).toHaveAttribute(
      "aria-disabled",
      "true",
    );
  });

  it("marks the selected tab with an indicator and weight, not colour alone", () => {
    render(<StudentTabs />);
    const selected = screen.getByRole("tab", { name: "Profile" });
    expect(selected.className).toContain(
      "data-selected:border-accent-maritime",
    );
    expect(selected.className).toContain("data-selected:font-semibold");
    expect(selected).toHaveAttribute("data-selected", "true");
  });

  it("scrolls horizontally instead of overflowing on small screens", () => {
    render(<StudentTabs />);
    expect(screen.getByRole("tablist").className).toContain("overflow-x-auto");
  });
});
