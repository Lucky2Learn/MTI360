import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { Button } from "@/design-system/components/Button";
import { expectFocusContained } from "@/design-system/testing/a11y";
import { expectNoA11yViolations } from "@/design-system/testing/axe";

import { Popover } from "./Popover";

function HelpPopover() {
  return (
    <Popover
      trigger={<Button variant="secondary">What is sea time?</Button>}
      title="Sea time"
    >
      <p>Time served on board a vessel, recorded in the CDC.</p>
      <Button variant="tertiary" size="sm">
        Read more
      </Button>
    </Popover>
  );
}

describe("Popover", () => {
  it("opens a labelled dialog anchored to its trigger and passes axe", async () => {
    const user = userEvent.setup();
    render(<HelpPopover />);
    await user.click(screen.getByRole("button", { name: "What is sea time?" }));
    expect(screen.getByRole("dialog", { name: "Sea time" })).toHaveTextContent(
      "Time served on board a vessel",
    );
    await expectNoA11yViolations(document.body);
  });

  it("moves focus in, closes with Escape and restores focus", async () => {
    const user = userEvent.setup();
    render(<HelpPopover />);
    const trigger = screen.getByRole("button", { name: "What is sea time?" });
    await user.click(trigger);
    const dialog = screen.getByRole("dialog");
    await waitFor(() =>
      expect(dialog.contains(document.activeElement)).toBe(true),
    );
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it("closes on outside interaction", async () => {
    const user = userEvent.setup();
    render(<HelpPopover />);
    await user.click(screen.getByRole("button", { name: "What is sea time?" }));
    await user.click(document.body);
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("accepts an aria-label when there is no visible title", async () => {
    const user = userEvent.setup();
    render(
      <Popover
        trigger={<Button>Quick settings</Button>}
        aria-label="Quick settings"
      >
        Density: comfortable
      </Popover>,
    );
    await user.click(screen.getByRole("button", { name: "Quick settings" }));
    expect(
      screen.getByRole("dialog", { name: "Quick settings" }),
    ).toBeInTheDocument();
  });

  it("is itself the labelled dialog, so the hidden dismiss buttons are inside it (T00-10)", async () => {
    const user = userEvent.setup();
    render(<HelpPopover />);
    await user.click(screen.getByRole("button", { name: "What is sea time?" }));
    const dialog = screen.getByRole("dialog", { name: "Sea time" });
    expect(screen.getAllByRole("dialog")).toHaveLength(1);
    const dismiss = document.querySelectorAll('button[aria-label="Dismiss"]');
    expect(dismiss.length).toBeGreaterThan(0);
    for (const button of dismiss)
      expect(dialog).toContainElement(button as HTMLElement);
    expect(screen.getByRole("heading", { name: "Sea time" }).id).toBe(
      dialog.getAttribute("aria-labelledby"),
    );
  });

  it("contains keyboard focus while open (T00-10)", async () => {
    const user = userEvent.setup();
    render(<HelpPopover />);
    await user.click(screen.getByRole("button", { name: "What is sea time?" }));
    const dialog = screen.getByRole("dialog");
    await waitFor(() =>
      expect(dialog.contains(document.activeElement)).toBe(true),
    );
    await expectFocusContained(user, dialog, 4);
  });
});
