import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { Button } from "@/design-system/components/Button";
import { Checkbox } from "@/design-system/components/Checkbox";
import { expectNoA11yViolations } from "@/design-system/testing/axe";

import { Drawer, type DrawerSide } from "./Drawer";

function FiltersDrawer({ side = "right" as DrawerSide, isDismissable = true }) {
  return (
    <Drawer
      side={side}
      isDismissable={isDismissable}
      title="Filters"
      description="Narrow the list."
      trigger={<Button variant="secondary">Filters</Button>}
      actions={(close) => <Button onPress={close}>Apply</Button>}
    >
      <Checkbox>Active only</Checkbox>
    </Drawer>
  );
}

describe("Drawer", () => {
  it("opens as a labelled modal dialog and passes axe", async () => {
    const user = userEvent.setup();
    render(<FiltersDrawer />);
    await user.click(screen.getByRole("button", { name: "Filters" }));
    const dialog = screen.getByRole("dialog", { name: "Filters" });
    expect(dialog).toHaveAccessibleDescription("Narrow the list.");
    await expectNoA11yViolations(document.body);
  });

  it("traps focus, closes with Escape and restores focus", async () => {
    const user = userEvent.setup();
    render(<FiltersDrawer />);
    const trigger = screen.getByRole("button", { name: "Filters" });
    await user.click(trigger);
    const dialog = screen.getByRole("dialog");
    await waitFor(() =>
      expect(dialog.contains(document.activeElement)).toBe(true),
    );
    for (let i = 0; i < 5; i += 1) {
      await user.tab();
      expect(dialog.contains(document.activeElement)).toBe(true);
    }
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it("closes on outside interaction when dismissable, and via its close button", async () => {
    const user = userEvent.setup();
    render(<FiltersDrawer />);
    await user.click(screen.getByRole("button", { name: "Filters" }));
    await user.click(document.body);
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());

    await user.click(screen.getByRole("button", { name: "Filters" }));
    await user.click(screen.getByRole("button", { name: "Close panel" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("stays open on outside interaction when not dismissable", async () => {
    const user = userEvent.setup();
    render(<FiltersDrawer isDismissable={false} />);
    await user.click(screen.getByRole("button", { name: "Filters" }));
    await user.click(document.body);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it.each<[DrawerSide, string]>([
    ["left", "starting:-translate-x-full"],
    ["right", "starting:translate-x-full"],
    ["top", "starting:-translate-y-full"],
    ["bottom", "starting:translate-y-full"],
  ])(
    "places a %s drawer and slides only without reduced motion",
    async (side, cls) => {
      const user = userEvent.setup();
      render(<FiltersDrawer side={side} />);
      await user.click(screen.getByRole("button", { name: "Filters" }));
      const panel = screen.getByRole("dialog").parentElement!;
      expect(panel.className).toContain(cls);
      expect(panel.className).toContain("motion-reduce:transition-none");
    },
  );

  it("supports controlled use without a trigger", async () => {
    const user = userEvent.setup();
    function Controlled() {
      const [open, setOpen] = useState(false);
      return (
        <>
          <Button onPress={() => setOpen(true)}>Show details</Button>
          <Drawer title="Details" isOpen={open} onOpenChange={setOpen}>
            Record details
          </Drawer>
        </>
      );
    }
    render(<Controlled />);
    await user.click(screen.getByRole("button", { name: "Show details" }));
    expect(screen.getByRole("dialog", { name: "Details" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });
});
